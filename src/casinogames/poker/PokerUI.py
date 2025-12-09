from __future__ import annotations

import discord
from contextlib import suppress
from collections import Counter

from casinogames.poker.Poker import Poker
from casinogames.poker.PokerPrint import render_text_board
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager


class PokerView(discord.ui.View):
    GAME_KEY = Poker.GAME_KEY

    def __init__(
        self,
        game: Poker,
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
        self.selected_discards: set[int] = set()
        self._add_controls()

    # -------------------------------------------------
    # UI helpers
    # -------------------------------------------------
    def _content(self, status: str = "", hide_dealer: bool = True) -> str:
        board = render_text_board(self.game, hide_dealer=hide_dealer)
        header = f"**{status}**\n" if status else ""
        return f"{header}```\n{board}\n```"

    async def _apply(self, status: str = "", *, hide_dealer: bool = True, view: discord.ui.View | None = None):
        if self.msg is None:
            return
        await self.msg.edit(content=self._content(status, hide_dealer=hide_dealer), view=view or self)

    # -------------------------------------------------
    # Controls
    # -------------------------------------------------
    def _add_controls(self):
        for i in range(5):
            btn = discord.ui.Button(label=f"Card {i+1}", style=discord.ButtonStyle.secondary, row=0, custom_id=f"poker_card_{i}")
            btn.callback = self._make_toggle(i, btn)
            self.add_item(btn)

        submit_btn = discord.ui.Button(label="Submit Discards", style=discord.ButtonStyle.green, row=1)
        submit_btn.callback = self._submit
        stand_btn = discord.ui.Button(label="Stand", style=discord.ButtonStyle.blurple, row=1)
        stand_btn.callback = self._stand
        self.add_item(submit_btn)
        self.add_item(stand_btn)

    def _make_toggle(self, idx: int, btn: discord.ui.Button):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player.id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return
            if idx in self.selected_discards:
                self.selected_discards.remove(idx)
                btn.style = discord.ButtonStyle.secondary
            else:
                self.selected_discards.add(idx)
                btn.style = discord.ButtonStyle.danger
            try:
                await interaction.response.edit_message(view=self)
            except discord.InteractionResponded:
                with suppress(Exception):
                    await interaction.edit_original_response(view=self)
        return callback

    # -------------------------------------------------
    # Actions
    # -------------------------------------------------
    async def _submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()

        if not self.selected_discards:
            await self._apply("No cards selected to discard.")
            return

        self.game.player_discard(sorted(self.selected_discards))
        self.selected_discards.clear()
        await self._apply("Your redraw is complete. Press Stand to resolve.")

        # disable further discards
        for child in self.children:
            if isinstance(child, discord.ui.Button) and "Card" in child.label:
                child.disabled = True

    async def _stand(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()

        # Dealer auto-discards before resolve
        self.game.dealer_discard()
        result = self.game.resolve_round()

        # Payout
        payout = int(result.get("payout", 0))
        EconomyManager.payout(self.player.id, payout, self.player.name)

        outcome = result.get("outcome", "push")
        summary_map = {
            "win": f"You win! (+{payout})",
            "lose": "Dealer wins.",
            "push": f"Push. ({payout} returned)",
        }
        summary = summary_map.get(outcome, "Round over.")

        session_id = getattr(self.game, "metrics_session_id", None)
        if not getattr(self.game, "metrics_logged", False):
            MetricsManager.record_game_result(
                session_id,
                result=outcome,
                payout=payout,
                net=int(result.get("net", 0)),
                metadata={
                    "player_rank": result.get("player_rank"),
                    "dealer_rank": result.get("dealer_rank"),
                },
            )
            setattr(self.game, "metrics_logged", True)

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await self._apply(summary, hide_dealer=False, view=None)

        if self.on_finish is not None:
            await self.on_finish(self.player.id)

        await self._show_replay()

    # -------------------------------------------------
    # Replay
    # -------------------------------------------------
    async def _show_replay(self):
        if self.start_game_callback is None or self.msg is None:
            return

        replay_btn = discord.ui.Button(label="Play Again", style=discord.ButtonStyle.green)
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.player.id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()

            def make_wager_callback():
                async def on_bet_selected(inner_inter: discord.Interaction, bet_amount: int):
                    new_game = Poker(bet_amount)
                    await self.start_game_callback(inner_inter, bet_amount, new_game=new_game)
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


def make_cleanup_renderer(view: PokerView):
    def renderer(status: str, colour=None):
        return {"content": view._content(status, hide_dealer=False), "embed": None, "attachments": []}
    return renderer
