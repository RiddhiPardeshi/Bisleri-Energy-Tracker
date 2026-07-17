import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    SECRET_KEY = os.getenv("SECRET_KEY", "bisleri_secret_key")

    MONGO_URI = os.getenv("MONGO_URI")