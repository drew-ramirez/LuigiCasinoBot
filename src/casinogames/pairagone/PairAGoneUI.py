###########################################################
# File: PairAGoneUI.py
#
# Description: Discord UI controls for Pair-a-Gone
###########################################################

import asyncio
import io

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
from utils.ui_embeds import make_game_header
from economy.EconomyManager import EconomyManager

faces = load_memory_faces()
backs = load_memory_backs()


class PairControls(discord.ui.View):
    def __init__(
        self,
        game: PairAGone,
        player: discord.User,
        on_finish=None,
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

        self._build_buttons()
        self._refresh_buttons()

    ###########################################################
    # Helpers
    ###########################################################
    def _header(self, dealer_action: str | None = None) -> str:
        action = (
            dealer_action or f"Cards remaining in deck: {self.game.remaining_in_deck()}"
        )
        stats = {
            "active_bet": self.game.bet,
            "stars_current": self.game.stars,
            "dealer_action": action,
        }
        return make_game_header(self.player, "Pair-a-Gone", stats)

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
                    child.label = "\u2800" # blank button
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
            await msg.edit(content=self._header("No match!"), view=self)
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
        flicker_gif = make_pair_flicker_gif(self.game, [a, b], [sa, sb], duration=70)
        flicker_gif.seek(0)
        await msg.edit(
            content=self._header("Match!"),
            attachments=[discord.File(flicker_gif, "pair_flicker.gif")],
            view=self,
        )
        await asyncio.sleep(0.6)

        new_cards = self.game.remove_and_fall([a, b])

        if not new_cards:
            await msg.edit(
                content=self._header(
                    f"Pair-a-Gone continues! Cards remaining: {self.game.remaining_in_deck()}"
                ),
                attachments=[self._board_file()],
                view=self,
            )
            await asyncio.sleep(0.6)
            return

        blanks = [pos for pos, _ in new_cards]
        blanks_bytes = render_pair_board_with_blanks(self.game, blanks)
        blanks_bytes.seek(0)
        await msg.edit(
            content=self._header("Dealer is dealing new cards..."),
            attachments=[discord.File(blanks_bytes, "pair_board.png")],
            view=self,
        )
        await asyncio.sleep(0.4)

        try:
            flip_gif = self.make_simultaneous_flip_gif(
                self.game, new_cards, duration=80
            )
            flip_gif.seek(0)
            await msg.edit(
                content=self._header(
                    f"Dealer flips new cards! Cards remaining: {self.game.remaining_in_deck()}"
                ),
                attachments=[discord.File(flip_gif, "pair_flip.gif")],
                view=self,
            )
            await asyncio.sleep(0.8)
        except Exception as e:
            print(f"[PairAGoneUI] flip gif failed: {e}")

        await msg.edit(
            content=self._header(
                f"Pair-a-Gone continues! Cards remaining: {self.game.remaining_in_deck()}"
            ),
            attachments=[self._board_file()],
            view=self,
        )

    async def _handle_board_cleared(self, msg: discord.Message):
        self.game.handle_game_end(won=True)
        payout = self.game.bet * 2
        EconomyManager.payout(self.player.id, payout, self.player.name)

        await msg.edit(
            content=self._header(
                f"Board cleared! You won {payout} coins. Stars: {self.game.stars}"
            ),
            attachments=[self._board_file()],
            view=None,
        )
        await self._show_replay(msg)

    async def _handle_no_moves(self, msg: discord.Message):
        self.game.handle_game_end(won=False)
        await msg.edit(
            content=self._header("Too bad. No moves left."),
            attachments=[self._board_file()],
            view=None,
        )
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
                    new_game = PairAGone(self.player.id, bet_amount)
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

            await msg.edit(view=wager_view)

        async def quit_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            await msg.edit(
                content=self._header("Thanks for playing Pair-a-Gone!"), view=None
            )

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

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
    wager_options=None,
    start_game_callback=None,
) -> PairControls:
    return PairControls(
        game,
        player, 
        on_finish,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
    )
