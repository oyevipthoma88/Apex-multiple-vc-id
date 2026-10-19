import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "vcjoiner")
SESSIONS_DIR = os.environ.get("SESSIONS_DIR", "sessions")
OWNER_IDS = [int(x) for x in os.environ.get("OWNER_IDS", "0").split() if x.strip()]
PORT = int(os.environ.get("PORT", "8080"))
WEB_URL = os.environ.get("WEB_URL", f"http://localhost:{PORT}")

os.makedirs(SESSIONS_DIR, exist_ok=True)
