###########################################################
# File: test_mongo.py
#
# Description: verifies MongoDB connection and basic economy operations
###########################################################

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.economy.EconomyManager import db

print("[DEBUG] Collections available:")
print(db.list_collection_names())
