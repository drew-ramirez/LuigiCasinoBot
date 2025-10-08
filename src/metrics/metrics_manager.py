###########################################################
# File: metrics_manager.py
#
# Description: Simple helpers for recording lightweight
#              engagement metrics (command volume, game starts)
#              into MongoDB so we can run aggregations later.
###########################################################

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from economy.EconomyManager import db

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    import discord  # type: ignore


class MetricsManager:
    """Static helpers for recording engagement metrics."""

    COMMAND_COLLECTION = db["metrics_command_events"]
    GAME_COLLECTION = db["metrics_game_events"]

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _safe_id(target: Any) -> Optional[int]:
        return getattr(target, "id", None) if target is not None else None

    @classmethod
    def record_command_event(
        cls,
        interaction: "discord.Interaction",
        command_name: str,
        *,
        game_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist a single slash-command invocation."""
        doc: Dict[str, Any] = {
            "command": command_name,
            "user_id": cls._safe_id(getattr(interaction, "user", None)),
            "guild_id": cls._safe_id(getattr(interaction, "guild", None)),
            "channel_id": cls._safe_id(getattr(interaction, "channel", None)),
            "timestamp": cls._utcnow(),
        }
        if game_key:
            doc["game_key"] = game_key
        if metadata:
            doc["metadata"] = metadata

        try:
            cls.COMMAND_COLLECTION.insert_one(doc)
        except Exception as exc:  # pragma: no cover - logging should not break gameplay
            print(f"[WARN] MetricsManager command insert failed: {exc}")

    @classmethod
    def record_game_start(
        cls,
        interaction: "discord.Interaction",
        game_key: str,
        *,
        bet_amount: Optional[int] = None,
        source_command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log that a user has started a new game session."""
        doc: Dict[str, Any] = {
            "game_key": game_key,
            "user_id": cls._safe_id(getattr(interaction, "user", None)),
            "guild_id": cls._safe_id(getattr(interaction, "guild", None)),
            "channel_id": cls._safe_id(getattr(interaction, "channel", None)),
            "timestamp": cls._utcnow(),
        }
        if bet_amount is not None:
            doc["bet_amount"] = int(bet_amount)
        if source_command:
            doc["command"] = source_command
        if metadata:
            doc["metadata"] = metadata

        try:
            cls.GAME_COLLECTION.insert_one(doc)
        except Exception as exc:  # pragma: no cover - logging should not break gameplay
            print(f"[WARN] MetricsManager game insert failed: {exc}")

