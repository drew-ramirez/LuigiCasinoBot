###########################################################
# File: LuckyStarsUI.py
#
# Description: Discord UI controls and animations for Lucky Stars
###########################################################

import asyncio
import io

import discord

from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import (
    make_slide_animation,
    render_lucky_board,
)
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_game_header
from economy.EconomyManager import EconomyManager

faces = load_memory_faces()
backs = load_memory_backs()


class LuckyStarsView(discord.ui.View):
    def __init__(
        self,
        game: LuckyStars,
        player: discord.User,
        on_finish,
        wager_options=None,
        start_game_callback=None,
        message: discord.Message | None = None,
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
        self.msg = message

        self.left_button = LuckyStarsButton("Left", 0)
        self.right_button = LuckyStarsButton("Right", 1)

        self.add_item(self.left_button)
        spacer = discord.ui.Button(
            label="", style=discord.ButtonStyle.grey, disabled=True
        )
        self.add_item(spacer)
        self.add_item(self.right_button)

    ###########################################################
    # helpers
    ###########################################################
    def _header(self, action: str | None = None) -> str:
        stats = {
            "active_bet": self.game.bet,
            "stars_current": 0,
            "dealer_action": action or "Pick a card!",
        }
        return make_game_header(self.player, "Lucky Stars", stats)

    def _board_file(
        self, reveal: bool = False, filename: str = "lucky.png"
    ) -> discord.File:
        board = render_lucky_board(self.game, reveal=reveal)
        board.seek(0)
        return discord.File(board, filename)

    async def _disable_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and not child.disabled:
                child.disabled = True
        if self.msg:
            await self.msg.edit(view=self)

    async def _enable_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False
        if self.msg:
            await self.msg.edit(view=self)

    ###########################################################
    # main selection flow
    ###########################################################
    async def handle_pick(self, interaction: discord.Interaction, pos: int):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        await interaction.response.defer()
        msg = self.msg or await interaction.original_response()
        self.msg = msg

        if self.game.picked is not None:
            return

        self.game.pick_card(pos)
        await self._disable_buttons()

        gif, total_seconds = make_slide_animation(
            self.game, duration=90, tail_hold_ms=1200
        )
        gif.seek(0)
        await msg.edit(
            content=self._header("Cards sliding into place..."),
            attachments=[discord.File(gif, f"luckystars_round{self.game.round}.gif")],
            view=self,
        )
        await asyncio.sleep(3)

        result = self.game.resolve_round()
        player_val = result["player_val"]
        dealer_val = result["dealer_val"]
        outcome = result["outcome"]

        summary = f"You got the {player_val}-star card. Dealer had {dealer_val}-star.\n"

        if outcome == "win":
            payout = self.game.bet * 2
            EconomyManager.payout(self.player.id, payout, self.player.name)
            summary += f"  You win {payout} coins!"
        else:
            summary += "  You lose this round."

        await msg.edit(
            content=self._header(summary),
            attachments=[self._board_file(reveal=True)],
            view=None,
        )

        await self._show_replay(summary)

    ###########################################################
    # replay / quit menu
    ###########################################################
    async def _show_replay(self, summary: str):
        if self.on_finish is not None:
            await self.on_finish(self.player.id)

        if not self.msg:
            return

        replay_btn = discord.ui.Button(
            label="Play Again", style=discord.ButtonStyle.green
        )
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(inter: discord.Interaction):
            if inter.user.id != self.player.id:
                await inter.response.send_message("Not your game!", ephemeral=True)
                return
            await inter.response.defer()
            if self.start_game_callback is None:
                await inter.response.send_message(
                    "Unable to start a new game right now.",
                    ephemeral=True,
                )
                return

            async def on_bet_selected(
                inner_inter: discord.Interaction, bet_amount: int
            ):
                await self.start_game_callback(
                    inner_inter,
                    bet_amount,
                    new_game=LuckyStars(bet_amount),
                )

            player_name = getattr(self.player, "display_name", self.player.name)
            wager_view = BetSelectView(
                self.player.id,
                player_name,
                on_bet_selected,
                wager_options=self.wager_options,
            )

            await self.msg.edit(view=wager_view)

        async def quit_cb(inter: discord.Interaction):
            if inter.user.id != self.player.id:
                await inter.response.send_message("Not your game!", ephemeral=True)
                return
            await inter.response.defer()
            await self.msg.edit(
                content=self._header("Thanks for playing Lucky Stars!"), view=None
            )

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

        await self.msg.edit(view=replay_view)


class LuckyStarsButton(discord.ui.Button):
    def __init__(self, label: str, pos: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.pos = pos

    async def callback(self, interaction: discord.Interaction):
        view: LuckyStarsView = self.view  # type: ignore
        await view.handle_pick(interaction, self.pos)


def make_lucky_controls(
    game: LuckyStars,
    player: discord.User,
    on_finish,
    wager_options=None,
    start_game_callback=None,
    message: discord.Message | None = None,
) -> LuckyStarsView:
    return LuckyStarsView(
        game,
        player,
        on_finish,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
        message=message,
    )
