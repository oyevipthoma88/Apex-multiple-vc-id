import asyncio
import sys

from config import BOT_TOKEN, API_ID, API_HASH, OWNER_IDS, PORT
from database import init_db
from web import start_in_thread
from handlers import bot
import vcmanager


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
        print("Set them in Render Dashboard or your .env file.")
        sys.exit(1)


async def main():
    _check_env()
    await init_db()
    print("Database initialized.")
    start_in_thread(PORT)
    print(f"Web keep-alive running on port {PORT}.")
    print("Starting Telegram bot...")
    await bot.start()
    # Restore any saved accounts + auto-rejoin on boot
    import database as db
    sessions = await db.list_sessions()
    for s in sessions:
        ok = await vcmanager.start_client(s)
        print(f"  restored {s}: {'ok' if ok else 'failed'}")
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
