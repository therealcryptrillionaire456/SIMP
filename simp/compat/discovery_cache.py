"""
SIMP A2A Discovery Cache + Error Taxonomy — Sprint 4

Thread-safe TTL cache for agent cards and typed compat-layer errors.
"""

import time
import threading
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class CompatErrorCode(str, Enum):
    INVALID_CARD = "invalid_card"
    CARD_NOT_FOUND = "card_not_found"
    CACHE_MISS = "cache_miss"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMITED = "rate_limited"
    INTERNAL = "internal_error"


_HTTP_STATUS: Dict[str, int] = {
    CompatErrorCode.INVALID_CARD: 400,
    CompatErrorCode.CARD_NOT_FOUND: 404,
    CompatErrorCode.CACHE_MISS: 404,
    CompatErrorCode.VALIDATION_ERROR: 422,
    CompatErrorCode.RATE_LIMITED: 429,
    CompatErrorCode.INTERNAL: 500,
}


class CompatError(Exception):
    """Typed error for the A2A compatibility layer."""

    def __init__(self, code: CompatErrorCode, message: str = ""):
        self.code = code
        self.message = message or code.value
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS.get(self.code, 500)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "http_status": self.http_status,
        }


# ---------------------------------------------------------------------------
# Card cache
# ---------------------------------------------------------------------------

class CardCache:
    """
    Thread-safe TTL memoisation cache for A2A agent cards.

    Default TTL: 60 s for agent cards, 300 s for broker card.
    """

    def __init__(self, agent_ttl: int = 60, broker_ttl: int = 300):
        self._agent_ttl = agent_ttl
        self._broker_ttl = broker_ttl
        self._store: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            card, ts = entry
            ttl = self._broker_ttl if key == "__broker__" else self._agent_ttl
            if time.time() - ts > ttl:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return card

    def put(self, key: str, card: Dict[str, Any]) -> None:
        with self._lock:
            self._store[key] = (card, time.time())

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "agent_ttl": self._agent_ttl,
                "broker_ttl": self._broker_ttl,
            }


# ---------------------------------------------------------------------------
# Card validation
# ---------------------------------------------------------------------------

_REQUIRED_CARD_FIELDS = ("name", "version", "url")
_REQUIRED_CARD_TYPES = {"name": str, "version": str, "url": str}


def validate_agent_card(card: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate that *card* has the minimum required A2A Agent Card fields.

    Returns (True, None) on success, (False, reason) on failure.
    """
    if not isinstance(card, dict):
        return False, "Card must be a dict"
    for field_name in _REQUIRED_CARD_FIELDS:
        if field_name not in card:
            return False, f"Missing required field: {field_name}"
        expected_type = _REQUIRED_CARD_TYPES.get(field_name)
        if expected_type and not isinstance(card[field_name], expected_type):
            return False, f"Field '{field_name}' must be {expected_type.__name__}"
    return True, None
