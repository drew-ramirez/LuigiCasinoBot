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
from utils.ui_embeds import make_game_header
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from economy.EconomyManager import EconomyManager


class MemoryMatchControls(discord.ui.View):
    #persistent view for Memory Match with per-card callbacks

    def __init__(
        self,
        game: MemoryMatch,
        player: discord.User,
        on_finish,
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

        self._build_buttons()

    def _build_buttons(self):
        for i in range(len(self.game.board)):
            btn = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.secondary,
                custom_id=f"memory_{i}",
                row=i // 4,
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _status_text(self, dealer_action: str | None = None) -> str:
        action = dealer_action or f"Attempts left: {self.game.remaining_attempts}"
        stats = {
            "active_bet": self.game.bet,
            "stars_current": self.game.stars,
            "dealer_action": action,
        }
        return make_game_header(self.player, "Memory Match", stats)

    def _board_file(self, filename: str = "board.png") -> discord.File:
        png = render_board_image(self.game)
        png.seek(0)
        return discord.File(png, filename)

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

        if not game.flip_card(pos):
            await msg.edit(content=self._status_text("Invalid flip."), view=self)
            return

        symbol, _, _ = game.board[pos]

        # disable buttons during animation
        for child in self.children:
            child.disabled = True
        await msg.edit(view=self)

        ###########################################################
        # flip animation
        ###########################################################
        gif = make_board_flip_gif(game, pos, symbol, duration=120)
        await msg.edit(
            content=self._status_text(f"Revealing card {pos + 1}..."),
            attachments=[discord.File(gif, filename=f"board_flip_{pos}.gif")],
        )
        await asyncio.sleep(0.6)

        ###########################################################
        # update static board
        ###########################################################
        await msg.edit(
            content=self._status_text(),
            attachments=[self._board_file()],
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
            if game.is_board_cleared():
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
        await asyncio.sleep(1.0)
        a, b = self.game.revealed[-2], self.game.revealed[-1]
        symbols = [self.game.board[a][0], self.game.board[b][0]]

        gif = make_board_reverse_flip_gif(self.game, [a, b], symbols, duration=120)
        await msg.edit(
            content=self._status_text("Not a match!"),
            attachments=[discord.File(gif, "board_unflip.gif")],
        )

        await asyncio.sleep(0.6)
        self.game.hide_unmatched()

        await msg.edit(
            content=self._status_text(),
            attachments=[self._board_file()],
        )
        await self.update_controls_for_unmatch([a, b], msg)

    async def _handle_win(self, interaction: discord.Interaction, msg: discord.Message):
        payout = self.game.bet * 2
        EconomyManager.payout(self.player.id, payout, self.player.name)

        await msg.edit(
            content=self._status_text(f"Board cleared! You won {payout} coins."),
            attachments=[self._board_file()],
        )
        await self._show_replay(msg)

    async def _handle_loss(self, msg: discord.Message):
        await msg.edit(
            content=self._status_text("No attempts remaining. Round over."),
            attachments=[self._board_file()],
        )
        await self._show_replay(msg)

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

                    new_game = MemoryMatch(self.player.id, bet_amount)
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
    wager_options=None,
    start_game_callback=None,
) -> MemoryMatchControls:
    return MemoryMatchControls(
        game,
        player,
        on_finish,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
    )
