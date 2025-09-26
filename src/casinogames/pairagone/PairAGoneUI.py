###########################################################
# File: PairAGoneUI.py
#
# Description: Discord UI controls for Pair-a-Gone
###########################################################

import discord
from casinogames.core.UIHelpers import make_controls

def make_pair_controls(num_cards: int, cols: int) -> discord.ui.View:
    # Pair-a-Gone uses "handle_pair_flip" in bot.py
    return make_controls(num_cards, cols, "handle_pair_flip")
