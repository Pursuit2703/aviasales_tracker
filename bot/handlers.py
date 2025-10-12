# bot/handlers.py
from telebot import types
from telebot.types import Message, CallbackQuery
from .fetcher import try_payloads, build_maps, cheapest_per_destination
from .formatter import format_card_ru
from .state import sessions, cities_cache, CITIES_CACHE_TTL
from .db import (
    add_subscription,
    alert_exists,
    add_alert,
    list_user_alerts,
    disable_alert,
    get_conn,
)
import time

PAGE_SIZE = 5
DEFAULT_ORIGIN = "TAS"
DEFAULT_CURRENCY = "uzs"
DEFAULT_MARKET = "uz"


def _format_price(amount, currency=DEFAULT_CURRENCY):
    try:
        a = int(round(float(amount)))
        return f"{a:,}".replace(",", " ") + f" {currency}"
    except Exception:
        return f"{amount} {currency}"


def make_markup_for_page(idx, total):
    kb = types.InlineKeyboardMarkup()
    if total <= 1:
        return kb
    if idx == 0:
        kb.add(types.InlineKeyboardButton("ДАЛЕЕ ▶", callback_data=f"nav_NEXT_{idx}"))
    elif idx == total - 1:
        kb.add(types.InlineKeyboardButton("◀ НАЗАД", callback_data=f"nav_BACK_{idx}"))
    else:
        kb.row(
            types.InlineKeyboardButton("◀ НАЗАД", callback_data=f"nav_BACK_{idx}"),
            types.InlineKeyboardButton("ДАЛЕЕ ▶", callback_data=f"nav_NEXT_{idx}")
        )
    return kb


def paginate(items, header="", footer=""):
    pages = []
    for i in range(0, len(items), PAGE_SIZE):
        pages.append(header + "\n".join(items[i:i + PAGE_SIZE]) + footer)
    return pages


def safe_fetch(origin, limit=50):
    try:
        data = try_payloads(origin, DEFAULT_CURRENCY, DEFAULT_MARKET, max_directions=limit, locales=["ru"])
        return data or {}
    except Exception:
        return {}


