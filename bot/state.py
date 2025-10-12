# bot/state.py
import time
from typing import Dict, Any

# sessions: user_id -> session dict (type either 'deals' or 'cities')
sessions: Dict[int, Dict[str, Any]] = {}

# cached cities result with ttl
cities_cache = {"ts": 0, "data": None}
CITIES_CACHE_TTL = 600  # seconds
