###########################################################
# File: EconomyManager.py
#
# Description: MongoDB economy manager for user balances,
#              bets, and payouts.
###########################################################
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DATABASE_NAME", "luigicasino")]