def register(bot):
    # -------------------- Bot commands --------------------
    bot.set_my_commands([
        types.BotCommand("start", "✅ Запустить бота"),
        types.BotCommand("help", "♻️ Помощь"),
        types.BotCommand("deals", "✈ Лучшие предложения"),
        types.BotCommand("cities", "🌍 Список городов"),
        types.BotCommand("subscribe", "🔔 Подписка на ежедневные предложения"),
        types.BotCommand("unsubscribe", "❌ Отписка от ежедневных предложений"),
        types.BotCommand("alert", "💰 Создать оповещение о цене"),
        types.BotCommand("myalerts", "📋 Мои оповещения"),
    ])

    # -------------------- Start / Help --------------------
    @bot.message_handler(commands=["start", "help"])
    def cmd_start(msg: Message):
        user_name = msg.from_user.first_name or "друг"
        intro = (
            f"👋 Привет, {user_name}!\n\n"
            "Я — ваш помощник по авиабилетам ✈️\n"
            "Команды для старта:\n"
            "✈ /deals IATA — лучшие предложения из города\n"
            "🌍 /cities — список городов\n"
            "🔔 /subscribe IATA [HH] [MM] — ежедневные предложения\n"
            "❌ /unsubscribe — отменить подписку\n"
            "💰 /alert ORIGIN DESTINATION [Цель] — оповещение о цене\n"
            "📋 /myalerts — активные оповещения"
        )
        bot.reply_to(msg, intro)

    # -------------------- Unsubscribe --------------------
    @bot.message_handler(commands=["unsubscribe"])
    def cmd_unsubscribe(msg: Message):
        user_id = msg.from_user.id
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE subscriptions SET enabled = 0 WHERE user_id = ?", (user_id,))
        changed = cur.rowcount
        conn.commit()
        conn.close()
        bot.reply_to(msg, "✅ Ваша подписка отменена." if changed else "❌ У вас нет активных подписок.")

    # -------------------- Cities --------------------
    @bot.message_handler(commands=["cities"])
    def cmd_cities(msg: Message):
        now = time.time()
        if not cities_cache["data"] or now - cities_cache["ts"] > CITIES_CACHE_TTL:
            data = safe_fetch(DEFAULT_ORIGIN)
            cities_map, _ = build_maps(data)
            if not cities_map:
                cities_map = {"TAS": "Ташкент", "MOW": "Москва", "IST": "Стамбул", "DXB": "Дубай", "AYT": "Анталья"}
            cities_cache.update({"data": cities_map, "ts": now})
        else:
            cities_map = cities_cache["data"]

        items = sorted([f"✈ {iata} — {name}" for iata, name in cities_map.items()])
        pages = paginate(items, header="🌍 Доступные города и IATA-коды\n\n", footer="\n\nЧтобы искать билеты: /deals TAS")
        if not pages:
            bot.reply_to(msg, "Нет доступных городов.")
            return

        status = bot.send_message(msg.chat.id, "Генерирую список городов...", disable_web_page_preview=True)
        bot.edit_message_text(pages[0], msg.chat.id, status.message_id, parse_mode="Markdown",
                              disable_web_page_preview=True, reply_markup=make_markup_for_page(0, len(pages)))
        sessions[msg.from_user.id] = {"type": "cities", "pages": pages, "page": 0,
                                      "message_id": status.message_id, "chat_id": msg.chat.id}

    # -------------------- Deals --------------------
    @bot.message_handler(commands=["deals"])
    def cmd_deals(msg: Message):
        parts = msg.text.strip().split()
        origin = parts[1].upper() if len(parts) >= 2 else DEFAULT_ORIGIN
        limit = min(100, max(1, int(parts[2]))) if len(parts) >= 3 else 20

        status_msg = bot.send_message(msg.chat.id, f"Ищу предложения из {origin}...", disable_web_page_preview=True)
        data = safe_fetch(origin)
        offers = data.get("one_way_offers") or []
        if not offers:
            bot.edit_message_text("Предложения не найдены.", msg.chat.id, status_msg.message_id)
            return

        cities_map, airlines_map = build_maps(data)
        best = cheapest_per_destination(offers)
        best.sort(key=lambda o: (o.get("price") or {}).get("value") or float("inf"))

        cards = [format_card_ru(item, cities_map, airlines_map, origin) for item in best[:limit]]
        pages = paginate(cards, header=f"🌍 Предложения из {cities_map.get(origin, origin)} ({origin})\n\n",
                         footer="\n\nЧтобы изменить город, используйте: /deals IST")

        bot.edit_message_text(pages[0], msg.chat.id, status_msg.message_id, parse_mode="Markdown",
                              disable_web_page_preview=True, reply_markup=make_markup_for_page(0, len(pages)))
        sessions[msg.from_user.id] = {"type": "deals", "pages": pages, "page": 0,
                                      "message_id": status_msg.message_id, "chat_id": msg.chat.id,
                                      "meta": {"origin": origin}}

    # -------------------- Subscribe --------------------
    @bot.message_handler(commands=["subscribe"])
    def cmd_subscribe(msg: Message):
        parts = msg.text.strip().split()
        origin = parts[1].upper() if len(parts) >= 2 else DEFAULT_ORIGIN
        hour = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 10
        minute = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0

        conn = get_conn()
        conn.cursor().execute("UPDATE subscriptions SET enabled = 0 WHERE user_id = ?", (msg.from_user.id,))
        conn.commit()
        conn.close()

        add_subscription(msg.from_user.id, origin, hour, minute)
        bot.reply_to(msg, f"✅ Подписка на предложения из {origin} в {hour:02d}:{minute:02d} установлена.")

    # -------------------- Alerts --------------------
    @bot.message_handler(commands=["alert"])
    def cmd_alert(msg: Message):
        parts = msg.text.strip().split()
        if len(parts) < 3:
            bot.reply_to(msg, "Использование: /alert ORIGIN DESTINATION [TARGET_PRICE]")
            return

        origin, destination = parts[1].upper(), parts[2].upper()
        target_price = float(parts[3]) if len(parts) >= 4 else None

        if alert_exists(msg.from_user.id, origin, destination):
            bot.reply_to(msg, f"⚠ Уже есть активное оповещение для {origin} → {destination}. /myalerts")
            return

        last_price = None
        data = safe_fetch(origin)
        offers = data.get("one_way_offers") or []
        for o in cheapest_per_destination(offers):
            p = o.get("price") or {}
            if p.get("destination_city_iata") == destination:
                last_price = p.get("value")
                break

        alert_id = add_alert(msg.from_user.id, origin, destination, target_price, last_price)

        text = f"✅ Оповещение установлено: {origin} → {destination}"
        if target_price is not None:
            text += f" (цель ≤ {_format_price(target_price)})"
        text += f"\n💰 Текущая цена: {_format_price(last_price) if last_price else 'N/A'}"
        text += f"\nID оповещения: {alert_id}"
        bot.reply_to(msg, text)

    # -------------------- My Alerts --------------------
    @bot.message_handler(commands=["myalerts"])
    def cmd_myalerts(msg: Message):
        alerts = list_user_alerts(msg.from_user.id, active_only=True)
        if not alerts:
            bot.reply_to(msg, "У вас нет активных оповещений.")
            return
        for a in alerts:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"delalert_{a['id']}"))
            bot.send_message(msg.chat.id,
                             f"🔔 ID {a['id']} — {a['origin']} → {a['destination']}\n"
                             f"Базовая: {_format_price(a['last_price']) if a['last_price'] else 'N/A'} | "
                             f"Цель: {_format_price(a['target_price']) if a['target_price'] else '—'}",
                             reply_markup=kb)

    # -------------------- Callbacks --------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("delalert_"))
    def cb_delete_alert(call: CallbackQuery):
        alert_id = int(call.data.split("_")[1])
        ok = disable_alert(alert_id, call.from_user.id)
        bot.answer_callback_query(call.id, "✅ Оповещение отключено." if ok else "❗ Нельзя отключить.")
        if ok:
            try:
                bot.edit_message_text("❌ Оповещение отключено.", call.message.chat.id, call.message.message_id)
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda c: c.data.startswith("nav_"))
    def cb_nav(call: CallbackQuery):
        uid, sess = call.from_user.id, sessions.get(call.from_user.id)
        if not sess:
            return bot.answer_callback_query(call.id, "Сессия не найдена. /deals или /cities снова.")
        action, cur = call.data.split("_")[1], sess.get("page", 0)
        total = len(sess["pages"])
        new = min(total - 1, cur + 1) if action == "NEXT" else max(0, cur - 1)
        if new == cur:
            return bot.answer_callback_query(call.id)
        bot.edit_message_text(sess["pages"][new], sess["chat_id"], sess["message_id"],
                              parse_mode="Markdown", disable_web_page_preview=True,
                              reply_markup=make_markup_for_page(new, total))
        sess["page"] = new
        bot.answer_callback_query(call.id)
