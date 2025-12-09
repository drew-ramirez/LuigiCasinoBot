#########################################################################
# File: casino_config.py
#
# Description: Guild-level configuration helpers for Luigi's Casino.
#              Stores and resolves channel/category visibility settings.
########################################################################

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

import discord

from economy.EconomyManager import db

# Keys for casino games where we always keep responses private unless a specific
# public channel is mapped. (FOR ANY NEW GAMES): Update this set so visibility
# logic stays aligned with the command registery from discord
DEFAULT_GAME_COMMAND_KEYS: set[str] = {
    "memorymatch",
    "pairagone",
    "luckystars",
    "picturepoker",
    "blackjack",
}


@dataclass
class GuildCasinoConfig:
    guild_id: int
    allowed_channels: set[int] = field(default_factory=set)
    channel_map: dict[str, int] = field(default_factory=dict)
    category_id: Optional[int] = None
    visibility_mode: str = "public"  # future expansion: "private" or others
    manager_role_ids: set[int] = field(default_factory=set)
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def all_public_channels(self) -> set[int]:
        combined = set(self.allowed_channels)
        combined.update(self.channel_map.values())
        return combined


@dataclass
class VisibilityDecision:
    is_public: bool
    home_channel_id: Optional[int]
    config: GuildCasinoConfig


