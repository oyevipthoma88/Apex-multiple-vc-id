import asyncio
import os
import threading

# CRITICAL: create loop FIRST, set as default, THEN import handlers
# so that `bot = Client(...)` in handlers.py binds to THIS loop
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

from pyrogram import idle
from handlers import bot, setup_telegram_logging

LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))


def _run_flask():
    from web import app
    # use_reloader=False is CRITICAL — otherwise Flask spawns 2nd process
    app.run(host="0.0.0.0", port=PORT, use_reloader=False, threaded=True)


async def main():
    # 1) Flask keep-alive in background thread
    threading.Thread(target=_run_flask, daemon=True).start()
    print("Web keep-alive running on port", PORT, flush=True)

    # 2) Start bot (handlers already registered on this client)
    await bot.start()
    print("Starting Telegram bot...", flush=True)

    # 3) Attach log channel
    if LOG_CHANNEL_ID:
        setup_telegram_logging(bot, LOG_CHANNEL_ID)
        print(f"[main] Deep logging -> {LOG_CHANNEL_ID}", flush=True)

    # 4) Restore accounts + start auto-rejoin
    try:
        from vcmanager import vcmanager
        await vcmanager.restore_all()
        print("Bot is running. Press Ctrl+C to stop.", flush=True)
        print("[auto-rejoin] loop started", flush=True)
    except Exception as e:
        print(f"[main] restore warning: {e}", flush=True)

    # 5) Keep alive
    await idle()
    await bot.stop()


if __name__ == "__main__":
    try:
        _loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            _loop.close()
        except Exception:
            pass
