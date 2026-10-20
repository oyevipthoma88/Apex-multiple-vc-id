import asyncio
import sys

from config import BOT_TOKEN, API_ID, API_HASH, OWNER_IDS, PORT
from database import init_db
import threading
from web import start_in_thread
from handlers import setup_telegram_logging, bot
import vcmanager
import database as db
from pyrogram import Client
import os


def _check_env():
    missing = []
    if not API_ID or not API_HASH:
        missing.append("API_ID / API_HASH")
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not OWNER_IDS or OWNER_IDS == [0]:
        missing.append("OWNER_IDS")
    if missing:
        print("Missing env vars: " + ", ".join(missing))
        print("Set them in your hosting dashboard or .env file.")
        sys.exit(1)


def run_flask():
    from web import app
    app.run(host="0.0.0.0", port=8080)


async def main():
    from handlers import bot  # use the client that already has all handlers

    _check_env()
    await init_db()
    print("Database initialized.")
    start_in_thread(PORT)
    print(f"Web keep-alive running on port {PORT}.")
    print("Starting Telegram bot...")
    # # threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()

    LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "0"))

    if LOG_CHANNEL_ID:
        setup_telegram_logging(bot, LOG_CHANNEL_ID)
        print(f"[main] Deep logging -> {LOG_CHANNEL_ID}")

    sessions = await db.list_sessions()
    for s in sessions:
        sname = s["session_name"] if isinstance(s, dict) else s
        sstr = s.get("session_string", "") if isinstance(s, dict) else ""
        ok = await vcmanager.start_client(sname, sstr)
        print(f"  restored {sname}: {'ok' if ok else 'failed'}")
    await vcmanager.start_rejoin_loop()
    print(f"Bot is running. {len(sessions)} accounts loaded. Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await vcmanager.stop_all()
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
