###########################################################
# File: EconomyManager.py
#
# Description: MongoDB economy manager for user balances,
#              bets, and payouts.
###########################################################

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

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
    @staticmethod
    def balance(user_id: int) -> int:
        record = db["users"].find_one({"user_id": user_id})
        if not record:
            db["users"].insert_one({"user_id": user_id, "balance": 1000})
            print(f"[DEBUG] Created new user {user_id} with 1000 coins.")
            return 1000
        return record.get("balance", 0)

    @staticmethod
    def grant(user_id: int, amount: int) -> int:
        db["users"].update_one({"user_id": user_id}, {"$inc": {"balance": amount}}, upsert=True)
        new_balance = EconomyManager.balance(user_id)
        print(f"[DEBUG] Granted {amount} coins to {user_id} -> balance {new_balance}")
        return new_balance

    @staticmethod
    def wager(user_id: int, amount: int) -> bool:
        bal = EconomyManager.balance(user_id)
        if bal < amount:
            print(f"[DEBUG] Wager denied for {user_id}: {bal} < {amount}")
            return False
        db["users"].update_one({"user_id": user_id}, {"$inc": {"balance": -amount}})
        print(f"[DEBUG] Wager accepted: {user_id} bet {amount}, new balance {bal - amount}")
        return True

    @staticmethod
    def payout(user_id: int, amount: int) -> int:
        new_balance = EconomyManager.grant(user_id, amount)
        print(f"[DEBUG] Payout: {user_id} won {amount}, balance {new_balance}")
        return new_balance
