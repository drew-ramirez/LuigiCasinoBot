import discord
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image

# Individual flip button
class FlipButton(discord.ui.Button):
    def __init__(self, pos: int):
        row = pos // 4  # 4 buttons per row
        super().__init__(
            label=str(pos + 1),
            style=discord.ButtonStyle.secondary,
            row=row
        )
        self.pos = pos

    async def callback(self, interaction: discord.Interaction):
        # Acknowledge the button press immediately (avoids "interaction failed")
        await interaction.response.defer(thinking=False, ephemeral=True)

        # Call the shared flip handler
        from bot import handle_memory_flip  # import the helper from bot.py
        await handle_memory_flip(interaction, self.pos)
    
    def mark_matched(self):
            # turn into ✅ and disable it
            self.label = "✅"
            self.disabled = True

    def reset_to_number(self):
        # Restore to its number and re-enable
        self.label = str(self.pos + 1)
        self.disabled = False

# Button Factory: generate full grid of buttons for current board state
def make_flip_controls(num_cards: int) -> discord.ui.View:
    view = discord.ui.View(timeout=900)
    for pos in range(num_cards):
        view.add_item(FlipButton(pos))
    return view

# Update the view when cards are matched
async def update_controls_for_match(view: discord.ui.View, positions: list[int], message: discord.Message):
    for child in view.children:
        if isinstance(child, FlipButton) and child.pos in positions:
            child.mark_matched()

    # push update to Discord
    await message.edit(view=view)

# Update the view when cards are unmatched (reset to numbers)
async def update_controls_for_unmatch(view: discord.ui.View, positions: list[int], message: discord.Message):
    for child in view.children:
        if isinstance(child, FlipButton) and child.pos in positions:
            child.reset_to_number()
    # push update to Discord
    await message.edit(view=view)