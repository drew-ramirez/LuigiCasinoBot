###########################################################
# File: UIHelpers.py
#
# Description: Shared UI helpers for card grid games
# Provides GridButton and make_controls factory.
###########################################################

import discord

class GridButton(discord.ui.Button):
    def __init__(self, pos: int, cols: int, handler_name: str):
        """
        :param pos: Linear position index (0..N-1)
        :param cols: Number of columns for row calculation
        :param handler_name: Name of the handler function in bot.py
        """
        row = pos // cols
        super().__init__(label=str(pos+1), style=discord.ButtonStyle.secondary, row=row)
        self.pos = pos
        self.handler_name = handler_name

    async def callback(self, interaction: discord.Interaction):
        # Acknowledge immediately to avoid "interaction failed"
        await interaction.response.defer(thinking=False, ephemeral=True)

        # Import bot module dictionary and call the correct handler
        from bot import __dict__ as bot_module
        handler = bot_module.get(self.handler_name)
        if handler:
            await handler(interaction, self.pos)

def make_controls(num_cards: int, cols: int, handler_name: str) -> discord.ui.View:
    """
    Factory to build a grid of GridButtons.

    :param num_cards: Number of buttons to create
    :param cols: Number of columns in the grid
    :param handler_name: Name of handler function in bot.py
    :return: discord.ui.View with the grid of buttons
    """
    view = discord.ui.View(timeout=900)
    for pos in range(num_cards):
        view.add_item(GridButton(pos, cols, handler_name))
    return view