class CasinoConfigManager:
    COLLECTION = db["casino_guild_config"]
    _cache: dict[int, GuildCasinoConfig] = {}

    @classmethod
    def _deserialize(cls, raw: dict) -> GuildCasinoConfig:
        if not raw:
            raise ValueError("Cannot deserialize empty guild config")

        allowed = set(raw.get("allowed_channels", []))
        channel_map = {
            key: int(value)
            for key, value in (raw.get("channel_map") or {}).items()
            if isinstance(value, (int, float, str)) and str(value).isdigit()
        }
        category_id = raw.get("category_id")
        if isinstance(category_id, (int, float, str)) and str(category_id).isdigit():
            category_id = int(category_id)
        else:
            category_id = None

        visibility_mode = raw.get("visibility_mode", "public") or "public"
        manager_role_ids = {
            int(role_id)
            for role_id in raw.get("manager_role_ids", [])
            if str(role_id).isdigit()
        }
        updated_at = raw.get("updated_at")
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at)
            except ValueError:
                updated_at = datetime.now(timezone.utc)
        elif not isinstance(updated_at, datetime):
            updated_at = datetime.now(timezone.utc)

        return GuildCasinoConfig(
            guild_id=int(raw["guild_id"]),
            allowed_channels=allowed,
            channel_map=channel_map,
            category_id=category_id,
            visibility_mode=visibility_mode,
            manager_role_ids=manager_role_ids,
            updated_at=updated_at,
        )

    @classmethod
    def _serialize(cls, config: GuildCasinoConfig) -> dict:
        return {
            "guild_id": config.guild_id,
            "allowed_channels": list(config.allowed_channels),
            "channel_map": {k: int(v) for k, v in config.channel_map.items()},
            "category_id": config.category_id,
            "visibility_mode": config.visibility_mode,
            "manager_role_ids": list(config.manager_role_ids),
            "updated_at": datetime.now(timezone.utc),
        }

    @classmethod
    def get_config(
        cls,
        guild_id: int,
        *,
        fallback_channels: Optional[Iterable[int]] = None,
    ) -> GuildCasinoConfig:
        if guild_id in cls._cache:
            return cls._cache[guild_id]

        raw = cls.COLLECTION.find_one({"guild_id": int(guild_id)})
        if raw:
            config = cls._deserialize(raw)
        else:
            config = GuildCasinoConfig(
                guild_id=int(guild_id),
                allowed_channels=set(int(x) for x in fallback_channels or []),
            )
            cls._cache[guild_id] = config
            return config

        cls._cache[guild_id] = config
        return config

    @classmethod
    def update_config(cls, config: GuildCasinoConfig) -> GuildCasinoConfig:
        payload = cls._serialize(config)
        cls.COLLECTION.update_one(
            {"guild_id": config.guild_id},
            {"$set": payload},
            upsert=True,
        )
        config.updated_at = payload["updated_at"]
        cls._cache[config.guild_id] = config
        return config

    # Mutators ---------------------------------------------------------------
    @classmethod
    def set_category(cls, guild_id: int, category_id: Optional[int]) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.category_id = category_id
        return cls.update_config(config)

    @classmethod
    def set_visibility_mode(cls, guild_id: int, mode: str) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.visibility_mode = mode
        return cls.update_config(config)

    @classmethod
    def set_allowed_channels(
        cls, guild_id: int, channel_ids: Iterable[int]
    ) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.allowed_channels = {int(ch) for ch in channel_ids}
        return cls.update_config(config)

    @classmethod
    def add_allowed_channel(cls, guild_id: int, channel_id: int) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.allowed_channels.add(int(channel_id))
        return cls.update_config(config)

    @classmethod
    def remove_allowed_channel(cls, guild_id: int, channel_id: int) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.allowed_channels.discard(int(channel_id))
        return cls.update_config(config)

    @classmethod
    def set_channel_map(
        cls,
        guild_id: int,
        *,
        command_key: str,
        channel_id: Optional[int],
    ) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        if channel_id is None:
            config.channel_map.pop(command_key, None)
        else:
            config.channel_map[command_key] = int(channel_id)
        return cls.update_config(config)

    @classmethod
    def add_manager_role(cls, guild_id: int, role_id: int) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.manager_role_ids.add(int(role_id))
        return cls.update_config(config)

    @classmethod
    def remove_manager_role(cls, guild_id: int, role_id: int) -> GuildCasinoConfig:
        config = cls.get_config(guild_id)
        config.manager_role_ids.discard(int(role_id))
        return cls.update_config(config)

    @classmethod
    def clear_cache(cls, guild_id: Optional[int] = None) -> None:
        if guild_id is None:
            cls._cache.clear()
        else:
            cls._cache.pop(int(guild_id), None)

    @classmethod
    def user_has_manager_access(cls, member: discord.Member) -> bool:
        if member.guild_permissions.manage_guild:
            return True
        config = cls.get_config(member.guild.id)
        member_role_ids = {role.id for role in member.roles}
        return bool(config.manager_role_ids.intersection(member_role_ids))

    # Visibility resolution -------------------------------------------------
    @classmethod
    def resolve_visibility(
        cls,
        *,
        guild_id: int,
        channel_id: Optional[int],
        command_key: Optional[str],
        fallback_channels: Optional[Iterable[int]] = None,
    ) -> VisibilityDecision:
        config = cls.get_config(guild_id, fallback_channels=fallback_channels)
        if channel_id is None:
            return VisibilityDecision(
                is_public=False,
                home_channel_id=None,
                config=config,
            )

        home_channel = None
        if command_key:
            home_channel = config.channel_map.get(command_key)

        normalized_channel_id = int(channel_id)
        is_allowed_channel = normalized_channel_id in config.allowed_channels

        normalized_command_key = command_key.lower() if isinstance(command_key, str) else None

        # game commands remain private (unless they have a home channel),
        # while generic utility commands can surface publicly in casino floor channels.
        is_game_command = False
        if normalized_command_key:
            channel_map_keys = {key.lower() for key in config.channel_map}
            if normalized_command_key in channel_map_keys:
                is_game_command = True
            elif normalized_command_key in DEFAULT_GAME_COMMAND_KEYS:
                is_game_command = True

        if home_channel is not None:
            is_public = normalized_channel_id == home_channel
        elif not is_game_command:
            is_public = is_allowed_channel
        else:
            is_public = False

        return VisibilityDecision(
            is_public=is_public,
            home_channel_id=home_channel,
            config=config,
        )
