###########################################################
# File: ui_embeds.py
#
# Description: Luigi's Casino UI header utilities.
###########################################################

from typing import List, Optional
from economy.EconomyManager import EconomyManager

BAR_WIDTH = 25  # total width of the header bar
TOP_BORDER = "╔" + "═" * BAR_WIDTH + "╗"
BOTTOM_BORDER = "╚" + "═" * BAR_WIDTH + "╝"
DIVIDER = " " + "═" * BAR_WIDTH + " "


def _compose_message(lines: List[str]) -> str:
    # Build a bordered message with standard casino styling
    if not lines:
        return "\n".join([TOP_BORDER, BOTTOM_BORDER])

    message: List[str] = [TOP_BORDER, f"  {lines[0]}"]

    for line in lines[1:]:
        message.append(DIVIDER)
        if line:
            message.append(f"  {line}")

    message.append(BOTTOM_BORDER)
    return "\n".join(message)


def make_game_header(user, game_name: str, stats: dict) -> str:
    """Render the standard in-game header with live balance and stats."""
    record = EconomyManager.ensure_user(user.id, user.name)
    balance = record.get("balance", 0)

    active_bet = stats.get("active_bet", 0)
    stars_current = stats.get("stars_current", 0)
    dealer_action = stats.get("dealer_action")
    round_summary = stats.get("round_summary")

    title = f"🎰 Luigi’s Casino — {game_name}"
    line1 = f"💰 Balance: {balance:,}   💎 Bet: {active_bet}   ⭐ Stars: {stars_current}"
    footer = round_summary or dealer_action

    lines = [title, line1]
    if footer:
        lines.append(str(footer))

    return _compose_message(lines)


def make_pregame_banner(
    game_name: str,
    balance: int,
    *,
    prompt: Optional[str] = None,
) -> str:
    """Render the common wager selection banner shown before each game."""
    call_to_action = prompt or "Select your wager amount to begin:"

    lines = [
        f"🎰 Luigi’s Casino — {game_name}",
        f"💰 Balance: {balance:,} coins",
        call_to_action,
    ]

    return _compose_message(lines)