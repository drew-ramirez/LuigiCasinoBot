###########################################################
# File: PicturePokerUI.py
#
# Description: Discord UI controls for Picture Poker
###########################################################

import discord
from discord.ui import View, Button

poker_games = {}
poker_messages = {}
poker_views = {}


class PokerControls(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.selected_discards = set()

        for i in range(5):
            btn = Button(
                label=f"Card {i+1}",
                style=discord.ButtonStyle.secondary,
                row=0,
                custom_id=f"card_{i}",
            )
            btn.callback = self._make_toggle(i, btn)
            self.add_item(btn)

        submit_btn = Button(
            label="submit discards",
            style=discord.ButtonStyle.green,
            row=1,
            custom_id="submit_discards",
        )
        submit_btn.callback = self._submit
        self.add_item(submit_btn)

        stand_btn = Button(
            label="stand",
            style=discord.ButtonStyle.blurple,
            row=1,
            custom_id="stand",
        )
        stand_btn.callback = self._stand
        self.add_item(stand_btn)

    def _make_toggle(self, idx: int, btn: Button):
        async def callback(interaction: discord.Interaction):
            if idx in self.selected_discards:
                self.selected_discards.remove(idx)
                btn.style = discord.ButtonStyle.secondary
            else:
                self.selected_discards.add(idx)
                btn.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(view=self)

        return callback

    async def _submit(self, interaction: discord.Interaction):
        from bot import handle_poker_discard

        await handle_poker_discard(
            interaction, self.user_id, list(self.selected_discards)
        )
        self.selected_discards.clear()

    async def _stand(self, interaction: discord.Interaction):
        from bot import handle_poker_stand

        await handle_poker_stand(interaction, self.user_id)


def make_poker_controls(user_id: int) -> PokerControls:
    return PokerControls(user_id)
