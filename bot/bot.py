# bot/bot.py
import signal
import sys
import os
from telebot import TeleBot
from .handlers import register
from .db import init_db
from .scheduler import run_scheduler   

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")  
bot = TeleBot(BOT_TOKEN, parse_mode="Markdown")


def shutdown(*args):
    """Graceful shutdown on SIGINT/SIGTERM."""
    print("\n[INFO] Shutting down bot...")
    bot.stop_polling()
    sys.exit(0)


def main():
    init_db()
    register(bot)

    try:
        run_scheduler(bot)
    except Exception as e:
        print("[WARN] Failed to start scheduler:", e)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("[INFO] Bot started. Listening...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
