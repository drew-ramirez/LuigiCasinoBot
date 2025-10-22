###########################################################
# File: metrics_manager.py
#
# Description: Helpers for logging engagement metrics and for
#              materializing daily rollups used by dashboards.
###########################################################

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from economy.EconomyManager import db

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    import discord  # type: ignore


class MetricsManager:
    """Static helpers for recording engagement metrics."""

    COMMAND_COLLECTION = db["metrics_command_events"]
    GAME_COLLECTION = db["metrics_game_events"]
    USERS_COLLECTION = db["users"]

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _safe_id(target: Any) -> Optional[int]:
        return getattr(target, "id", None) if target is not None else None

    @staticmethod
    def _normalize_id(value: Any) -> Any:
        if isinstance(value, str):
            try:
                from bson import ObjectId  # type: ignore

                return ObjectId(value)
            except Exception:
                return value
        return value

    @staticmethod
    async def _run_async(callable_: Callable[[], None]) -> None:
        await asyncio.to_thread(callable_)

    @classmethod
    def _dispatch_write(
        cls,
        callback: Callable[[], None],
        label: str,
        *,
        immediate: bool = False,
    ) -> None:
        """Execute Mongo writes without blocking the event loop."""
        def guarded() -> None:
            try:
                callback()
            except Exception as exc:  # pragma: no cover - logging should not break gameplay
                print(f"[WARN] {label} failed: {exc}")

        if immediate:
            guarded()
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            guarded()
            return

        loop.create_task(cls._run_async(guarded))

    @classmethod
    def _command_doc(
        cls,
        interaction: "discord.Interaction",
        command_name: str,
        *,
        game_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        return doc

    @classmethod
    def record_command_event(
        cls,
        interaction: "discord.Interaction",
        command_name: str,
        *,
        game_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        immediate: bool = False,
    ) -> None:
        """Persist a single slash-command invocation."""
        doc = cls._command_doc(
            interaction,
            command_name,
            game_key=game_key,
            metadata=metadata,
        )
        cls._dispatch_write(
            lambda: cls.COMMAND_COLLECTION.insert_one(doc),
            "MetricsManager command insert",
            immediate=immediate,
        )

    @classmethod
    async def record_command_event_async(
        cls,
        interaction: "discord.Interaction",
        command_name: str,
        *,
        game_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Async helper to await completion for testing or batch jobs."""
        doc = cls._command_doc(
            interaction,
            command_name,
            game_key=game_key,
            metadata=metadata,
        )

        await cls._run_async(
            lambda: cls.COMMAND_COLLECTION.insert_one(doc)
        )

    @classmethod
    def _game_doc(
        cls,
        interaction: "discord.Interaction",
        game_key: str,
        *,
        bet_amount: Optional[int] = None,
        source_command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        return doc

    @classmethod
    def record_game_start(
        cls,
        interaction: "discord.Interaction",
        game_key: str,
        *,
        bet_amount: Optional[int] = None,
        source_command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        immediate: bool = False,
    ) -> Optional[Any]:
        """Log that a user has started a new game session."""
        doc = cls._game_doc(
            interaction,
            game_key,
            bet_amount=bet_amount,
            source_command=source_command,
            metadata=metadata,
        )
        inserted_id: Dict[str, Any] = {}

        def op() -> None:
            result = cls.GAME_COLLECTION.insert_one(doc)
            inserted_id["value"] = result.inserted_id

        cls._dispatch_write(
            op,
            "MetricsManager game insert",
            immediate=immediate,
        )
        return inserted_id.get("value")

    @classmethod
    def record_game_result(
        cls,
        session_id: Any,
        *,
        result: str,
        payout: int = 0,
        net: int = 0,
        turns: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        immediate: bool = False,
    ) -> None:
        """Attach the outcome of a game session to an existing metrics record."""

        if session_id is None:
            return

        target_id = cls._normalize_id(session_id)

        def op() -> None:
            update: Dict[str, Any] = {
                "result": result,
                "payout": int(payout),
                "net": int(net),
                "completed_at": cls._utcnow(),
            }
            if turns is not None:
                update["turns"] = int(turns)
            if duration_seconds is not None:
                update["duration_seconds"] = float(duration_seconds)
            if metadata:
                update.update(metadata)

            cls.GAME_COLLECTION.update_one(
                {"_id": target_id},
                {"$set": update},
                upsert=False,
            )

        cls._dispatch_write(
            op,
            "MetricsManager game result update",
            immediate=immediate,
        )

    @classmethod
    def record_game_timeout(
        cls,
        session_id: Any,
        *,
        reason: str = "timeout",
        metadata: Optional[Dict[str, Any]] = None,
        immediate: bool = False,
    ) -> None:
        """Mark an incomplete session as a loss caused by abandonment or timeout."""
        if session_id is None:
            return

        target_id = cls._normalize_id(session_id)

        def op() -> None:
            session_doc = cls.GAME_COLLECTION.find_one({"_id": target_id})
            if not session_doc or session_doc.get("result") is not None:
                return

            stamped = cls._utcnow()
            bet_amount = session_doc.get("bet_amount") or 0
            try:
                wager = abs(int(bet_amount))
            except (TypeError, ValueError):
                wager = 0

            update: Dict[str, Any] = {
                "result": "loss",
                "payout": 0,
                "net": -wager,
                "completed_at": stamped,
                "completion_reason": reason,
                "timeout_logged_at": stamped,
            }

            started_at = session_doc.get("timestamp")
            if isinstance(started_at, datetime):
                normalized_started = started_at
                if normalized_started.tzinfo is None:
                    normalized_started = normalized_started.replace(
                        tzinfo=timezone.utc
                    )
                normalized_stamped = stamped
                if normalized_stamped.tzinfo is None:
                    normalized_stamped = normalized_stamped.replace(
                        tzinfo=timezone.utc
                    )
                update["duration_seconds"] = max(
                    0.0,
                    (normalized_stamped - normalized_started).total_seconds(),
                )

            if metadata:
                update.update(metadata)

            cls.GAME_COLLECTION.update_one(
                {"_id": target_id},
                {"$set": update},
                upsert=False,
            )

        cls._dispatch_write(
            op,
            "MetricsManager game timeout update",
            immediate=immediate,
        )

    @classmethod
    async def record_game_start_async(
        cls,
        interaction: "discord.Interaction",
        game_key: str,
        *,
        bet_amount: Optional[int] = None,
        source_command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        doc = cls._game_doc(
            interaction,
            game_key,
            bet_amount=bet_amount,
            source_command=source_command,
            metadata=metadata,
        )
        await cls._run_async(
            lambda: cls.GAME_COLLECTION.insert_one(doc)
        )


class MetricsRollups:
    """Aggregate daily economy and guild summaries for dashboards."""

    ECONOMY_ROLLUPS = db["metrics_economy_rollups"]
    GUILD_ROLLUPS = db["metrics_guild_rollups"]
    USER_GUILD_AFFINITY = db["metrics_user_guild_affinity"]
    _indexes_ready = False

    @classmethod
    def _ensure_indexes(cls) -> None:
        if cls._indexes_ready:
            return
        try:
            # Ensure rollup lookups and upserts stay efficient as data grows.
            cls.ECONOMY_ROLLUPS.create_index("date", unique=True)
            cls.GUILD_ROLLUPS.create_index(
                [("date", 1), ("guild_id", 1)], unique=True
            )
            cls.USER_GUILD_AFFINITY.create_index(
                [("user_id", 1), ("guild_id", 1)], unique=True
            )
            cls.USER_GUILD_AFFINITY.create_index(
                [("user_id", 1), ("is_primary", 1)]
            )
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] MetricsRollups index creation failed: {exc}")
        cls._indexes_ready = True

    @classmethod
    def record_economy_snapshot(cls, *, as_of: Optional[datetime] = None) -> Dict[str, Any]:
        """Capture total coins, wins/losses, and user counts."""
        cls._ensure_indexes()
        stamped = as_of or datetime.now(timezone.utc)
        date_key = stamped.date().isoformat()

        # Aggregate totals directly from the users collection so we capture the current economy state.
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_users": {"$sum": 1},
                    "total_balance": {"$sum": {"$ifNull": ["$balance", 0]}},
                    "total_coins_won": {"$sum": {"$ifNull": ["$coins_won", 0]}},
                    "total_coins_lost": {"$sum": {"$ifNull": ["$coins_lost", 0]}},
                    "total_games_played": {"$sum": {"$ifNull": ["$games_played", 0]}},
                }
            }
        ]

        aggregated = list(MetricsManager.USERS_COLLECTION.aggregate(pipeline))
        summary = aggregated[0] if aggregated else {}

        doc: Dict[str, Any] = {
            "date": date_key,
            "generated_at": stamped,
            "total_users": summary.get("total_users", 0),
            "total_balance": summary.get("total_balance", 0),
            "total_coins_won": summary.get("total_coins_won", 0),
            "total_coins_lost": summary.get("total_coins_lost", 0),
            "total_games_played": summary.get("total_games_played", 0),
        }

        cls.ECONOMY_ROLLUPS.update_one(
            {"date": date_key},
            {"$set": doc},
            upsert=True,
        )
        return doc

    @classmethod
    def record_guild_snapshot(
        cls,
        *,
        as_of: Optional[datetime] = None,
        window_hours: int = 24,
    ) -> list[Dict[str, Any]]:
        """Summarize game activity per guild over the recent window."""
        cls._ensure_indexes()
        stamped = as_of or datetime.now(timezone.utc)
        date_key = stamped.date().isoformat()
        window_start = stamped - timedelta(hours=window_hours)

        # Pull recent game sessions by guild to see which servers are most active.
        match_stage: Dict[str, Any] = {
            "guild_id": {"$ne": None},
            "timestamp": {"$gte": window_start},
        }

        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": {
                        "guild_id": "$guild_id",
                        "game_key": {"$ifNull": ["$game_key", "unknown"]},
                    },
                    "sessions": {"$sum": 1},
                    "total_bet": {"$sum": {"$ifNull": ["$bet_amount", 0]}},
                    "players": {"$addToSet": "$user_id"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "guild_id": "$_id.guild_id",
                    "game_key": "$_id.game_key",
                    "sessions": 1,
                    "total_bet": 1,
                    "players": "$players",
                    "unique_players": {"$size": "$players"},
                }
            },
            {
                "$group": {
                    "_id": "$guild_id",
                    "games": {
                        "$push": {
                            "game_key": "$game_key",
                            "sessions": "$sessions",
                            "unique_players": "$unique_players",
                            "total_bet": "$total_bet",
                        }
                    },
                    "total_sessions": {"$sum": "$sessions"},
                    "total_bet": {"$sum": "$total_bet"},
                    "player_sets": {"$push": "$players"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "guild_id": "$_id",
                    "games": 1,
                    "total_sessions": 1,
                    "total_bet": 1,
                    "unique_players": {
                        "$size": {
                            # Collapse all player id sets per guild into one combined unique list.
                            "$reduce": {
                                "input": "$player_sets",
                                "initialValue": [],
                                "in": {"$setUnion": ["$$value", "$$this"]},
                            }
                        }
                    },
                }
            },
        ]

        records = list(MetricsManager.GAME_COLLECTION.aggregate(pipeline))
        docs: list[Dict[str, Any]] = []

        for record in records:
            doc = {
                "date": date_key,
                "generated_at": stamped,
                "window_hours": window_hours,
                "window_start": window_start,
                "window_end": stamped,
                "guild_id": record["guild_id"],
                "total_sessions": record.get("total_sessions", 0),
                "unique_players": record.get("unique_players", 0),
                "total_bet": record.get("total_bet", 0),
                "games": record.get("games", []),
            }
            cls.GUILD_ROLLUPS.update_one(
                {"date": date_key, "guild_id": record["guild_id"]},
                {"$set": doc},
                upsert=True,
            )
            docs.append(doc)

        return docs

    @classmethod
    def record_user_guild_affinity(
        cls,
        *,
        as_of: Optional[datetime] = None,
        lookback_days: int = 30,
    ) -> list[Dict[str, Any]]:
        """Assign each user a primary guild based on recent activity."""
        cls._ensure_indexes()
        stamped = as_of or datetime.now(timezone.utc)
        window_start = stamped - timedelta(days=lookback_days)

        # Count how many sessions each user played per guild within the lookback window.
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": window_start},
                    "user_id": {"$ne": None},
                    "guild_id": {"$ne": None},
                }
            },
            {
                "$group": {
                    "_id": {"user_id": "$user_id", "guild_id": "$guild_id"},
                    "sessions": {"$sum": 1},
                    "last_played": {"$max": "$timestamp"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "user_id": "$_id.user_id",
                    "guild_id": "$_id.guild_id",
                    "sessions": 1,
                    "last_played": 1,
                }
            },
        ]

        records = list(MetricsManager.GAME_COLLECTION.aggregate(pipeline))

        by_user: Dict[int, list[Dict[str, Any]]] = {}
        for record in records:
            by_user.setdefault(record["user_id"], []).append(record)

        updates: list[Dict[str, Any]] = []
        for user_id, entries in by_user.items():
            # Highest session count wins; most recent play breaks ties so active guilds stay primary.
            entries.sort(
                key=lambda item: (
                    item.get("sessions", 0),
                    item.get("last_played")
                    if isinstance(item.get("last_played"), datetime)
                    else datetime.min.replace(tzinfo=timezone.utc),
                ),
                reverse=True,
            )
            primary_guild_id = entries[0]["guild_id"] if entries else None
            for entry in entries:
                doc = {
                    "user_id": user_id,
                    "guild_id": entry["guild_id"],
                    "sessions": entry.get("sessions", 0),
                    "last_played": entry.get("last_played", stamped),
                    "lookback_days": lookback_days,
                    "generated_at": stamped,
                    "is_primary": entry["guild_id"] == primary_guild_id,
                }
                cls.USER_GUILD_AFFINITY.update_one(
                    {"user_id": user_id, "guild_id": entry["guild_id"]},
                    {"$set": doc},
                    upsert=True,
                )
                updates.append(doc)

        return updates
