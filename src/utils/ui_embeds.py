###########################################################
# File: ui_embeds.py
#
# Description: Discord-safe header (manually hard-aligned)
#              Stats evenly spaced to match title width.
###########################################################

import discord
from economy.EconomyManager import EconomyManager


def make_game_header(
    user,
    game_name: str,
    active_bet: int = 0,
    stars_current: int = 0,
    stars_goal: int = 0,
    win_streak: int = 0,
    multiplier: float = 1.0,
    dealer_action: str = None,
    round_summary: str = None,
):
    from economy.EconomyManager import EconomyManager

    # pull live balance
    record = EconomyManager.ensure_user(user.id, user.name)
    balance = record.get("balance", 0)
    star_text = f"{stars_current}" if not stars_goal else f"{stars_current}/{stars_goal}"

    ###########################################################
    # base lines
    ###########################################################
    title = f"🎰 **Luigi’s Casino — {game_name}**"
    line1 = f"💰 **Balance:** {balance:,}  🎯 **Bet:** {active_bet}"
    line2 = f"⭐ **Stars:** {star_text}  🔥 **Win Streak:** {win_streak}  🎯 **x{multiplier:.1f}**"

    # dynamic final line
    if round_summary:
        line3 = round_summary
    elif dealer_action:
        line3 = dealer_action
    else:
        line3 = f"Waiting for **{user.display_name}**..."

    ###########################################################
    # combine with consistent spacing
    ###########################################################
    content = "\n".join(
        [
            "╭───────────────────────────────────────────╮",
            "               "+title,
            "    ────────────────────────────────────────────",
            "               "+line1,
            "         "+line2,
            "    ────────────────────────────────────────────",
             "         "+line3,
            "╰───────────────────────────────────────────╯",
        ]
    )

    return content