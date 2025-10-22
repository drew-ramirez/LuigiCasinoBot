###########################################################
# File: MemoryMatchUI.py
#
# Description: Discord UI controls for Luigi's Casino Memory Match
# Converted to a persistent View subclass.
###########################################################

import discord
import asyncio
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import (
    render_board_image,
    make_board_flip_gif,
    make_board_reverse_flip_gif,
)
from utils.ui_embeds import make_game_header, make_gif_game_header
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager

# this'll probably be better for future iterations
FLIP_FRAME_DURATION_MS = 90
FLIP_ANIMATION_DELAY = 0.45
MISMATCH_REVEAL_DELAY = 0.55
UNFLIP_FRAME_DURATION_MS = 90
UNFLIP_ANIMATION_DELAY = 0.45


class MemoryMatchControls(discord.ui.View):
    #persistent view for Memory Match with per-card callbacks
    GAME_KEY = MemoryMatch.GAME_KEY

    def __init__(
        self,
        game: MemoryMatch,
        player: discord.User,
        on_finish,
        *,
        animations_enabled: bool,
        wager_options=None,
        start_game_callback=None,
    ):
        super().__init__(timeout=None)
        self.game = game
        self.player = player
        self.on_finish = on_finish
        self.wager_options = wager_options or list(DEFAULT_WAGER_OPTIONS)
        self.start_game_callback = start_game_callback
        self.msg: discord.Message | None = None
        self.animations_enabled = animations_enabled
        self._pending_next_streak: int | None = None
        self._last_streak_info: dict | None = None

        self._build_buttons()

    def _build_buttons(self):
        cols = max(1, getattr(self.game, "COLS", 4) or 1)
        for i in range(len(self.game.board)):
            row = i // cols
            btn = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.secondary,
                custom_id=f"memory_{i}",
                row=row,
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _reset_board_controls(self):
        self.clear_items()
        self._build_buttons()

    BOARD_FILENAME = "memory_board.png"

    def _status_payload(
        self,
        dealer_action: str | None = None,
        *,
        attachment: discord.File | None = None,
        include_board: bool = True,
    ) -> tuple[discord.Embed, list[discord.File]]:
        action = dealer_action or f"Attempts left: {self.game.remaining_attempts}"
        streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            self.player.name,
        )
        multiplier = EconomyManager.star_bonus_multiplier(
            streak, MemoryMatch.GAME_KEY
        )
        streak_summary = f"(⭐ bonus x{multiplier:.2f})"
        if action:
            action = f"{action} | {streak_summary}"
        else:
            action = streak_summary
        session_stars = getattr(self.game, "session_stars", self.game.stars)
        stats = {
            "active_bet": self.game.bet,
            "stars_current": session_stars,
            "dealer_action": action,
        }
        embed = make_game_header(self.player, "Memory Match", stats)
        files: list[discord.File] = []
        if attachment is not None:
            embed.set_image(url=f"attachment://{attachment.filename}")
            files.append(attachment)
        elif include_board:
            board_file = self._board_file()
            embed.set_image(url=f"attachment://{board_file.filename}")
            files.append(board_file)
        return embed, files

    def _board_file(self, filename: str | None = None) -> discord.File:
        target_name = filename or self.BOARD_FILENAME
        png = render_board_image(self.game)
        png.seek(0)
        return discord.File(png, target_name)

    def _status_text(self, dealer_action: str | None = None) -> str:
        action = dealer_action or f"Attempts left: {self.game.remaining_attempts}"
        streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            self.player.name,
        )
        multiplier = EconomyManager.star_bonus_multiplier(
            streak, MemoryMatch.GAME_KEY
        )
        streak_summary = f"(⭐ bonus x{multiplier:.2f})"
        if action:
            action = f"{action} | {streak_summary}"
        else:
            action = streak_summary
        session_stars = getattr(self.game, "session_stars", self.game.stars)
        stats = {
            "active_bet": self.game.bet,
            "stars_current": session_stars,
            "dealer_action": action,
        }
        return make_gif_game_header(self.player, "Memory Match", stats)

    ###########################################################
    # callback factory
    ###########################################################
    def _make_callback(self, pos: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return

            await interaction.response.defer()
            await self.handle_memory_flip(interaction, pos)

        return callback

    ###########################################################
    # main flip handler
    ###########################################################
    async def handle_memory_flip(self, interaction: discord.Interaction, pos: int):
        game = self.game
        msg = self.msg or await interaction.original_response()

        if self.animations_enabled:
            if not game.flip_card(pos):
                await msg.edit(content=self._status_text("Invalid flip."), view=self)
                return

            symbol, _, _ = game.board[pos]

            for child in self.children:
                child.disabled = True
            await msg.edit(view=self)

            gif = make_board_flip_gif(
                game, pos, symbol, duration=FLIP_FRAME_DURATION_MS
            )
            gif.seek(0)
            await msg.edit(
                content=self._status_text(f"Revealing card {pos + 1}..."),
                attachments=[discord.File(gif, filename=f"memory_flip_{pos}.gif")],
                view=self,
            )
            await asyncio.sleep(FLIP_ANIMATION_DELAY)

            await msg.edit(
                content=self._status_text(),
                attachments=[self._board_file()],
                view=self,
            )
        else:
            if not game.flip_card(pos):
                embed, files = self._status_payload("Invalid flip.")
                await msg.edit(
                    content=None,
                    embed=embed,
                    attachments=files,
                    view=self,
                )
                return

            for child in self.children:
                child.disabled = True
            await msg.edit(view=self)

            embed, files = self._status_payload(
                f"Attempts left: {self.game.remaining_attempts}",
            )
            await msg.edit(
                content=None,
                embed=embed,
                attachments=files,
                view=self,
            )

        ###########################################################
        # match check
        ###########################################################
        result = None
        if len(game.revealed) % 2 == 0:
            result = game.check_match()
            if result is None:
                result = True

        if result is False:
            await self._handle_mismatch(msg)
        elif result:
            await self.update_controls_for_match(game.revealed[-2:], msg)
            board_cleared = game.is_board_cleared()
            if game.last_bonus_awarded and not board_cleared:
                if self.animations_enabled:
                    await msg.edit(
                        content=self._status_text("3-Streak, +1 attempt!"),
                        attachments=[self._board_file()],
                        view=self,
                    )
                else:
                    embed_bonus, bonus_files = self._status_payload(
                        "3-Streak, +1 attempt!"
                    )
                    await msg.edit(
                        content=None,
                        embed=embed_bonus,
                        attachments=bonus_files,
                        view=self,
                    )
                game.last_bonus_awarded = False
            elif game.last_bonus_awarded:
                # ensure flag does not linger if the board is cleared
                game.last_bonus_awarded = False

            if board_cleared:
                await self._handle_win(interaction, msg)
                return

        if game.remaining_attempts <= 0:
            await self._handle_loss(msg)
            return

        ###########################################################
        # re-enable buttons
        ###########################################################
        for i, child in enumerate(self.children):
            if i < len(game.board):
                _, _, matched = game.board[i]
                child.disabled = matched
            else:
                child.disabled = True
        await msg.edit(view=self)

    async def _handle_mismatch(self, msg: discord.Message):
        await asyncio.sleep(MISMATCH_REVEAL_DELAY)
        a, b = self.game.revealed[-2], self.game.revealed[-1]
        symbols = [self.game.board[a][0], self.game.board[b][0]]

        if self.animations_enabled:
            gif = make_board_reverse_flip_gif(
                self.game, [a, b], symbols, duration=UNFLIP_FRAME_DURATION_MS
            )
            gif.seek(0)
            await msg.edit(
                content=self._status_text("Not a match!"),
                attachments=[discord.File(gif, "memory_unflip.gif")],
                view=self,
            )
            await asyncio.sleep(UNFLIP_ANIMATION_DELAY)
            self.game.hide_unmatched()
            await msg.edit(
                content=self._status_text(),
                attachments=[self._board_file()],
                view=self,
            )
        else:
            self.game.hide_unmatched()
            embed, files = self._status_payload("Not a match!")
            await msg.edit(
                content=None,
                embed=embed,
                attachments=files,
                view=self,
            )
        await self.update_controls_for_unmatch([a, b], msg)

    async def _handle_win(self, interaction: discord.Interaction, msg: discord.Message):
        final_board = self._board_file()
        current_streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            self.player.name,
        )
        multiplier = EconomyManager.star_bonus_multiplier(
            current_streak, MemoryMatch.GAME_KEY
        )
        payout_base = self.game.bet * 2
        payout = int(round(payout_base * multiplier))
        EconomyManager.payout(self.player.id, payout, self.player.name)
        session_id = getattr(self.game, "metrics_session_id", None)
        MetricsManager.record_game_result(
            session_id,
            result="win",
            payout=payout,
            net=int(payout - self.game.bet),
            metadata={
                "remaining_attempts": self.game.remaining_attempts,
                "session_stars": getattr(self.game, "session_stars", self.game.stars),
            },
        )
        setattr(self.game, "metrics_logged", True)

        streak_info = EconomyManager.adjust_star_bonus(
            self.player.id,
            self.GAME_KEY,
            delta=1,
            username=self.player.name,
            career_increment=1,
        )
        self._last_streak_info = streak_info
        self._pending_next_streak = streak_info["stars"] + 1
        self.game.award_star()

        session_stars = getattr(self.game, "session_stars", self.game.stars)
        summary = (
            f"Board cleared! You won {payout} coins.\n"
            " Continue or Exit Now?"
        )
        if self.animations_enabled:
            await msg.edit(
                content=self._status_text(summary),
                attachments=[final_board],
                view=None,
            )
        else:
            embed, files = self._status_payload(summary, attachment=final_board)
            await msg.edit(content=None, embed=embed, attachments=files, view=None)

        await self._prompt_continue(
            msg,
            next_streak=self._pending_next_streak,
        )

    async def _handle_loss(self, msg: discord.Message):
        current_streak = EconomyManager.star_bonus_count(
            self.player.id,
            self.GAME_KEY,
            self.player.name,
        )
        if current_streak > 0:
            EconomyManager.adjust_star_bonus(
                self.player.id,
                self.GAME_KEY,
                delta=-1,
                username=self.player.name,
            )

        self._last_streak_info = None

        if self.animations_enabled:
            await msg.edit(
                content=self._status_text("No attempts remaining"),
                attachments=[self._board_file()],
                view=None,
            )
        else:
            embed, files = self._status_payload("No attempts remaining")
            await msg.edit(
                content=None,
                embed=embed,
                attachments=files,
                view=None,
            )
        session_id = getattr(self.game, "metrics_session_id", None)
        MetricsManager.record_game_result(
            session_id,
            result="loss",
            payout=0,
            net=int(-self.game.bet),
            metadata={
                "remaining_attempts": self.game.remaining_attempts,
                "session_stars": getattr(self.game, "session_stars", self.game.stars),
            },
        )
        setattr(self.game, "metrics_logged", True)
        await self._show_replay(msg)

    async def _prompt_continue(self, msg: discord.Message, next_streak: int):
        multiplier_next = EconomyManager.star_bonus_multiplier(
            next_streak, MemoryMatch.GAME_KEY
        )
        continue_btn = discord.ui.Button(
            label=f"Continue (next bonus x{multiplier_next:.2f})",
            style=discord.ButtonStyle.green,
        )
        cash_out_btn = discord.ui.Button(
            label="Exit Now",
            style=discord.ButtonStyle.red,
        )

        async def continue_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            if self._last_streak_info is None:
                current = EconomyManager.star_bonus_count(
                    self.player.id,
                    self.GAME_KEY,
                    self.player.name,
                )
                self._last_streak_info = {
                    "stars": current,
                    "career_total": EconomyManager.ensure_user(
                        self.player.id, self.player.name
                    ).get("career_stars_total", 0),
                    "multiplier": EconomyManager.star_bonus_multiplier(
                        current, MemoryMatch.GAME_KEY
                    ),
                }
            streak_info = self._last_streak_info
            self._last_streak_info = None
            self.game.generate_board()
            await self._start_next_round(msg, streak_info=streak_info)

        async def cash_out_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            self._last_streak_info = None
            session_stars = getattr(self.game, "session_stars", self.game.stars)
            summary = f"Cashed out at round {session_stars}"
            final_board = self._board_file()
            if self.animations_enabled:
                await msg.edit(
                    content=self._status_text(summary),
                    attachments=[final_board],
                    view=None,
                )
            else:
                embed, files = self._status_payload(summary)
                await msg.edit(
                    content=None, embed=embed, attachments=files, view=None
                )
            if not getattr(self.game, "metrics_logged", False):
                session_id = getattr(self.game, "metrics_session_id", None)
                MetricsManager.record_game_result(
                    session_id,
                    result="cashout",
                    payout=0,
                    net=0,
                    metadata={
                        "remaining_attempts": self.game.remaining_attempts,
                        "session_stars": session_stars,
                    },
                )
                setattr(self.game, "metrics_logged", True)
            await self._show_replay(msg)

        continue_btn.callback = continue_cb
        cash_out_btn.callback = cash_out_cb

        prompt_view = discord.ui.View()
        prompt_view.add_item(continue_btn)
        prompt_view.add_item(cash_out_btn)

        await msg.edit(view=prompt_view)

    async def _start_next_round(self, msg: discord.Message, streak_info: dict | None = None):
        self._reset_board_controls()
        self.msg = msg
        if streak_info and "stars" in streak_info:
            self._pending_next_streak = streak_info["stars"] + 1
        note = ""
        next_target = self._pending_next_streak
        if next_target:
            note = (
                #f" Next bonus will x{EconomyManager.star_bonus_multiplier(next_target):.2f}."
            )
        message = f"New board ready!\n{note}" if note else "New board ready!"
        if self.animations_enabled:
            await msg.edit(
                content=self._status_text(message),
                attachments=[self._board_file()],
                view=self,
            )
        else:
            embed, files = self._status_payload(message)
            await msg.edit(content=None, embed=embed, attachments=files, view=self)

    async def _show_replay(self, msg: discord.Message):
        if self.on_finish is not None:
            await self.on_finish(self.player.id)

        replay_btn = discord.ui.Button(label="Play Again", style=discord.ButtonStyle.green)
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()

            def make_wager_callback():
                async def on_bet_selected(inner_inter: discord.Interaction, bet_amount: int):
                    if self.start_game_callback is None:
                        await inner_inter.response.send_message(
                            "Unable to start new game right now.",
                            ephemeral=True,
                        )
                        return

                    initial_stars = EconomyManager.star_bonus_count(
                        self.player.id,
                        self.GAME_KEY,
                        self.player.name,
                    )
                    new_game = MemoryMatch(
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

            wager_view = BetSelectView(
                self.player.id,
                self.player.name,
                make_wager_callback(),
                wager_options=self.wager_options,
            )

            await msg.edit(view=wager_view)

        async def quit_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            if not getattr(self.game, "metrics_logged", False):
                session_id = getattr(self.game, "metrics_session_id", None)
                MetricsManager.record_game_result(
                    session_id,
                    result="quit",
                    payout=0,
                    net=0,
                    metadata={
                        "remaining_attempts": self.game.remaining_attempts,
                        "session_stars": getattr(self.game, "session_stars", self.game.stars),
                    },
                )
                setattr(self.game, "metrics_logged", True)
            await msg.edit(view=None)

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

        await msg.edit(view=replay_view)

    ###########################################################
    # UI updates for matched cards
    ###########################################################
    async def update_controls_for_match(self, positions: list[int], message: discord.Message):
        for child in self.children:
            if hasattr(child, "custom_id"):
                idx = int(child.custom_id.split("_")[-1])
                if idx in positions:
                    child.label = "⭐"
                    child.disabled = True
        await message.edit(view=self)

    ###########################################################
    # UI updates for unmatched cards
    ###########################################################
    async def update_controls_for_unmatch(self, positions: list[int], message: discord.Message):
        for child in self.children:
            if hasattr(child, "custom_id"):
                idx = int(child.custom_id.split("_")[-1])
                if idx in positions:
                    child.label = str(idx + 1)
                    child.disabled = False
        await message.edit(view=self)


def make_memory_view(
    game: MemoryMatch,
    player: discord.User,
    on_finish,
    *,
    animations_enabled: bool,
    wager_options=None,
    start_game_callback=None,
) -> MemoryMatchControls:
    return MemoryMatchControls(
        game,
        player,
        on_finish,
        animations_enabled=animations_enabled,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
    )
