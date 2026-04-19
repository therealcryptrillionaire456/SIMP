"""
SIMP Intent Delivery Engine — Sprint 51

Delivers routed intents to registered agents via HTTP POST.
File-based agents are skipped with FILE_BASED_SKIP status.
Uses stdlib urllib only — no third-party HTTP libraries.
"""

import json
import logging
import threading
import time
import urllib.request
import urllib.error
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("SIMP.Delivery")


# ---------------------------------------------------------------------------
# Delivery status constants
# ---------------------------------------------------------------------------

class DeliveryStatus:
    """Constants for delivery outcomes."""
    DELIVERED = "delivered"
    FILE_BASED_SKIP = "file_based_skip"
    IDEMPOTENT_SKIP = "idempotent_skip"
    FAILED_TIMEOUT = "failed_timeout"
    FAILED_HTTP = "failed_http"
    FAILED_CONNECTION = "failed_connection"
    FAILED_INVALID_ENDPOINT = "failed_invalid_endpoint"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DeliveryResult:
    """Outcome of a single delivery attempt."""
    status: str
    attempts: int = 0
    elapsed_ms: float = 0.0
    http_status: Optional[int] = None
    response_body: str = ""
    error: str = ""


@dataclass
class DeliveryConfig:
    """Tuning knobs for the delivery engine."""
    max_attempts: int = 3
    base_backoff_s: float = 1.0
    timeout_s: float = 10.0
    max_response_body: int = 500
    idempotency_cache_size: int = 1000  # Max entries in idempotency cache
    idempotency_ttl_s: float = 300.0    # 5 minutes TTL for idempotency cache


# ---------------------------------------------------------------------------
# IntentDeliveryEngine
# ---------------------------------------------------------------------------

