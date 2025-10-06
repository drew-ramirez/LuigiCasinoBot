###########################################################
# File: bet_selector.py
#
# Description: Universal bet selection UI for all Luigi's Casino games.
# Handles wager validation, deduction, and callback to start game logic.
###########################################################

import discord
from economy.EconomyManager import EconomyManager


class BetSelectView(discord.ui.View):
    #Reusable wager selection view for casino games.

    def __init__(
        self,
        user_id: int,
        username: str,
        on_bet_selected,
        min_bet: int = 1,
        max_bet: int = 5,
        wager_options: list[int] | None = None,
    ):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.username = username
        self.on_bet_selected = on_bet_selected

        amounts: list[int] = []
        if wager_options:
            for value in wager_options:
                try:
                    amount = int(value)
                except (TypeError, ValueError):
                    continue
                if amount <= 0 or amount in amounts:
                    continue
                amounts.append(amount)
        else:
            amounts = list(range(min_bet, max_bet + 1))

        if not amounts:
            amounts = [min_bet]

        for idx, amount in enumerate(amounts):
            button = discord.ui.Button(
                label=f"Bet {amount}",
                style=discord.ButtonStyle.green,
                custom_id=f"bet_{amount}",
                row=idx // 5,
            )
            button.callback = self._make_bet_callback(amount)
            self.add_item(button)

    def _make_bet_callback(self, amount: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return

            balance = EconomyManager.balance(self.user_id, self.username)
            if balance < amount:
                await interaction.response.send_message(
                    f"You do not have enough coins to bet {amount}. (Balance {balance:,})",
                    ephemeral=True,
                )
                return

            if not EconomyManager.wager(self.user_id, amount, self.username):
                await interaction.response.send_message(
                    "Could not place that wager right now. Please try again.",
                    ephemeral=True,
                )
                return

            await self.on_bet_selected(interaction, amount)

        return callback