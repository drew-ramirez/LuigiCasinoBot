###########################################################
# File: PairAGoneUI.py
#
# Description: Discord UI controls for Pair-a-Gone
###########################################################

import asyncio
import io
from contextlib import suppress
import discord
from PIL import Image

from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import (
    make_pair_flicker_gif,
    render_pair_board,
    render_pair_board_with_blanks,
)
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager

faces = load_memory_faces()
backs = load_memory_backs()


class PairControls(discord.ui.View):
    GAME_KEY = PairAGone.GAME_KEY

    def __init__(
        self,
        game: PairAGone,
        player: discord.User,
        on_finish=None,
        *,
        animations_enabled: bool,
        wager_options=None,
        start_game_callback=None,
        msg: discord.Message | None = None,
    ):
        super().__init__(timeout=None)
        self.game = game
        self.player = player
        self.on_finish = on_finish
        self.wager_options = (
            list(wager_options)
            if wager_options is not None
            else list(DEFAULT_WAGER_OPTIONS)
        )
        self.start_game_callback = start_game_callback
        self.msg = msg
        self.animations_enabled = animations_enabled

        self._build_buttons()
        self._refresh_buttons()

    ###########################################################
    # Helpers
    ###########################################################
    def _status_stats(self, dealer_action: str | None = None) -> dict:
        action = (
            dealer_action or f"Cards remaining in deck: {self.game.remaining_in_deck()}"
        )
        streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            getattr(self.player, "name", "Unknown"),
        )
        multiplier = EconomyManager.star_bonus_multiplier(streak, self.GAME_KEY)
        if action:
            action = f"{action} \n(⭐ bonus x{multiplier:.2f})"
        else:
            action = f"\n(⭐ bonus x{multiplier:.2f})"
        return {
            "active_bet": self.game.bet,
            "stars_current": getattr(self.game, "session_stars", self.game.stars),
            "dealer_action": action,
        }

    def _header_payload(
        self, dealer_action: str | None = None
    ) -> tuple[str | None, discord.Embed | None]:
        stats = self._status_stats(dealer_action)
        if self.animations_enabled:
            return make_gif_game_header(self.player, "Pair-a-Gone", stats), None
        embed = make_game_header(self.player, "Pair-a-Gone", stats)
        return None, embed

    async def _apply_status(
        self,
        msg: discord.Message,
        dealer_action: str | None = None,
        *,
        attachments: list[discord.File] | None = None,
        view: discord.ui.View | None,
    ) -> None:
        attachment_name = attachments[0].filename if attachments else None
        content, embed = self._header_payload(dealer_action)
        if embed and attachment_name:
            embed.set_image(url=f"attachment://{attachment_name}")
        edit_kwargs: dict[str, object] = {
            "content": content,
            "embed": embed,
            "view": view,
        }
        if attachments is not None:
            edit_kwargs["attachments"] = attachments
        await msg.edit(**edit_kwargs)

    def _board_file(self, filename: str = "pair_board.png") -> discord.File:
        board_bytes = render_pair_board(self.game)
        board_bytes.seek(0)
        return discord.File(board_bytes, filename)

    def _build_buttons(self):
        total = self.game.COLS * self.game.ROWS
        for i in range(total):
            btn = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.secondary,
                custom_id=f"pair_{i}",
                row=i // self.game.COLS,
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _refresh_buttons(self):
        deck_remaining = self.game.remaining_in_deck()
        for i, child in enumerate(self.children):
            if not isinstance(child, discord.ui.Button):
                continue
            has_card = i < len(self.game.board) and self.game.board[i] is not None
            if has_card:
                child.disabled = False
                child.label = str(i + 1)
            else:
                if deck_remaining == 0:
                    child.disabled = True
                    child.label = "\u2800"  # blank button
                else:
                    child.disabled = False
                    child.label = str(i + 1)

    ###########################################################
    # Callbacks
    ###########################################################
    def _make_callback(self, pos: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                await interaction.response.send_message(
                    "Not your game!", ephemeral=True
                )
                return

            await interaction.response.defer()
            await self.handle_pair_flip(interaction, pos)

        return callback

    ###########################################################
    # Core flow
    ###########################################################
    async def handle_pair_flip(self, interaction: discord.Interaction, pos: int):
        msg = self.msg or await interaction.original_response()
        self.msg = msg

        if pos in self.game.selected:
            return

        for child in self.children:
            if (
                isinstance(child, discord.ui.Button)
                and child.custom_id == f"pair_{pos}"
            ):
                child.disabled = True
                break
        await msg.edit(view=self)

        self.game.selected.append(pos)
        if len(self.game.selected) < 2:
            return

        a, b = self.game.selected
        self.game.selected = []

        sa, sb = self.game.board[a], self.game.board[b]
        ra, ca = divmod(a, self.game.COLS)
        rb, cb = divmod(b, self.game.COLS)
        is_adjacent = abs(ra - rb) <= 1 and abs(ca - cb) <= 1
        is_match = sa == sb and sa is not None and is_adjacent

        if not is_match:
            self._refresh_buttons()
            attachments = None
            if not self.animations_enabled:
                attachments = [self._board_file()]
            await self._apply_status(
                msg,
                "No match!",
                attachments=attachments,
                view=self,
            )
            return

        for child in self.children:
            child.disabled = True
        await msg.edit(view=self)

        await self._play_match_sequence(msg, a, b, sa, sb)

        self._refresh_buttons()
        await msg.edit(view=self)

        if self.game.is_board_cleared():
            await self._handle_board_cleared(msg)
            return

        if not self.game.has_possible_moves():
            await self._handle_no_moves(msg)
            return

    async def _play_match_sequence(
        self, msg: discord.Message, a: int, b: int, sa: str, sb: str
    ):
        if not self.animations_enabled:
            new_cards = self.game.remove_and_fall([a, b])
            if new_cards:
                action = (
                    f"Match! Cards in Deck: "
                    f"{self.game.remaining_in_deck()}"
                )
            else:
                action = (
                    f"Match! Cards remaining in deck: "
                    f"{self.game.remaining_in_deck()}"
                )
            await self._apply_status(
                msg,
                action,
                attachments=[self._board_file()],
                view=self,
            )
            return

        flicker_gif = make_pair_flicker_gif(
            self.game, [a, b], [sa, sb], duration=70
        )
        flicker_gif.seek(0)
        await self._apply_status(
            msg,
            "Match!",
            attachments=[discord.File(flicker_gif, "pair_flicker.gif")],
            view=self,
        )
        await asyncio.sleep(0.6)

        new_cards = self.game.remove_and_fall([a, b])

        if not new_cards:
            await self._apply_status(
                msg,
                f"Pair-a-Gone continues! Cards remaining: {self.game.remaining_in_deck()}",
                attachments=[self._board_file()],
                view=self,
            )
            await asyncio.sleep(0.6)
            return

        blanks = [pos for pos, _ in new_cards]
        blanks_bytes = render_pair_board_with_blanks(self.game, blanks)
        blanks_bytes.seek(0)
        await self._apply_status(
            msg,
            "Dealer is dealing new cards...",
            attachments=[discord.File(blanks_bytes, "pair_board.png")],
            view=self,
        )
        await asyncio.sleep(0.4 if self.animations_enabled else 0.25)

        try:
            flip_gif = self.make_simultaneous_flip_gif(
                self.game, new_cards, duration=80
            )
            flip_gif.seek(0)
            await self._apply_status(
                msg,
                f"Dealer flips new cards! Cards remaining: {self.game.remaining_in_deck()}",
                attachments=[discord.File(flip_gif, "pair_flip.gif")],
                view=self,
            )
            await asyncio.sleep(0.8)
        except Exception as e:
            print(f"[PairAGoneUI] flip gif failed: {e}")
            await asyncio.sleep(0.2)

        await self._apply_status(
            msg,
            f"Pair-a-Gone continues! Cards remaining: {self.game.remaining_in_deck()}",
            attachments=[self._board_file()],
            view=self,
        )

    async def _handle_board_cleared(self, msg: discord.Message):
        player_name = getattr(self.player, "name", "Unknown")
        current_streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            player_name,
        )
        multiplier = EconomyManager.star_bonus_multiplier(current_streak, self.GAME_KEY)
        base_payout = self.game.bet * 2
        payout = int(round(base_payout * multiplier))

        self.game.handle_game_end(won=True)
        EconomyManager.payout(self.player.id, payout, player_name)
        session_id = getattr(self.game, "metrics_session_id", None)
        MetricsManager.record_game_result(
            session_id,
            result="win",
            payout=payout,
            net=int(payout - self.game.bet),
            metadata={
                "remaining_deck": self.game.remaining_in_deck(),
                "session_stars": getattr(self.game, "session_stars", self.game.stars),
            },
        )
        setattr(self.game, "metrics_logged", True)

        streak_info = EconomyManager.adjust_star_bonus(
            self.player.id,
            self.GAME_KEY,
            delta=1,
            username=player_name,
            career_increment=1,
        )

        session_stars = getattr(self.game, "session_stars", self.game.stars)
        summary = (
            f"Board cleared! You won {payout} coins. Stars this session: {session_stars}. "
            f"Streak: {streak_info['stars']} (Career {streak_info['career_total']})"
        )

        await self._apply_status(
            msg,
            summary,
            attachments=[self._board_file()],
            view=None,
        )
        await self._show_replay(msg)

    async def _handle_no_moves(self, msg: discord.Message):
        player_name = getattr(self.player, "name", "Unknown")
        current_streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            player_name,
        )
        if current_streak > 0:
            EconomyManager.adjust_star_bonus(
                self.player.id,
                self.GAME_KEY,
                delta=-1,
                username=player_name,
            )
        self.game.handle_game_end(won=False)
        await self._apply_status(
            msg,
            "Too bad. No moves left.",
            attachments=[self._board_file()],
            view=None,
        )
        session_id = getattr(self.game, "metrics_session_id", None)
        MetricsManager.record_game_result(
            session_id,
            result="loss",
            payout=0,
            net=int(-self.game.bet),
            metadata={
                "remaining_deck": self.game.remaining_in_deck(),
                "session_stars": getattr(self.game, "session_stars", self.game.stars),
            },
        )
        setattr(self.game, "metrics_logged", True)
        await self._show_replay(msg)

    async def _show_replay(self, msg: discord.Message):
        if self.on_finish is not None:
            await self.on_finish(self.player.id)

        replay_btn = discord.ui.Button(
            label="Play Again", style=discord.ButtonStyle.green
        )
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()

            if self.start_game_callback is None:
                await btn_inter.response.send_message(
                    "Unable to start new game right now.",
                    ephemeral=True,
                )
                return

            def make_wager_callback():
                async def on_bet_selected(
                    inner_inter: discord.Interaction, bet_amount: int
                ):
                    initial_stars = EconomyManager.star_bonus_count(
                        self.player.id,
                        self.GAME_KEY,
                        player_name,
                    )
                    new_game = PairAGone(
                        self.player.id,
                        bet_amount,
                        initial_stars=initial_stars,
                    )
                    await self.start_game_callback(
                        inner_inter,
                        bet_amount,
                        new_game=new_game,
                    )

                return on_bet_selected

            player_name = getattr(self.player, "display_name", self.player.name)
            wager_view = BetSelectView(
                self.player.id,
                player_name,
                make_wager_callback(),
                wager_options=self.wager_options,
            )

            try:
                await btn_inter.edit_original_response(view=wager_view)
            except Exception:
                with suppress(Exception):
                    await msg.edit(view=wager_view)

        async def quit_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            action = "Thanks for playing Pair-a-Gone!"
            if self.animations_enabled:
                await self._apply_status(
                    msg,
                    action,
                    view=None,
                )
            else:
                await self._apply_status(
                    msg,
                    action,
                    attachments=[self._board_file()],
                    view=None,
                )
            if not getattr(self.game, "metrics_logged", False):
                session_id = getattr(self.game, "metrics_session_id", None)
                MetricsManager.record_game_result(
                    session_id,
                    result="quit",
                    payout=0,
                    net=0,
                    metadata={
                        "remaining_deck": self.game.remaining_in_deck(),
                        "session_stars": getattr(self.game, "session_stars", self.game.stars),
                    },
                )
                setattr(self.game, "metrics_logged", True)
            if self.on_finish is not None:
                await self.on_finish(self.player.id)

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

        with suppress(Exception):
            await msg.edit(view=replay_view)

    ###########################################################################
    # Simultaneous flip gif generator
    ###########################################################################
    def make_simultaneous_flip_gif(self, game, new_cards, duration=80) -> io.BytesIO:
        base_board = Image.open(
            render_pair_board_with_blanks(game, [pos for pos, _ in new_cards])
        ).convert("RGBA")

        frames = []

        frame1 = base_board.copy()
        for pos, _ in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            back = backs.get("back_full")
            frame1.paste(back, (slot_x, slot_y), mask=back)
        frames.append(frame1)

        frame2 = base_board.copy()
        for pos, _ in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            half = backs.get("back_half")
            frame2.paste(half, (slot_x, slot_y), mask=half)
        frames.append(frame2)

        frame3 = base_board.copy()
        for pos, _ in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            edge = backs.get("back_edge")
            frame3.paste(edge, (slot_x, slot_y), mask=edge)
        frames.append(frame3)

        frame4 = base_board.copy()
        for pos, sym in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            face_edge = faces.get_flip(sym)
            frame4.paste(face_edge, (slot_x, slot_y), mask=face_edge)
        frames.append(frame4)

        frame5 = base_board.copy()
        for pos, sym in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            face = faces.get_face(sym)
            frame5.paste(face, (slot_x, slot_y), mask=face)
        frames.append(frame5)

        out = io.BytesIO()
        frames[0].save(
            out,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=1,
            disposal=2,
            optimize=False,
        )
        out.seek(0)
        return out


def make_pair_view(
    game: PairAGone,
    player: discord.User,
    on_finish,
    *,
    animations_enabled: bool,
    wager_options=None,
    start_game_callback=None,
    msg: discord.Message | None = None,
) -> PairControls:
    return PairControls(
        game,
        player,
        on_finish,
        animations_enabled=animations_enabled,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
        msg=msg,
    )
