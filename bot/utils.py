# bot/utils.py

from datetime import datetime
from urllib.parse import urlencode

_RU_MONTH_GENITIVE = [
    "января","февраля","марта","апреля","мая","июня",
    "июля","августа","сентября","октября","ноября","декабря"
]

DOMAINS_TO_TRY = ["https://www.aviasales.uz", "https://www.aviasales.ru"]

def compact_price(amount, currency):
    """Return a compact human-friendly price string, e.g. '1.26M uzs' or '310.1k uzs'."""
    try:
        a = float(amount)
        if a >= 1_000_000:
            return f"{a/1_000_000:.2f}M {currency}"
        if a >= 1_000:
            # if divisible by 1000 show integer '1k', otherwise one decimal
            return f"{a/1000:.1f}k {currency}" if a % 1000 else f"{int(a/1000)}k {currency}"
        return f"{int(a)} {currency}"
    except Exception:
        return f"{amount} {currency}"

def format_date_ru(ymd):
    """Convert 'YYYY-MM-DD' -> 'D <month name in genitive> YYYY' or return input on failure."""
    if not ymd:
        return None
    try:
        dt = datetime.strptime(ymd, "%Y-%m-%d")
        return f"{dt.day} {_RU_MONTH_GENITIVE[dt.month-1]} {dt.year}"
    except Exception:
        return ymd

def _yyyymmdd_to_ddmmyyyy(date_str):
    """Convert YYYY-MM-DD -> DDMMYYYY string used for search URLs."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d%m%Y")
    except Exception:
        return None

def simple_search_link(origin, depart_date, dest, price_val=None, currency=None, prefer_domain=DOMAINS_TO_TRY[0]):
    """
    Construct a simple Aviasales /search/ URL used as a fallback when ticket_link isn't a full URL.
    This preserves the original project's URL structure (dd[:4] behavior kept intentionally).
    """
    dd = _yyyymmdd_to_ddmmyyyy(depart_date) or datetime.now().strftime("%d%m%Y")
    # keep the original pattern (origin + first 4 chars of dd + dest + '1')
    path = f"/search/{origin}{dd[:4]}{dest}1"
    params = [
        ("expected_price", str(int(price_val)) if price_val else ""),
        ("expected_price_currency", currency or ""),
        ("expected_price_source", "share"),
        ("search_date", dd),
        ("request_source", "explore-hot_tickets"),
        ("utm_source", "explore-hot_tickets"),
    ]
    q = urlencode(params, doseq=True, safe=":/_.,")
    return prefer_domain.rstrip("/") + path + "?" + q
