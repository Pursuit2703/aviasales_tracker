# bot/formatter.py
from typing import Dict, Any
from .utils import simple_search_link, compact_price, format_date_ru

def format_card_ru(o: Dict[str, Any], cities_map: Dict[str,str], airlines_map: Dict[str,str], origin: str) -> str:
    p = o.get("price") or {}
    old = o.get("old_price") or {}

    dest = p.get("destination_city_iata") or "?"
    dest_name = cities_map.get(dest, dest)
    curr = p.get("currency") or "UZS"

    compact = compact_price(p.get("value"), curr)
    old_compact = compact_price(old.get("value"), curr) if old else "—"

    depart_date = p.get("depart_date")
    depart_display = format_date_ru(depart_date) or ""

    segs = p.get("segments") or []
    origin_code = origin
    depart_time = arrival_time = None
    if segs:
        fl1 = segs[0].get("flight_legs") or []
        fl2 = segs[-1].get("flight_legs") or []
        if fl1:
            origin_code = fl1[0].get("origin") or origin
            depart_date = fl1[0].get("local_depart_date") or depart_date
            depart_time = fl1[0].get("local_depart_time")
        if fl2:
            arrival_time = fl2[-1].get("local_arrival_time")
            dest = fl2[-1].get("destination") or dest
            dest_name = cities_map.get(dest, dest_name)

    airline_code = p.get("main_airline")
    airline_name = airlines_map.get(airline_code, airline_code or "")

    duration_minutes = p.get("duration")
    duration = "Неизвестно" if duration_minutes is None else f"{duration_minutes//60}ч {duration_minutes%60}м" if duration_minutes >= 60 else f"{duration_minutes}м"

    stops = p.get("number_of_changes")
    if stops is None:
        stops_str = ""
    elif stops == 0:
        stops_str = "Прямой рейс"
    elif stops == 1:
        stops_str = "1 пересадка"
    else:
        stops_str = f"{stops} пересадок"

    ticket_link = p.get("ticket_link")
    if not ticket_link or not ticket_link.startswith("http"):
        ticket_link = simple_search_link(origin_code, depart_date, dest, price_val=p.get("value"), currency=curr)

    lines = [
        f"✈️ **{dest_name} ({dest})**",
        f"🛫 Airline: *{airline_name}*" if airline_name else None,
        f"💰 Price: **{current_price}**" + (f" _(was {old_price})_" if old_price else ""),
        f"📅 Date: {depart_display}" if depart_display else None,
        f"⏰ Time: {depart_time or '??:??'} {origin_code} → {arrival_time or '??:??'} {dest}" if depart_time or arrival_time else None,
        f"🕒 Duration: {duration} / {stops_str}",
        "",
        f"[Подробнее и билеты >]({ticket_link})"
    ]

    return "\n".join(filter(None, lines))
