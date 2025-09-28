import discord
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image
from casinogames.core.UIHelpers import make_controls

# Button Factory: generate full grid of buttons for current board state
def make_flip_controls(num_cards: int) -> discord.ui.View:
    # MemoryMatch always has 4 columns and uses "handle_memory_flip"
    return make_controls(num_cards, 4, "handle_memory_flip")

# Update the view when cards are matched
async def update_controls_for_match(view: discord.ui.View, positions: list[int], message: discord.Message):
    for child in view.children:
        # GridButton comes from UIHelpers, but still has .pos
        if hasattr(child, "pos") and child.pos in positions:
            child.label = "✅"
            child.disabled = True

    # push update to Discord
    await message.edit(view=view)

# Update the view when cards are unmatched (reset to numbers)
async def update_controls_for_unmatch(view: discord.ui.View, positions: list[int], message: discord.Message):
    for child in view.children:
        if hasattr(child, "pos") and child.pos in positions:
            child.label = str(child.pos + 1)
            child.disabled = False
    # push update to Discord
    await message.edit(view=view)