###########################################################
# File: settings.py
#
# Description: Shared configuration helpers for Luigi's Casino bot.
###########################################################

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def fallback_allowed_channels() -> set[int]:
    channels_env = os.getenv("CASINO_CHANNEL_IDS")
    if channels_env:
        return {
            int(v.strip()) for v in channels_env.split(",") if v.strip().isdigit()
        }
    single_channel = os.getenv("CASINO_CHANNEL_ID", "")
    if single_channel and single_channel.isdigit():
        return {int(single_channel)}
    return set()


@lru_cache(maxsize=1)
def dev_user_ids() -> set[int]:
    raw = os.getenv("DEV_USER_IDS", "")
    if not raw:
        return set()
    ids: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(int(chunk))
    return ids
