# bot/fetcher.py
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Dict, Tuple, List, Any, Optional

API_URL = "https://ariadne.aviasales.com/api/gql"
DOMAINS_TO_TRY = ["https://www.aviasales.uz", "https://www.aviasales.ru"]

# GraphQL queries
SAFE_QUERY = r"""query HotOffersV1($input: HotOffersV1Input!, $brand: Brand!, $locales: [String!]) {
  hot_offers_v1(input: $input, brand: $brand) {
    one_way_offers { price { depart_date value currency ticket_link found_at signature search_id main_airline with_baggage duration number_of_changes destination_city_iata segments { flight_legs { origin destination local_depart_date local_depart_time local_arrival_date local_arrival_time flight_number } transfers { duration_seconds country_code visa_required night_transfer at to tags } } } old_price { value currency } }
    meta_data_cities { city { iata translations(filters: {locales: $locales}) } }
    meta_data_airlines { iata translations(filters: {locales: $locales}) }
  }
}"""
MINIMAL_QUERY = r"""query HotOffersV1($input: HotOffersV1Input!, $brand: Brand!, $locales: [String!]) {
  hot_offers_v1(input: $input, brand: $brand) {
    one_way_offers { price { depart_date value currency ticket_link found_at signature search_id main_airline with_baggage duration number_of_changes destination_city_iata } old_price { value currency } }
    cities { city { iata translations(filters: {locales: $locales}) } }
    airlines { iata translations(filters: {locales: $locales}) }
  }
}"""
ULTRA_MINIMAL_QUERY = r"""query HotOffersV1($input: HotOffersV1Input!, $brand: Brand!) {
  hot_offers_v1(input: $input, brand: $brand) {
    one_way_offers { price { value currency destination_city_iata depart_date ticket_link } old_price { value currency } }
  }
}"""
CANDIDATE_PAYLOADS = [(SAFE_QUERY, "HotOffersV1"), (MINIMAL_QUERY, "HotOffersV1"), (ULTRA_MINIMAL_QUERY, "HotOffersV1")]

def try_payloads(origin: str, currency: str = "uzs", market: str = "uz", max_directions: int = 50, locales: list = ["ru"]) -> Optional[Dict[str, Any]]:
    base_input = {
        "origin_iata": origin,
        "origin_type": "CITY",
        "currency": currency,
        "market": market,
        "one_way": True,
        "trip_class": "Y",
        "max_directions": max_directions,
        "group_by": "NONE",
        "badge_flag": "on",
        "tags_flag": None,
    }
    for query, op_name in CANDIDATE_PAYLOADS:
        vars_ = {"brand": "AS", "input": base_input}
        if "$locales" in query:
            vars_["locales"] = locales
        payload = {"query": query, "variables": vars_, "operation_name": op_name}
        try:
            r = requests.post(API_URL, json=payload, timeout=12)
            body = r.json()
        except Exception:
            continue
        if r.status_code != 200 or body.get("errors"):
            continue
        data = body.get("data", {}).get("hot_offers_v1") or body.get("hot_offers_v1")
        if data:
            return data
    return None

def cheapest_per_destination(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best = {}
    for o in offers:
        p = o.get("price") or {}
        dest = p.get("destination_city_iata")
        if not dest:
            segs = p.get("segments") or []
            if segs:
                legs = segs[0].get("flight_legs") or []
                if legs:
                    dest = legs[-1].get("destination")
        if not dest:
            continue
        v = p.get("value")
        if v is None:
            continue
        if dest not in best or v < (best[dest]["price"].get("value") or float("inf")):
            best[dest] = o
    return list(best.values())

def build_maps(data: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    cities, airlines = {}, {}
    for it in data.get("meta_data_cities") or data.get("cities") or []:
        city = it.get("city") or {}
        iata = city.get("iata")
        if not iata:
            continue
        trans = city.get("translations") or {}
        name = None
        ru = trans.get("ru")
        if isinstance(ru, dict):
            for v in ru.values():
                if isinstance(v, str) and v.strip():
                    name = v.strip()
                    break
        elif isinstance(ru, str) and ru.strip():
            name = ru.strip()
        cities[iata] = name or iata
    for it in data.get("meta_data_airlines") or data.get("airlines") or []:
        code = it.get("iata")
        if not code:
            continue
        trans = it.get("translations") or {}
        name = None
        for v in trans.values():
            if isinstance(v, str) and v.strip():
                name = v.strip()
                break
            if isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, str) and vv.strip():
                        name = vv.strip()
                        break
                if name:
                    break
        airlines[code] = name or it.get("name") or code
    return cities, airlines

def build_search_link_from_ticket(ticket_link: str, price_block: Dict[str, Any], prefer_domain: str = DOMAINS_TO_TRY[0]) -> Tuple[str, Optional[str]]:
    if not ticket_link:
        return "N/A", "no ticket_link"
    if ticket_link.startswith("http"):
        return ticket_link, None
    if not ticket_link.startswith("/"):
        ticket_link = "/" + ticket_link
    parsed = urlparse(ticket_link)
    clean_path = parsed.path
    if not clean_path.startswith("/search/"):
        clean_path = "/search/" + clean_path.lstrip("/")
    qs = parse_qs(parsed.query, keep_blank_values=True)
    depart_date = price_block.get("depart_date")
    if depart_date:
        try:
            qs["search_date"] = [datetime.strptime(depart_date, "%Y-%m-%d").strftime("%d%m%Y")]
        except Exception:
            pass
    val = price_block.get("value")
    if "expected_price" not in qs and val is not None:
        qs["expected_price"] = [str(int(val)) if float(val).is_integer() else str(val)]
    if "expected_price_currency" not in qs and price_block.get("currency"):
        qs["expected_price_currency"] = [price_block.get("currency")]
    if "expected_price_source" not in qs:
        qs["expected_price_source"] = ["share"]
    if "expected_price_uuid" not in qs and price_block.get("search_id"):
        qs["expected_price_uuid"] = [price_block.get("search_id")]
    if "t" not in qs:
        sig = price_block.get("signature") or price_block.get("search_id")
        if sig:
            qs["t"] = [str(sig)]
    qs["request_source"] = ["explore-hot_tickets"]
    qs["utm_source"] = ["explore-hot_tickets"]
    ordered_keys = ["expected_price","expected_price_currency","expected_price_source","expected_price_uuid","request_source","search_date","t","utm_source"]
    params_list = [(k,vv) for k in ordered_keys if k in qs for vv in qs[k]]
    for k,vv_list in qs.items():
        if k not in ordered_keys:
            for vv in vv_list:
                params_list.append((k,vv))
    full_url = prefer_domain.rstrip("/") + clean_path + "?" + urlencode(params_list, doseq=True, safe=":/_.,")
    return full_url, None
