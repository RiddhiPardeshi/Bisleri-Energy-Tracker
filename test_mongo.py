from pymongo import MongoClient
from config import Config
import certifi

client = MongoClient(
    Config.MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where()
)

print(client.list_database_names())