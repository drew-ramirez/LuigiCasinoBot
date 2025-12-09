from __future__ import annotations
import discord
from casinogames.blackjack.Blackjack import Blackjack
from casinogames.blackjack.BlackjackPrint import render_text_board
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager


class BlackjackView(discord.ui.View):
    GAME_KEY = Blackjack.GAME_KEY

    def __init__(
        self,
        game: Blackjack,
        player: discord.abc.User,
        on_finish,
        *,
        start_game_callback=None,
        wager_options=None,
        message: discord.Message | None = None,
    ):
        super().__init__(timeout=None)
        self.game = game
        self.player = player
        self.on_finish = on_finish
        self.start_game_callback = start_game_callback
        self.wager_options = wager_options or list(DEFAULT_WAGER_OPTIONS)
        self.msg = message
        self._add_controls()

    def _board_content(self, status: str = "") -> str:
        board = render_text_board(self.game, hide_dealer_hole=not self.game.finished)
        header = f"**{status}**\n" if status else ""
        return f"{header}```\n{board}\n```"

    async def _apply(self, status: str = "", *, view: discord.ui.View | None = None):
        if self.msg is None:
            return
        await self.msg.edit(content=self._board_content(status), view=view or self)

    def _add_controls(self):
        for label, style, cb in (
            ("Hit", discord.ButtonStyle.green, self._handle_hit),
            ("Stand", discord.ButtonStyle.blurple, self._handle_stand),
            ("Double", discord.ButtonStyle.gray, self._handle_double),
        ):
            btn = discord.ui.Button(label=label, style=style)
            btn.callback = cb
            self.add_item(btn)

    async def _handle_hit(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        await self._finish_or_update(self.game.hit())

    async def _handle_stand(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        await self._finish_or_update(self.game.stand())

    async def _handle_double(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        if not EconomyManager.wager(
            self.player.id, self.game.base_bet, self.player.name
        ):
            await interaction.followup.send(
                "Insufficient balance to double down.", ephemeral=True
            )
            return
        await self._finish_or_update(self.game.double_down())

    async def _finish_or_update(self, result: dict):
        if self.game.finished:
            await self._finalize(result)
        else:
            await self._apply("Your move...")

    async def _finalize(self, result: dict):
        payout = int(result.get("payout", 0))
        EconomyManager.payout(self.player.id, payout, self.player.name)
        outcome = result.get("outcome", "push")
        summary = {
            "win": f"You win! (+{payout})",
            "blackjack": f"Blackjack! (+{payout})",
            "push": f"Push. ({payout} returned)",
            "lose": "Dealer wins.",
            "bust": "You busted.",
        }.get(outcome, "Round over.")
        session_id = getattr(self.game, "metrics_session_id", None)
        if not getattr(self.game, "metrics_logged", False):
            MetricsManager.record_game_result(
                session_id,
                result=outcome,
                payout=payout,
                net=int(result.get("net", 0)),
                metadata={
                    "player_total": result.get("player_total"),
                    "dealer_total": result.get("dealer_total"),
                    "doubled": bool(getattr(self.game, "doubled", False)),
                },
            )
            setattr(self.game, "metrics_logged", True)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self._apply(summary, view=self)
        if self.on_finish is not None:
            await self.on_finish(self.player.id)
        await self._show_replay()

    async def _show_replay(self):
        if self.start_game_callback is None or self.msg is None:
            return
        replay_btn = discord.ui.Button(
            label="Play Again", style=discord.ButtonStyle.green
        )
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()

            def make_wager_callback():
                async def on_bet_selected(
                    inner_inter: discord.Interaction, bet_amount: int
                ):
                    new_game = Blackjack(bet_amount)
                    await self.start_game_callback(
                        inner_inter, bet_amount, new_game=new_game
                    )

                return on_bet_selected

            wager_view = BetSelectView(
                self.player.id,
                self.player.name,
                make_wager_callback(),
                wager_options=self.wager_options,
            )
            await btn_inter.edit_original_response(view=wager_view, content=None)

        async def quit_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            await btn_inter.edit_original_response(view=None)

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb
        view = discord.ui.View()
        view.add_item(replay_btn)
        view.add_item(quit_btn)
        await self.msg.edit(view=view)


def make_cleanup_renderer(view: BlackjackView):
    def renderer(status: str, colour=None):
        return {
            "content": view._board_content(status),
            "embed": None,
            "attachments": [],
        }

    return renderer


def make_blackjack_view(
    game: Blackjack,
    player: discord.abc.User,
    on_finish,
    *,
    start_game_callback=None,
    wager_options=None,
    message: discord.Message | None = None,
) -> BlackjackView:
    return BlackjackView(
        game,
        player,
        on_finish,
        start_game_callback=start_game_callback,
        wager_options=wager_options,
        message=message,
    )
