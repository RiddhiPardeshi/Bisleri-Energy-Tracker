from pymongo import MongoClient
import certifi
from config import Config

client = MongoClient(
    Config.MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000
)

mongo_db = client["bisleri_energy_tracker"]

admins = mongo_db["admins"]
daily_entries = mongo_db["daily_entries"]
expenses = mongo_db["expenses"]
stocks = mongo_db["stocks"]

# New collections
employees = mongo_db["employees"]
attendance = mongo_db["attendance"]
products = mongo_db["products"]
meters = mongo_db["meters"]