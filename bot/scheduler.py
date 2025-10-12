# bot/scheduler.py

import threading
import time
import schedule
import traceback
from datetime import datetime

from .db import list_subscriptions
from .fetcher import try_payloads, build_maps, cheapest_per_destination
from .formatter import format_card_ru
from .alerts import check_alerts_once

PAGE_SIZE = 5

def send_deals(bot, user_id, origin):
    """Send first 15 best deals to a user immediately."""
    data = try_payloads(origin, "uzs", "uz", max_directions=50, locales=["ru"])
    if not data:
        bot.send_message(user_id, f"Не удалось получить данные от API для {origin}.")
        return

    offers = data.get("one_way_offers") or []
    if not offers:
        bot.send_message(user_id, f"Нет доступных предложений из {origin}.")
        return

    cities_map, airlines_map = build_maps(data)
    best = cheapest_per_destination(offers)
    best.sort(key=lambda o: (o.get("price") or {}).get("value") or float("inf"))
    cards = [format_card_ru(item, cities_map, airlines_map, origin) for item in best[:PAGE_SIZE*3]]  # first 15 deals

    header = f"🌍 Ежедневные предложения из {cities_map.get(origin, origin)} ({origin})\n\n"
    for i in range(0, len(cards), PAGE_SIZE):
        chunk = "\n\n".join(cards[i:i+PAGE_SIZE])
        try:
            bot.send_message(user_id, header + chunk, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception:
            print(f"[Scheduler] Failed to send deals to {user_id} for {origin}")
            traceback.print_exc()

def run_scheduler(bot):
    """Start the scheduler in a background daemon thread."""
    def job_subscriptions():
        now = datetime.now()
        try:
            subs = list_subscriptions()
        except Exception:
            print("[Scheduler] Failed to load subscriptions")
            traceback.print_exc()
            return

        for sub in subs:
            try:
                # Access sqlite3.Row fields directly
                if not sub["enabled"]:
                    continue
                hour, minute = sub["hour"], sub["minute"]
                if now.hour == hour and now.minute == minute:
                    send_deals(bot, sub["user_id"], sub["origin"])
            except Exception:
                traceback.print_exc()
                continue

    def job_alerts():
        try:
            sent = check_alerts_once(bot)
            if sent:
                print(f"[Scheduler] Sent {sent} alert notifications.")
        except Exception:
            print("[Scheduler] Error running alerts job")
            traceback.print_exc()

    def scheduler_loop():
        print("[Scheduler] background thread started")
        schedule.every(1).minutes.do(job_subscriptions)
        schedule.every(1).minutes.do(job_alerts)
        while True:
            try:
                schedule.run_pending()
            except Exception:
                traceback.print_exc()
            time.sleep(5)

    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

__all__ = ["run_scheduler", "send_deals"]
