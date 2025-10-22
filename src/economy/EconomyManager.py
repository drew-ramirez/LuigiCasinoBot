###########################################################
# File: EconomyManager.py
#
# Description: MongoDB economy manager for user balances,
#              user creation, bets, and payouts.
###########################################################

from pymongo import MongoClient  # type: ignore
from pymongo.server_api import ServerApi  # type: ignore
from dotenv import load_dotenv
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
import os
import time

###########################################################
# database connection
###########################################################
load_dotenv()

uri = os.getenv("MONGO_URI")
client = MongoClient(uri, server_api=ServerApi("1"))
db = client[os.getenv("DATABASE_NAME", "luigicasino")]


###########################################################
# economy manager
###########################################################
class EconomyManager:
    COLLECTION = db["users"]

    ###########################################################
    # ensure user exists
    ###########################################################
    @staticmethod
    def ensure_user(user_id: int, username: str = "Unknown") -> dict:
        # find an existing user or create a new one with default balance
        record = EconomyManager.COLLECTION.find_one({"user_id": user_id})
        if record:
            return record

        new_user = {
            "user_id": user_id,
            "username": username,
            "balance": 500,
            "games_played": 0,
            "created_at": int(time.time()),
            # Tracking fields for future features
            "star_bonuses": {},
            "career_stars_total": 0,
            "coins_won": 0,
            "coins_lost": 0,
            "biggest_cashout": 0,
            "profile_level": 1,
            "daily_claim_streak": 0,
            "last_daily_claim": "",
            "animations_enabled": True,
        }

        EconomyManager.COLLECTION.insert_one(new_user)
        return new_user

    ###########################################################
    # get balance
    ###########################################################
    @staticmethod
    def balance(user_id: int, username: str = "Unknown") -> int:
        record = EconomyManager.ensure_user(user_id, username)
        return record.get("balance", 0)

    ###########################################################
    # star bonus helpers
    ###########################################################
    @staticmethod
    def _resolve_bonus_map(record: dict) -> dict:
        """Return the star bonus map, handling legacy 'streaks' key."""
        bonuses = record.get("star_bonuses")
        if bonuses is None:
            bonuses = record.get("streaks", {})
        return bonuses or {}

    ###########################################################
    # animation preference
    ###########################################################
    @staticmethod
    def animations_enabled(user_id: int, username: str = "Unknown") -> bool:
        record = EconomyManager.ensure_user(user_id, username)
        pref = record.get("animations_enabled")
        if pref is None:
            return True
        return bool(pref)

    @staticmethod
    def set_animations_enabled(
        user_id: int, enabled: bool, username: str = "Unknown"
    ) -> bool:
        EconomyManager.ensure_user(user_id, username)
        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id}, {"$set": {"animations_enabled": bool(enabled)}}
        )
        return bool(enabled)

    @staticmethod
    def star_bonus_count(user_id: int, game_key: str, username: str = "Unknown") -> int:
        record = EconomyManager.ensure_user(user_id, username)
        bonuses = EconomyManager._resolve_bonus_map(record)
        try:
            return max(0, int(bonuses.get(game_key, 0)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def star_bonus_multiplier(stars: int, game_key: str | None = None) -> float:
        rules: dict[str | None, tuple[float, float]] = {
            "pairagone": (0.25, 2.5),
            "memorymatch": (0.25, 2.5),
            "picturepoker": (0.15, 2.5),
            "luckystars": (0.15, 2.5),
            None: (0.05, 1.5),
        }
        increment, max_multiplier = rules.get(game_key, rules[None])
        stars = max(0, int(stars))
        multiplier = 1.0 + (stars * increment)
        multiplier = min(multiplier, max_multiplier)
        return round(multiplier, 4)

    @staticmethod
    def adjust_star_bonus(
        user_id: int,
        game_key: str,
        *,
        delta: int | None = None,
        absolute: int | None = None,
        username: str = "Unknown",
        career_increment: int = 0,
    ) -> dict:
        """
        Update the star bonus count for a given game, optionally increasing the career total.

        Returns a dict containing the new count, updated career total, and
        current multiplier.
        """
        record = EconomyManager.ensure_user(user_id, username)
        current = EconomyManager.star_bonus_count(user_id, game_key, username)

        if absolute is not None:
            new_value = max(0, int(absolute))
        elif delta is not None:
            new_value = max(0, current + int(delta))
        else:
            new_value = current

        update_query: dict[str, dict[str, object]] = {
            "$set": {f"star_bonuses.{game_key}": new_value}
        }
        if career_increment:
            update_query.setdefault("$inc", {})["career_stars_total"] = int(
                max(0, career_increment)
            )

        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id},
            update_query,
        )

        career_total = record.get("career_stars_total", 0) + max(
            0, int(career_increment)
        )
        multiplier = EconomyManager.star_bonus_multiplier(new_value, game_key)

        return {
            "stars": new_value,
            "career_total": career_total,
            "multiplier": multiplier,
        }

    @staticmethod
    def reset_star_bonus(
        user_id: int, game_key: str, username: str = "Unknown"
    ) -> dict:
        return EconomyManager.adjust_star_bonus(
            user_id,
            game_key,
            absolute=0,
            username=username,
        )

    ###########################################################
    # daily reward helpers
    ###########################################################
    @staticmethod
    def record_daily_claim(
        user_id: int,
        username: str = "Unknown",
    ) -> dict:
        """Handle daily reward streak tracking with a midnight PST reset."""
        record = EconomyManager.ensure_user(user_id, username)

        pst = ZoneInfo("America/Los_Angeles")
        now_pst = datetime.now(pst)
        today = now_pst.date()

        last_raw = record.get("last_daily_claim", "")
        last_date = None

        if isinstance(last_raw, str) and last_raw:
            try:
                last_date = datetime.strptime(last_raw, "%Y-%m-%d").date()
            except ValueError:
                last_date = None
        elif isinstance(last_raw, (int, float)) and last_raw:
            try:
                last_date = datetime.fromtimestamp(float(last_raw), tz=pst).date()
            except Exception:
                last_date = None

        streak_raw = record.get("daily_claim_streak", 0) or 0
        try:
            streak = max(0, int(streak_raw))
        except (TypeError, ValueError):
            streak = 0

        if last_date == today:
            next_midnight = datetime.combine(
                today + timedelta(days=1),
                dt_time.min,
                tzinfo=pst,
            )
            seconds_remaining = int((next_midnight - now_pst).total_seconds())
            return {
                "available": False,
                "seconds_remaining": max(0, seconds_remaining),
                "streak": streak,
                "last_claim": last_date,
            }

        if last_date == today - timedelta(days=1):
            streak += 1
        else:
            streak = 1

        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "last_daily_claim": today.isoformat(),
                    "daily_claim_streak": streak,
                }
            },
        )

        return {
            "available": True,
            "streak": streak,
            "last_claim": today,
        }

    ###########################################################
    # grant coins
    ###########################################################
    @staticmethod
    def grant(user_id: int, amount: int, username: str = "Unknown") -> int:
        EconomyManager.ensure_user(user_id, username)
        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id}, {"$inc": {"balance": amount}}
        )
        new_balance = EconomyManager.balance(user_id, username)
        return new_balance

    ###########################################################
    # wager coins
    ###########################################################
    @staticmethod
    def wager(user_id: int, amount: int, username: str = "Unknown") -> bool:
        bal = EconomyManager.balance(user_id, username)
        if bal < amount:
            return False

        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "balance": -amount,
                    "games_played": 1,
                    "coins_lost": amount,
                }
            },
        )
        return True

    ###########################################################
    # payout winnings
    ###########################################################
    @staticmethod
    def payout(user_id: int, amount: int, username: str = "Unknown") -> int:
        EconomyManager.ensure_user(user_id, username)
        update_query: dict[str, dict[str, object]] = {
            "$inc": {
                "balance": amount,
                "coins_won": amount,
            },
            "$max": {"biggest_cashout": amount},
        }
        EconomyManager.COLLECTION.update_one({"user_id": user_id}, update_query)
        new_balance = EconomyManager.balance(user_id, username)
        return new_balance

