# bot/alerts.py
from typing import Dict, Any, List, Tuple
import traceback

from .db import list_alerts, update_alert_price
from .fetcher import try_payloads, cheapest_per_destination, build_maps

def _find_deal_for_destination(offers: List[Dict[str, Any]], destination: str):
    """Return the offer dict for the given destination (or None)."""
    for o in cheapest_per_destination(offers):
        p = o.get("price") or {}
        if p.get("destination_city_iata") == destination:
            return o
    return None

def check_alerts_once(bot) -> int:
    """
    Check all active alerts and send notifications if conditions met.

    Returns:
        count of notifications sent.
    """
    sent = 0
    alerts = list_alerts()
    if not alerts:
        return 0

    # Group alerts by origin to avoid fetching the same origin multiple times
    origins: Dict[str, List[Dict[str, Any]]] = {}
    for a in alerts:
        origins.setdefault(a["origin"], []).append(a)

    for origin, alerts_for_origin in origins.items():
        try:
            data = try_payloads(origin, "uzs", "uz", max_directions=50, locales=["ru"])
            if not data:
                # no data for this origin — skip all alerts for it
                continue

            offers = data.get("one_way_offers") or []
            cities_map, airlines_map = build_maps(data)

            for alert in alerts_for_origin:
                try:
                    alert_id = int(alert["id"])
                    user_id = alert["user_id"]
                    destination = alert["destination"]
                    target_price = alert["target_price"]
                    last_price = alert["last_price"]
                    active = alert["active"]

                    if not active:
                        continue

                    deal = _find_deal_for_destination(offers, destination)
                    if not deal:
                        continue

                    price_block = deal.get("price", {})
                    price = price_block.get("value")
                    if price is None:
                        continue

                    # If baseline not set, initialize it and skip notification
                    if last_price is None:
                        update_alert_price(alert_id, price)
                        continue

                    try:
                        current = float(price)
                        baseline = float(last_price)
                    except Exception:
                        continue

                    should_notify = False
                    if target_price is not None:
                        try:
                            tp = float(target_price)
                        except Exception:
                            tp = None
                        if tp is not None and current <= tp and current < baseline:
                            should_notify = True
                    else:
                        if current < baseline:
                            should_notify = True

                    if should_notify:
                        # build message
                        card_text = None
                        try:
                            # format_card_ru is not imported here to keep separation of concerns in alerts.
                            # We'll attach a concise message; scheduler previously used format_card_ru.
                            from .formatter import format_card_ru
                            card_text = format_card_ru(deal, cities_map, airlines_map, origin)
                        except Exception:
                            card_text = f"{origin} → {destination}: {int(current)}"

                        msg = f"💰 Цена изменилась для рейса {origin} → {destination}:\n\n{card_text}"
                        try:
                            bot.send_message(user_id, msg, parse_mode="Markdown", disable_web_page_preview=True)
                            sent += 1
                        except Exception:
                            # if send fails, log and continue
                            print(f"[Alerts] Failed to send message to {user_id} for alert {alert_id}")
                            traceback.print_exc()

                        # update baseline price
                        try:
                            update_alert_price(alert_id, current)
                        except Exception:
                            print(f"[Alerts] Failed to update baseline for alert {alert_id}")
                            traceback.print_exc()

                except Exception:
                    # Don't let one bad alert stop others
                    traceback.print_exc()
                    continue

        except Exception:
            print(f"[Alerts] Failed to fetch or process origin {origin}")
            traceback.print_exc()
            continue

    return sent
