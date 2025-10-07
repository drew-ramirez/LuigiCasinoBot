###########################################################
# File: test_mongo.py
#
# Description: verifies MongoDB connection and economy functions
###########################################################

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.economy.EconomyManager import EconomyManager, db

###########################################################
# connection check
###########################################################
print("[DEBUG] Collections available:")
print(db.list_collection_names())

###########################################################
# just testing economy functions
###########################################################
test_user = "TestUser#355"

print("\n[DEBUG] Starting economy test...")
balance = EconomyManager.balance(test_user)
print(f"[DEBUG] Initial balance for {test_user}: {balance}")

EconomyManager.wager(test_user, 50)
EconomyManager.payout(test_user, 100)
final_balance = EconomyManager.balance(test_user)

print(f"[DEBUG] Final balance for {test_user}: {final_balance}")
print("[DEBUG] Test complete.")
