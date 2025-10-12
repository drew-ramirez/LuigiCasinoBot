###########################################################
# File: emoji_config.py
#
# Description: Centralized emoji helpers for Luigi's Casino.
###########################################################

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Dict, Optional

import discord


# Defaults used across embeds if no override is provided.
DEFAULT_UI_EMOJIS: Dict[str, str] = {
    "coin": "💰",
    "cashout": "💸",
    "star": "🌟",
}

# Picture Poker specific defaults (best -> worst order).
DEFAULT_PICTURE_POKER_EMOJIS: Dict[str, str] = {
    "cloud": "☁️",
    "mushroom": "🍄",
    "flower": "🌸",
    "luigi": "🟩",
    "mario": "🟥",
    "star": "⭐",
}


def _load_json_overrides(raw: str) -> Dict[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("[WARN] CASINO_POKER_EMOJIS is not valid JSON; ignoring.")
        return {}

    if not isinstance(data, dict):
        return {}

    normalized: Dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized[key.lower()] = value
    return normalized


@lru_cache(maxsize=1)
def picture_poker_emojis() -> Dict[str, str]:
    """Return defaults merged with JSON overrides (cached)."""
    merged: Dict[str, str] = dict(DEFAULT_PICTURE_POKER_EMOJIS)
    raw = os.getenv("CASINO_POKER_EMOJIS", "").strip()
    if raw:
        overrides = _load_json_overrides(raw)
        for key, value in overrides.items():
            if key in merged:
                merged[key] = value
    return merged


def get_coin_emoji() -> str:
    return os.getenv("CASINO_COIN_EMOJI", DEFAULT_UI_EMOJIS["coin"])


def get_cashout_emoji() -> str:
    return os.getenv("CASINO_CASHOUT_EMOJI", DEFAULT_UI_EMOJIS["cashout"])


def get_star_emoji() -> str:
    return picture_poker_emojis().get("star", DEFAULT_UI_EMOJIS["star"])


CUSTOM_EMOJI_RE = re.compile(r"<(a?):([a-zA-Z0-9_]+):([0-9]+)>$")


def _component_emoji(raw: Optional[str]) -> Optional[discord.PartialEmoji | str]:
    if not raw:
        return None
    match = CUSTOM_EMOJI_RE.fullmatch(raw.strip())
    if match:
        animated = bool(match.group(1))
        name = match.group(2)
        emoji_id = int(match.group(3))
        return discord.PartialEmoji(name=name, id=emoji_id, animated=animated)
    return raw


def get_coin_component_emoji() -> Optional[discord.PartialEmoji | str]:
    return _component_emoji(get_coin_emoji())


def get_cashout_component_emoji() -> Optional[discord.PartialEmoji | str]:
    return _component_emoji(get_cashout_emoji())


def get_star_component_emoji() -> Optional[discord.PartialEmoji | str]:
    return _component_emoji(get_star_emoji())
