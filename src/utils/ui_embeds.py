###########################################################
# File: ui_embeds.py
#
# Description: Luigi's Casino UI header utilities.
###########################################################

from typing import List, Optional

import discord

from economy.EconomyManager import EconomyManager
from utils.emoji_config import get_coin_emoji, get_star_emoji

# ##########################################################
# Static embed helpers - no animations
# ##########################################################

EMBED_COLOR = discord.Color.from_rgb(24, 131, 62)  # Luigi green
COIN_EMOJI = get_coin_emoji()
BET_EMOJI = "💎"
STAR_EMOJI = get_star_emoji()


def _format_number(amount: int) -> str:
    return f"{amount:,}"


def make_game_header(user, game_name: str, stats: dict) -> discord.Embed:
    """Render the embed-based header with live balance and stats."""
    record = EconomyManager.ensure_user(user.id, user.name)
    balance = record.get("balance", 0)

    active_bet = stats.get("active_bet", 0)
    stars_current = stats.get("stars_current", 0)
    dealer_action = stats.get("dealer_action")
    round_summary = stats.get("round_summary")

    embed = discord.Embed(
        title=f"🎰 Luigi's Casino – {game_name}",
        color=EMBED_COLOR,
    )
    if getattr(user, "display_avatar", None):
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)
    else:
        embed.set_author(name=user.display_name)

    embed.add_field(
        name="Balance",
        value=f"{COIN_EMOJI} {_format_number(balance)}",
        inline=True,
    )
    embed.add_field(
        name="Bet", value=f"{BET_EMOJI} {_format_number(active_bet)}", inline=True
    )
    embed.add_field(name="Stars", value=f"{STAR_EMOJI} {stars_current}", inline=True)

    footer_text = round_summary or dealer_action
    if footer_text:
        embed.add_field(name="Game Status", value=str(footer_text), inline=False)

    embed.set_footer(text="Luigi's Casino")
    return embed


def make_pregame_banner(
    game_name: str,
    balance: int,
    *,
    prompt: Optional[str] = None,
) -> discord.Embed:
    """Render the embed used during wager selection."""
    call_to_action = prompt or "Select your wager amount to begin:"
    embed = discord.Embed(
        title=f"🎰 Luigi's Casino – {game_name}",
        description=call_to_action,
        color=EMBED_COLOR,
    )
    embed.add_field(
        name="Balance",
        value=f"{COIN_EMOJI} {_format_number(balance)} coins",
        inline=False,
    )
    embed.set_footer(text="Luigi's Casino")
    return embed


# ##########################################################
# Animated/gif board helpers - gif board layout
# ##########################################################

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


def make_gif_game_header(user, game_name: str, stats: dict) -> str:
    """Render the classic ASCII header used alongside gif boards."""
    record = EconomyManager.ensure_user(user.id, user.name)
    balance = record.get("balance", 0)

    active_bet = stats.get("active_bet", 0)
    stars_current = stats.get("stars_current", 0)
    dealer_action = stats.get("dealer_action")
    round_summary = stats.get("round_summary")

    title = f"🎰 Luigi’s Casino - {game_name}"
    line1 = (
        f"{COIN_EMOJI} Balance: {balance:,}   "
        f"{BET_EMOJI} Bet: {active_bet}   "
        f"{STAR_EMOJI} Stars: {stars_current}"
    )
    footer = round_summary or dealer_action

    lines = [title, line1]
    if footer:
        lines.append(str(footer))

    return _compose_message(lines)


def make_gif_pregame_banner(
    game_name: str,
    balance: int,
    *,
    prompt: Optional[str] = None,
) -> str:
    """Render the wager selection banner for the gif/animated layout."""
    call_to_action = prompt or "Select your wager amount to begin:"

    lines = [
        f"🎰 Luigi’s Casino - {game_name}",
        f"{COIN_EMOJI} Balance: {balance:,} coins",
        call_to_action,
    ]

    return _compose_message(lines)
