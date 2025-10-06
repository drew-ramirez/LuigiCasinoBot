###########################################################
# File: ui_embeds.py
#
# Description: Luigi’s Casino header
###########################################################

from economy.EconomyManager import EconomyManager

BAR_WIDTH = 25 # total width of the header bar

def make_game_header(user, game_name: str, stats: dict):
    # pull live balance
    record = EconomyManager.ensure_user(user.id, user.name)
    balance = record.get("balance", 0)

    # extract stats from game
    active_bet = stats.get("active_bet", 0)
    stars_current = stats.get("stars_current", 0)
    dealer_action = stats.get("dealer_action")
    round_summary = stats.get("round_summary")

    # Borders and dividers
    top_border = "╔" + "═" * BAR_WIDTH + "╗"
    bottom_border = "╚" + "═" * BAR_WIDTH + "╝"
    divider = " " + "═" * BAR_WIDTH + " "

    # Header lines
    title = f"🎰 Luigi’s Casino — {game_name}"
    line1 = f"💰 Balance: {balance:,}   💎 Bet: {active_bet}   ⭐ Stars: {stars_current}"

    # dealer text or round summary
    footer = round_summary or dealer_action or ""

    # message builder
    content = "\n".join([
        top_border,
        f"  {title}",
        divider,
        f"  {line1}",
        divider,
        f"  {footer}" if footer else "",
        bottom_border,
    ])

    return content.strip()