class IntentDeliveryEngine:
    """
    Delivers intents to agent HTTP endpoints.

    Resolution rules:
    - File-based agents (endpoint contains "(file-based)" or doesn't start with
      "http") are never contacted — returns FILE_BASED_SKIP immediately.
    - HTTP agents get a POST to {endpoint}/intent with JSON body.
    - On connection error: retry up to max_attempts with exponential backoff.
    - On 4xx/5xx: fail immediately with FAILED_HTTP (no retry).
    - On timeout: fail immediately with FAILED_TIMEOUT.
    - Idempotency: prevents duplicate delivery of same intent to same endpoint
      within config.idempotency_ttl_s seconds.
    """

    def __init__(self, config: Optional[DeliveryConfig] = None):
        self.config = config or DeliveryConfig()
        # LRU cache for idempotency: key = (endpoint, intent_id_hash)
        self._idempotency_cache: OrderedDict = OrderedDict()
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_file_based(endpoint: str) -> bool:
        """Return True if the endpoint indicates a file-based agent."""
        if not endpoint:
            return True
        if "(file-based)" in endpoint:
            return True
        if not endpoint.lower().startswith("http"):
            return True
        return False

    # ------------------------------------------------------------------
    # idempotency helpers
    # ------------------------------------------------------------------

    def _check_idempotency(self, endpoint: str, intent_data: Dict[str, Any]) -> bool:
        """
        Check if this intent has already been delivered to this endpoint.
        Returns True if duplicate (should skip), False if new.
        """
        intent_id = intent_data.get("intent_id", "")
        if not intent_id:
            return False  # No intent_id, can't track idempotency
        
        # Create cache key
        cache_key = f"{endpoint}:{intent_id}"
        
        with self._cache_lock:
            # Check if in cache
            if cache_key in self._idempotency_cache:
                timestamp, _ = self._idempotency_cache[cache_key]
                # Check if still within TTL
                if time.time() - timestamp < self.config.idempotency_ttl_s:
                    logger.debug("Idempotency check: duplicate intent %s to %s", intent_id, endpoint)
                    return True
                else:
                    # Expired, remove it
                    del self._idempotency_cache[cache_key]
            
            # Add to cache (or update if expired)
            self._idempotency_cache[cache_key] = (time.time(), intent_id)
            
            # Trim cache if too large
            while len(self._idempotency_cache) > self.config.idempotency_cache_size:
                self._idempotency_cache.popitem(last=False)
        
        return False

    def _record_delivery(self, endpoint: str, intent_data: Dict[str, Any]) -> None:
        """
        Record a successful delivery for idempotency tracking.
        """
        intent_id = intent_data.get("intent_id", "")
        if not intent_id:
            return
        
        cache_key = f"{endpoint}:{intent_id}"
        with self._cache_lock:
            self._idempotency_cache[cache_key] = (time.time(), intent_id)
            # Move to end (most recent)
            self._idempotency_cache.move_to_end(cache_key)
            
            # Trim cache if too large
            while len(self._idempotency_cache) > self.config.idempotency_cache_size:
                self._idempotency_cache.popitem(last=False)

    # ------------------------------------------------------------------
    # deliver
    # ------------------------------------------------------------------

    def deliver(self, endpoint: str, intent_data: Dict[str, Any]) -> DeliveryResult:
        """
        Deliver *intent_data* to the agent at *endpoint*.

        Returns a DeliveryResult with status, attempts, elapsed time, etc.
        """
        t0 = time.monotonic()

        # --- idempotency check ----------------------------------------
        if self._check_idempotency(endpoint, intent_data):
            return DeliveryResult(
                status=DeliveryStatus.IDEMPOTENT_SKIP,
                attempts=0,
                elapsed_ms=_elapsed(t0),
                error="Duplicate intent delivery prevented by idempotency check",
            )

        # --- file-based agents ----------------------------------------
        if self.is_file_based(endpoint):
            return DeliveryResult(
                status=DeliveryStatus.FILE_BASED_SKIP,
                attempts=0,
                elapsed_ms=_elapsed(t0),
            )

        # --- validate endpoint ----------------------------------------
        url = endpoint.rstrip("/") + "/intent"
        if not url.lower().startswith("http"):
            return DeliveryResult(
                status=DeliveryStatus.FAILED_INVALID_ENDPOINT,
                attempts=0,
                elapsed_ms=_elapsed(t0),
                error=f"Invalid endpoint URL: {endpoint}",
            )

        # --- attempt delivery with retries ----------------------------
        body = json.dumps(intent_data).encode("utf-8")
        last_error = ""

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                    status_code = resp.status
                    resp_body = resp.read().decode("utf-8", errors="replace")
                    resp_body = resp_body[:self.config.max_response_body]

                # Record successful delivery for idempotency
                self._record_delivery(endpoint, intent_data)
                
                return DeliveryResult(
                    status=DeliveryStatus.DELIVERED,
                    attempts=attempt,
                    elapsed_ms=_elapsed(t0),
                    http_status=status_code,
                    response_body=resp_body,
                )

            except urllib.error.HTTPError as exc:
                # 4xx / 5xx — no retry
                resp_body = ""
                try:
                    resp_body = exc.read().decode("utf-8", errors="replace")
                    resp_body = resp_body[:self.config.max_response_body]
                except Exception:
                    pass
                return DeliveryResult(
                    status=DeliveryStatus.FAILED_HTTP,
                    attempts=attempt,
                    elapsed_ms=_elapsed(t0),
                    http_status=exc.code,
                    response_body=resp_body,
                    error=f"HTTP {exc.code}: {exc.reason}",
                )

            except urllib.error.URLError as exc:
                # Connection-level error — retry with backoff
                last_error = str(exc.reason)
                if attempt < self.config.max_attempts:
                    backoff = self.config.base_backoff_s * (2 ** (attempt - 1))
                    time.sleep(backoff)

            except TimeoutError:
                return DeliveryResult(
                    status=DeliveryStatus.FAILED_TIMEOUT,
                    attempts=attempt,
                    elapsed_ms=_elapsed(t0),
                    error="Request timed out",
                )

            except OSError as exc:
                # Socket-level error — retry with backoff
                last_error = str(exc)
                if attempt < self.config.max_attempts:
                    backoff = self.config.base_backoff_s * (2 ** (attempt - 1))
                    time.sleep(backoff)

        # Exhausted retries
        return DeliveryResult(
            status=DeliveryStatus.FAILED_CONNECTION,
            attempts=self.config.max_attempts,
            elapsed_ms=_elapsed(t0),
            error=last_error,
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _elapsed(t0: float) -> float:
    return round((time.monotonic() - t0) * 1000, 2)


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

DEFAULT_DELIVERY_ENGINE = IntentDeliveryEngine()
