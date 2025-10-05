###########################################################
# File: EconomyManager.py
#
# Description: MongoDB economy manager for user balances,
#              user creation, bets, and payouts.
###########################################################

from pymongo import MongoClient  # type: ignore
from pymongo.server_api import ServerApi  # type: ignore
from dotenv import load_dotenv
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
        #find an existing user or create a new one with default balance
        record = EconomyManager.COLLECTION.find_one({"user_id": user_id})
        if record:
            return record

        new_user = {
            "user_id": user_id,
            "username": username,
            "balance": 1000,
            "games_played": 0,
            "created_at": int(time.time()),
        }

        EconomyManager.COLLECTION.insert_one(new_user)
        print(f"[DEBUG] Created new user record for {username} ({user_id}) with 1000 coins.")
        return new_user

    ###########################################################
    # get balance
    ###########################################################
    @staticmethod
    def balance(user_id: int, username: str = "Unknown") -> int:
        record = EconomyManager.ensure_user(user_id, username)
        return record.get("balance", 0)

    ###########################################################
    # grant coins
    ###########################################################
    @staticmethod
    def grant(user_id: int, amount: int, username: str = "Unknown") -> int:
        EconomyManager.ensure_user(user_id, username)
        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}}
        )
        new_balance = EconomyManager.balance(user_id, username)
        print(f"[DEBUG] Granted {amount} coins to {username} ({user_id}) -> balance {new_balance}")
        return new_balance

    ###########################################################
    # wager coins
    ###########################################################
    @staticmethod
    def wager(user_id: int, amount: int, username: str = "Unknown") -> bool:
        bal = EconomyManager.balance(user_id, username)
        if bal < amount:
            print(f"[DEBUG] Wager denied for {username} ({user_id}): {bal} < {amount}")
            return False

        EconomyManager.COLLECTION.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )
        print(f"[DEBUG] Wager accepted: {username} ({user_id}) bet {amount}, new balance {bal - amount}")
        return True

    ###########################################################
    # payout winnings
    ###########################################################
    @staticmethod
    def payout(user_id: int, amount: int, username: str = "Unknown") -> int:
        EconomyManager.ensure_user(user_id, username)
        new_balance = EconomyManager.grant(user_id, amount, username)
        print(f"[DEBUG] Payout: {username} ({user_id}) won {amount}, balance {new_balance}")
        return new_balance
