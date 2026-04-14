"""
SIMP Monitoring Dashboard — Read-Only FastAPI Backend

Proxies existing SIMP broker endpoints (port 5555) for safe public exposure.
All routes are GET-only. No write operations. No secrets exposed.

Run:
    python dashboard/server.py
    # or: uvicorn dashboard.server:app --host 0.0.0.0 --port 8050
"""

import asyncio
import contextlib
import copy
import json
import logging
import os
import re
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Set

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import operator API
from dashboard.operator_api import router as operator_router

# Try to import mesh dashboard
try:
    from dashboard.mesh_dashboard import MeshDashboard
    MESH_DASHBOARD_AVAILABLE = True
    logger.info("MeshDashboard available for mesh visualization")
except ImportError:
    MESH_DASHBOARD_AVAILABLE = False
    logger.warning("MeshDashboard not available. Mesh visualization will be limited.")

# Configure logging
logger = logging.getLogger(__name__)
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:5555")
PROJECTX_GUARD_URL = os.environ.get("PROJECTX_GUARD_URL", "http://127.0.0.1:8771")
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8050"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))  # seconds
BROKER_CACHE_TTL = float(os.environ.get("BROKER_CACHE_TTL", str(max(POLL_INTERVAL * 2, 10))))
BROKER_NEGATIVE_CACHE_TTL = float(os.environ.get("BROKER_NEGATIVE_CACHE_TTL", "30"))
BROKER_SNAPSHOT_INTENTS = int(os.environ.get("BROKER_SNAPSHOT_INTENTS", "50"))
# BROKER_DASHBOARD_PATH = f"/dashboard?public=1&intents={BROKER_SNAPSHOT_INTENTS}"  # HTML endpoint, not JSON
BROKER_DASHBOARD_PATH = "/agents"  # JSON endpoint for agent data
ACTIVITY_BUFFER_SIZE = 100
ACTIVITY_LOG_PATH = Path(__file__).parent / "activity_log.jsonl"
OPERATOR_LOG_PATH = Path(__file__).parent / "operator_events.jsonl"

# Comma-separated list of allowed CORS origins.
# Default "*" is acceptable for a GET-only public dashboard but can be
# tightened per deployment via DASHBOARD_CORS_ORIGINS env var.
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("DASHBOARD_CORS_ORIGINS", "*").split(",")
    if o.strip()
]

# Fields that must never appear in public responses
SENSITIVE_KEYS = frozenset({
    "api_key", "api_secret", "secret", "token", "password", "credential",
    "private_key", "access_token", "refresh_token", "auth",
})
_STRING_REDACTION_PATTERNS = (
    (
        re.compile(r"(?i)\b((?:x-[a-z0-9-]*api-key|authorization)\s*:\s*)([^\"\n\r]+)(?=\")"),
        lambda match: f"{match.group(1)}<redacted>",
    ),
    (
        re.compile(r"(?i)\b((?:x-[a-z0-9-]*api-key|authorization)\s*:\s*)([^\s`]+)"),
        lambda match: f"{match.group(1)}<redacted>",
    ),
    (
        re.compile(r"\b([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*=\s*)(['\"]?)([^'\"\s`]+)(\2)", re.IGNORECASE),
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>{match.group(4)}",
    ),
    (
        re.compile(r"(?i)\b(Bearer\s+)([A-Za-z0-9._:-]+)"),
        lambda match: f"{match.group(1)}<redacted>",
    ),
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _broker_client, _projectx_client
    http_limits = httpx.Limits(max_connections=8, max_keepalive_connections=4, keepalive_expiry=30.0)
    _broker_client = httpx.AsyncClient(
        base_url=BROKER_URL,
        timeout=httpx.Timeout(5.0),
        limits=http_limits,
    )
    _projectx_client = httpx.AsyncClient(
        base_url=PROJECTX_GUARD_URL,
        timeout=httpx.Timeout(30.0),
        limits=http_limits,
    )
    _load_persisted_events()
    task = asyncio.create_task(_poll_broker())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if _broker_client is not None:
            await _broker_client.aclose()
        if _projectx_client is not None:
            await _projectx_client.aclose()
        _broker_client = None
        _projectx_client = None


app = FastAPI(
    title="SIMP Dashboard",
    description="Public read-only monitoring dashboard for the SIMP broker.",
    version="1.0.0",
    docs_url=None,   # disable Swagger UI in production
    redoc_url=None,
    lifespan=lifespan,
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Include operator API router
app.include_router(operator_router)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

activity_buffer: deque[dict] = deque(maxlen=ACTIVITY_BUFFER_SIZE)
_last_snapshot: dict[str, Any] = {}
_started_at = datetime.now(timezone.utc).isoformat()
DASHBOARD_VERSION = "1.4.1"
_broker_client: httpx.AsyncClient | None = None
_projectx_client: httpx.AsyncClient | None = None
_broker_cache: dict[str, dict[str, Any]] = {}

# Active WebSocket connections
_ws_clients: Set[WebSocket] = set()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact(obj: Any) -> Any:
    """Recursively strip sensitive keys and endpoint URLs from a data structure."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            lower_k = k.lower()
            if any(s in lower_k for s in SENSITIVE_KEYS):
                continue
            if lower_k == "endpoint" and isinstance(v, str):
                # Replace actual URL with just the mode indicator
                if v.startswith("http"):
                    cleaned[k] = "http"
                elif v == "":
                    cleaned[k] = "file-based"
                elif v.startswith("/") or v.startswith("file"):
                    cleaned[k] = "file-based"
                else:
                    cleaned[k] = "redacted"
            elif lower_k in ("file_path", "filepath", "path", "local_path"):
                continue
            elif lower_k in ("prompt", "raw_prompt", "prompt_body"):
                continue
            else:
                cleaned[k] = _redact(v)
        return cleaned
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    if isinstance(obj, str):
        redacted = obj
        for pattern, repl in _STRING_REDACTION_PATTERNS:
            redacted = pattern.sub(repl, redacted)
        return redacted
    return obj


def _cache_ttl_for_path(path: str) -> float:
    if path.startswith(("/tasks", "/routing", "/logs")):
        return BROKER_NEGATIVE_CACHE_TTL
    return BROKER_CACHE_TTL


def _cached_entry_fresh(entry: dict[str, Any] | None, ttl: float) -> bool:
    if not entry:
        return False
    return (time.monotonic() - float(entry.get("timestamp", 0))) < ttl


async def _broker_cached_get(
    path: str,
    *,
    ttl: float | None = None,
    force_refresh: bool = False,
    allow_stale: bool = True,
) -> dict | None:
    ttl = _cache_ttl_for_path(path) if ttl is None else ttl
    cached = _broker_cache.get(path)
    if not force_refresh and _cached_entry_fresh(cached, ttl):
        if cached.get("missing"):
            return None
        return copy.deepcopy(cached.get("data"))

    client = _broker_client
    if client is None:
        if allow_stale and cached and cached.get("data") is not None:
            return copy.deepcopy(cached.get("data"))
        return None

    try:
        resp = await client.get(path)
        if resp.status_code == 404:
            _broker_cache[path] = {
                "timestamp": time.monotonic(),
                "data": None,
                "missing": True,
            }
            return None
        resp.raise_for_status()
        data = resp.json()
        _broker_cache[path] = {
            "timestamp": time.monotonic(),
            "data": data,
            "missing": False,
        }
        return copy.deepcopy(data)
    except Exception:
        if allow_stale and cached and cached.get("data") is not None:
            return copy.deepcopy(cached.get("data"))
        return None


async def _broker_snapshot(*, force_refresh: bool = False) -> dict[str, dict | None]:
    # Get multiple data points from broker
    agents_data, stats_data, health_data = await asyncio.gather(
        _broker_cached_get("/agents", force_refresh=force_refresh),
        _broker_cached_get("/stats", force_refresh=force_refresh),
        _broker_cached_get("/health", force_refresh=force_refresh),
    )
    
    # Combine into dashboard data structure
    dashboard_data = {
        "agents": agents_data.get("agents", {}) if agents_data else {},
        "stats": stats_data if stats_data else {},
        "health": health_data if health_data else {}
    }
    
    return {"dashboard": dashboard_data, "health": health_data}


async def _broker_get(path: str) -> dict | None:
    return await _broker_cached_get(path)


async def _broker_post(path: str, payload: dict[str, Any]) -> dict | None:
    try:
        client = _broker_client
        if client is None:
            return None
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def _projectx_get(path: str) -> dict | None:
    try:
        client = _projectx_client
        if client is None:
            return None
        resp = await client.get(path)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def _projectx_post(path: str, payload: dict) -> dict | None:
    try:
        client = _projectx_client
        if client is None:
            return None
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _append_operator_event(
    *,
    request_id: str,
    intent_type: str | None,
    action_type: str,
    status: str,
    summary: str,
    source_agent: str = "dashboard_ui",
    target_agent: str = "projectx_native",
    latency_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _redact(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "intent_type": intent_type,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "action_type": action_type,
            "status": status,
            "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
            "summary": summary,
            "details": details or {},
        }
    )
    OPERATOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OPERATOR_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")
    return payload


def _tail_operator_events(limit: int = 25) -> list[dict]:
    if limit <= 0 or not OPERATOR_LOG_PATH.exists():
        return []
    try:
        lines = OPERATOR_LOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(_redact(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return rows[::-1]


def _detect_changes(old_snapshot: dict, new_snapshot: dict) -> list[dict]:
    """Compare two broker snapshots and produce activity events for changes."""
    events: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    # Detect agent count changes
    old_count = old_snapshot.get("agents_online", 0)
    new_count = new_snapshot.get("agents_online", 0)
    if old_count != new_count:
        events.append({
            "timestamp": now,
            "event_type": "agent_count_change",
            "source_agent": "broker",
            "target_agent": "system",
            "intent_type": "health",
            "delivery_status": "delivered",
            "result": f"Agents online: {old_count} → {new_count}",
            "redacted": True,
        })

    # Detect intent routing changes
    old_routed = old_snapshot.get("intents_routed", 0)
    new_routed = new_snapshot.get("intents_routed", 0)
    if new_routed > old_routed:
        diff = new_routed - old_routed
        events.append({
            "timestamp": now,
            "event_type": "intents_routed",
            "source_agent": "broker",
            "target_agent": "various",
            "intent_type": "routing",
            "delivery_status": "delivered",
            "result": f"{diff} intent(s) routed",
            "redacted": True,
        })

    old_failed = old_snapshot.get("intents_failed", 0)
    new_failed = new_snapshot.get("intents_failed", 0)
    if new_failed > old_failed:
        diff = new_failed - old_failed
        events.append({
            "timestamp": now,
            "event_type": "intents_failed",
            "source_agent": "broker",
            "target_agent": "various",
            "intent_type": "routing",
            "delivery_status": "failed",
            "result": f"{diff} intent(s) failed",
            "redacted": True,
        })

    # Detect delivery status changes from intent records
    old_delivery = old_snapshot.get("delivery_counts", {})
    new_delivery = new_snapshot.get("delivery_counts", {})
    for status_key in ("queued_no_endpoint", "connection_refused", "timeout", "rate_limited"):
        old_val = old_delivery.get(status_key, 0)
        new_val = new_delivery.get(status_key, 0)
        if new_val > old_val:
            diff = new_val - old_val
            events.append({
                "timestamp": now,
                "event_type": f"delivery_{status_key}",
                "source_agent": "broker",
                "target_agent": "various",
                "intent_type": "delivery",
                "delivery_status": status_key,
                "result": f"{diff} intent(s) {status_key}",
                "redacted": True,
            })

    # Detect broker state changes
    old_state = old_snapshot.get("broker_state")
    new_state = new_snapshot.get("broker_state")
    if old_state and new_state and old_state != new_state:
        events.append({
            "timestamp": now,
            "event_type": "broker_state_change",
            "source_agent": "broker",
            "target_agent": "system",
            "intent_type": "control",
            "delivery_status": "delivered",
            "result": f"Broker state: {old_state} → {new_state}",
            "redacted": True,
        })

    return events


def _flatten_snapshot(dashboard_data: dict | None, health_data: dict | None) -> dict:
    """Build a flat snapshot dict from broker dashboard and health responses."""
    snap: dict[str, Any] = {}
    if dashboard_data:
        broker = dashboard_data.get("broker", {})
        snap["agents_online"] = broker.get("agents_online", 0)
        snap["broker_state"] = broker.get("status", "unknown")
        snap["intents_routed"] = broker.get("routed", 0)
        snap["intents_failed"] = broker.get("failed", 0)
        snap["intents_received"] = broker.get("total_intents", 0)
        snap["delivery_counts"] = _recent_delivery_counts(
            broker,
            _dashboard_recent_intents(dashboard_data, limit=25),
        )
    if health_data:
        snap["agents_online"] = health_data.get("agents_online", 0)
        snap["broker_state"] = health_data.get("state", "paused" if health_data.get("paused") else "running")
    return snap


def _dashboard_agents(dashboard_data: dict | None) -> list[dict]:
    if not dashboard_data:
        return []
    agents = dashboard_data.get("agents", [])
    if isinstance(agents, dict):
        return list(agents.values())
    if isinstance(agents, list):
        return agents
    return []


def _queue_depth(agent_queues: Any) -> int:
    if not isinstance(agent_queues, dict):
        return 0
    return sum(value for value in agent_queues.values() if isinstance(value, int))


def _normalize_recent_intent(intent: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    intent_id = str(intent.get("id") or intent.get("intent_id") or "")
    source_agent = str(intent.get("source_agent") or intent.get("source") or "unknown")
    target_agent = str(intent.get("target_agent") or intent.get("target") or "unknown")
    intent_type = str(intent.get("intent_type") or intent.get("event_type") or "intent")
    delivery_status = str(intent.get("delivery_status") or "unknown")
    timestamp = intent.get("timestamp") or intent.get("delivered_at") or generated_at
    intent_ref = intent_id[:12] if intent_id else "unknown"

    return {
        "intent_id": intent_id,
        "timestamp": timestamp,
        "source_agent": source_agent,
        "target_agent": target_agent,
        "intent_type": intent_type,
        "event_type": intent_type,
        "delivery_status": delivery_status,
        "delivery_latency_ms": intent.get("delivery_latency_ms"),
        "retry_count": intent.get("retry_count"),
        "fallback_agent": intent.get("fallback_agent"),
        "result": f"{source_agent} -> {target_agent} ({intent_ref})",
        "redacted": True,
    }


def _dashboard_recent_intents(
    dashboard_data: dict | None,
    *,
    limit: int = 25,
    newest_first: bool = True,
) -> list[dict[str, Any]]:
    if not dashboard_data or limit <= 0:
        return []
    raw_intents = dashboard_data.get("recent_intents", [])
    if not isinstance(raw_intents, list):
        return []

    trimmed = raw_intents[:limit]
    if not newest_first:
        trimmed = list(reversed(trimmed))

    generated_at = dashboard_data.get("generated_at")
    return [_normalize_recent_intent(intent, generated_at=generated_at) for intent in trimmed]


def _recent_delivery_counts(
    broker_data: dict[str, Any], recent_deliveries: list[dict[str, Any]]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for delivery in recent_deliveries:
        status = str(delivery.get("delivery_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1

    counts["delivered"] = int(broker_data.get("routed", counts.get("delivered", 0)) or 0)
    counts["failed"] = int(broker_data.get("failed", counts.get("failed", 0)) or 0)
    counts["queued"] = _queue_depth(broker_data.get("agent_queues", {}))

    for status in ("queued_no_endpoint", "connection_refused", "timeout", "rate_limited"):
        counts.setdefault(status, 0)

    return counts


def _dashboard_stats_payload(dashboard_data: dict | None) -> dict | None:
    if not dashboard_data:
        return None
    broker = dashboard_data.get("broker", {})
    queue_depth = _queue_depth(broker.get("agent_queues", {}))
    recent_deliveries = _dashboard_recent_intents(dashboard_data, limit=10)
    delivery_counts = _recent_delivery_counts(broker, recent_deliveries)
    return {
        "broker": {
            "state": broker.get("status", "unknown"),
            "stats": {
                "agents_online": broker.get("agents_online", 0),
                "pending_intents": queue_depth,
                "intents_received": broker.get("total_intents", 0),
                "intents_routed": broker.get("routed", 0),
                "intents_failed": broker.get("failed", 0),
                "delivery_counts": delivery_counts,
                "recent_deliveries": recent_deliveries,
            },
        },
        "dashboard_started_at": _started_at,
    }


def _recent_intent_events(dashboard_data: dict | None) -> list[dict]:
    if not dashboard_data:
        return []
    return _dashboard_recent_intents(dashboard_data, limit=25, newest_first=False)


async def _broker_intent_detail(intent_id: str) -> tuple[dict | None, str]:
    path = f"/intents/{intent_id}"
    cached = _broker_cache.get(path)

    if _cached_entry_fresh(cached, BROKER_CACHE_TTL):
        if cached.get("missing"):
            return None, "not_found"
        return copy.deepcopy(cached.get("data")), "success"

    client = _broker_client
    if client is None:
        if cached and cached.get("data") is not None:
            return copy.deepcopy(cached.get("data")), "stale"
        return None, "unreachable"

    try:
        resp = await client.get(path)
        if resp.status_code == 404:
            _broker_cache[path] = {
                "timestamp": time.monotonic(),
                "data": None,
                "missing": True,
            }
            return None, "not_found"
        resp.raise_for_status()
        data = resp.json()
        _broker_cache[path] = {
            "timestamp": time.monotonic(),
            "data": data,
            "missing": False,
        }
        return copy.deepcopy(data), "success"
    except Exception:
        if cached and cached.get("data") is not None:
            return copy.deepcopy(cached.get("data")), "stale"
        return None, "unreachable"


async def _broker_failed_intents(limit: int = 50) -> dict[str, Any] | None:
    limit = max(1, min(limit, 200))
    return await _broker_get(f"/intents/failed?limit={limit}")


def _summarize_failed_intents(intents: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_target_agent: dict[str, int] = {}
    latest_failure_at = None

    for intent in intents:
        status = str(intent.get("delivery_status") or "unknown")
        target = str(intent.get("target_agent") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_target_agent[target] = by_target_agent.get(target, 0) + 1
        timestamp = intent.get("delivered_at") or intent.get("timestamp")
        if timestamp and (latest_failure_at is None or str(timestamp) > str(latest_failure_at)):
            latest_failure_at = timestamp

    return {
        "count": len(intents),
        "latest_failure_at": latest_failure_at,
        "by_status": by_status,
        "by_target_agent": by_target_agent,
    }


def _normalize_intent_detail(intent: dict[str, Any] | None, *, lookup_status: str = "success") -> dict[str, Any]:
    payload = dict(intent or {})
    intent_id = str(payload.get("id") or payload.get("intent_id") or "")
    delivery_status = str(payload.get("delivery_status") or "unknown")
    failure_reason = payload.get("failure_reason")
    if not failure_reason and delivery_status not in ("delivered", "pending"):
        failure_reason = delivery_status

    lifecycle = payload.get("lifecycle")
    if not isinstance(lifecycle, list):
        lifecycle = []
    route_attempts = payload.get("route_attempts")
    if not isinstance(route_attempts, list):
        route_attempts = []
    correlation_ids = payload.get("correlation_ids")
    if not isinstance(correlation_ids, dict):
        correlation_ids = {}
    fallback_behavior = payload.get("fallback_behavior")
    if not isinstance(fallback_behavior, dict):
        fallback_behavior = {}

    correlation_ids.setdefault("broker_intent_id", intent_id or None)
    correlation_ids.setdefault("correlation_id", correlation_ids.get("request_id") or intent_id or None)
    fallback_behavior.setdefault("mode", "unknown" if delivery_status != "delivered" else "none")
    fallback_behavior.setdefault("queued_for_polling", False)
    fallback_behavior.setdefault("dlq_eligible", False)
    fallback_behavior.setdefault("fallback_agent", None)

    return {
        "intent_id": intent_id,
        "timestamp": payload.get("timestamp"),
        "delivered_at": payload.get("delivered_at"),
        "source_agent": payload.get("source_agent", "unknown"),
        "target_agent": payload.get("target_agent", "unknown"),
        "intent_type": payload.get("intent_type", "intent"),
        "delivery_status": delivery_status,
        "failure_reason": failure_reason or ("unknown" if delivery_status != "delivered" else None),
        "delivery_response": payload.get("delivery_response"),
        "lookup_status": lookup_status,
        "correlation_ids": correlation_ids,
        "fallback_behavior": fallback_behavior,
        "route_attempts": route_attempts,
        "lifecycle": lifecycle,
        "summary": f"{payload.get('source_agent', 'unknown')} -> {payload.get('target_agent', 'unknown')}",
        "raw_intent": payload,
    }


async def _broker_registry_agents() -> list[dict[str, Any]]:
    data = await _broker_get("/agents")
    agents = data.get("agents", []) if isinstance(data, dict) else []
    if isinstance(agents, list):
        return agents
    if isinstance(agents, dict):
        return list(agents.values())
    return []


async def _broker_list_intents(limit: int = 50, *, failed_only: bool = False) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    path = f"/intents?limit={limit}"
    if failed_only:
        path += "&failed=1"
    data = await _broker_get(path)
    intents = data.get("intents", []) if isinstance(data, dict) else []
    if isinstance(intents, list):
        return intents
    return []


def _task_status_from_delivery(delivery_status: str) -> str:
    status = str(delivery_status or "unknown")
    if status in {"delivered", "ok", "success"}:
        return "completed"
    if status in {"pending", "queued", "queued_no_endpoint"}:
        return "queued"
    if status in {"connection_refused", "timeout", "rate_limited"} or status.startswith("http_") or status.startswith("error_"):
        return "failed"
    return status


def _task_priority_from_delivery(delivery_status: str) -> str:
    status = str(delivery_status or "unknown")
    if status in {"connection_refused", "timeout", "rate_limited"} or status.startswith("http_") or status.startswith("error_"):
        return "high"
    if status == "queued_no_endpoint":
        return "medium"
    return "normal"


def _task_from_intent(intent: dict[str, Any]) -> dict[str, Any]:
    intent_id = str(intent.get("id") or intent.get("intent_id") or "")
    delivery_status = str(intent.get("delivery_status") or "unknown")
    task_status = _task_status_from_delivery(delivery_status)
    source_agent = str(intent.get("source_agent") or "unknown")
    target_agent = str(intent.get("target_agent") or "unknown")
    intent_type = str(intent.get("intent_type") or "intent")
    reason = intent.get("failure_reason")
    title = f"{source_agent} -> {target_agent} ({intent_type})"
    if reason:
        title = f"{title}: {reason}"
    return {
        "task_id": intent_id,
        "title": title,
        "task_type": intent_type,
        "priority": _task_priority_from_delivery(delivery_status),
        "status": task_status,
        "assigned_agent": target_agent,
        "claimed_by": target_agent,
        "created_at": intent.get("timestamp") or intent.get("delivered_at"),
        "delivery_status": delivery_status,
        "failure_reason": reason,
        "source_agent": source_agent,
    }


def _derived_task_payload(intents: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = [_task_from_intent(intent) for intent in intents]
    failure_stats: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for task in tasks:
        status = str(task.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "failed":
            failure_key = str(task.get("failure_reason") or task.get("delivery_status") or "unknown")
            failure_stats[failure_key] = failure_stats.get(failure_key, 0) + 1
    return {
        "status": "success",
        "broker_url_reachable": True,
        "source": "derived_intents",
        "tasks": tasks,
        "count": len(tasks),
        "failure_stats": failure_stats,
        "status_counts": status_counts,
    }


def _derived_routing_payload(agents: list[dict[str, Any]]) -> dict[str, Any]:
    task_routing: dict[str, list[str]] = {}
    stale_agents: list[str] = []
    for agent in agents:
        agent_id = str(agent.get("agent_id") or agent.get("name") or "unknown")
        if agent.get("stale"):
            stale_agents.append(agent_id)
        for capability in agent.get("capabilities", []) or []:
            task_routing.setdefault(str(capability), []).append(agent_id)
    for capability, agent_ids in task_routing.items():
        task_routing[capability] = sorted(agent_ids)

    support = [agent_id for agent_id in ("projectx_native", "kashclaw_gemma") if any(agent_id in ids for ids in task_routing.values())]
    builder_pool = {
        "primary": "gemma4_local" if any("gemma4_local" in ids for ids in task_routing.values()) else None,
        "secondary": "claude_cowork" if any("claude_cowork" in ids for ids in task_routing.values()) else None,
        "support": support,
    }
    return {
        "status": "success",
        "broker_url_reachable": True,
        "source": "derived_capabilities",
        "policy": {
            "task_routing": task_routing,
            "builder_pool": builder_pool,
        },
        "pool_status": {
            "agent_count": len(agents),
            "stale_count": len(stale_agents),
            "stale_agents": stale_agents[:10],
        },
    }


def _derived_memory_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for task in tasks[:25]:
        rows.append(
            {
                "slug": str(task.get("task_id") or "")[:12],
                "title": task.get("title"),
                "status": task.get("status"),
            }
        )
    return {
        "status": "success",
        "broker_url_reachable": True,
        "source": "derived_task_memory",
        "tasks": rows,
        "count": len(rows),
    }


def _derived_memory_conversations(limit: int = 20) -> dict[str, Any]:
    conversations: list[dict[str, Any]] = []
    for event in _tail_operator_events(limit=limit * 3):
        request_id = event.get("request_id")
        if not request_id:
            continue
        conversations.append(
            {
                "id": request_id,
                "topic": event.get("summary") or event.get("intent_type") or "operator_event",
                "participants": [event.get("source_agent") or "dashboard_ui", event.get("target_agent") or "projectx_native"],
                "created_at": event.get("timestamp"),
            }
        )
        if len(conversations) >= limit:
            break
    return {
        "status": "success",
        "broker_url_reachable": True,
        "source": "derived_operator_events",
        "conversations": conversations,
        "count": len(conversations),
    }


def _flow_group_key(intent: dict[str, Any]) -> str | None:
    correlation = intent.get("correlation_ids") if isinstance(intent.get("correlation_ids"), dict) else {}
    plan_id = correlation.get("plan_id")
    source_intent_id = correlation.get("source_intent_id")
    correlation_id = correlation.get("correlation_id")
    broker_intent_id = correlation.get("broker_intent_id") or intent.get("id")
    if plan_id:
        return f"plan:{plan_id}"
    if source_intent_id:
        return f"source:{source_intent_id}"
    if correlation_id and correlation_id != broker_intent_id:
        return f"corr:{correlation_id}"
    return None


def _flow_phase(intent: dict[str, Any]) -> str:
    intent_type = str(intent.get("intent_type") or "").lower()
    target_agent = str(intent.get("target_agent") or "").lower()
    if intent_type in {"planning", "research", "architecture", "docs", "spec"}:
        return "planner"
    if target_agent in {"gemma4_local", "kashclaw_gemma"}:
        return "planner"
    if intent_type.startswith("native_agent_") or target_agent == "projectx_native":
        return "executor"
    return "linked"


def _flow_intent_view(intent: dict[str, Any]) -> dict[str, Any]:
    correlation = intent.get("correlation_ids") if isinstance(intent.get("correlation_ids"), dict) else {}
    return {
        "intent_id": intent.get("id") or intent.get("intent_id"),
        "source_agent": intent.get("source_agent"),
        "target_agent": intent.get("target_agent"),
        "intent_type": intent.get("intent_type"),
        "delivery_status": intent.get("delivery_status"),
        "timestamp": intent.get("timestamp"),
        "delivered_at": intent.get("delivered_at"),
        "phase": _flow_phase(intent),
        "plan_id": correlation.get("plan_id"),
        "source_intent_id": correlation.get("source_intent_id"),
        "correlation_id": correlation.get("correlation_id"),
    }


def _derived_flow_payload(intents: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for intent in intents:
        key = _flow_group_key(intent)
        if not key:
            continue
        grouped.setdefault(key, []).append(intent)

    flows: list[dict[str, Any]] = []
    for flow_id, rows in grouped.items():
        rows = sorted(rows, key=lambda row: row.get("timestamp") or "")
        planner = next((row for row in rows if _flow_phase(row) == "planner"), rows[0] if rows else None)
        executors = [row for row in rows if _flow_phase(row) == "executor"]
        statuses = sorted({str(row.get("delivery_status") or "unknown") for row in rows})
        last_updated = max((row.get("delivered_at") or row.get("timestamp") or "") for row in rows)
        flows.append(
            {
                "flow_id": flow_id,
                "intent_count": len(rows),
                "last_updated": last_updated,
                "statuses": statuses,
                "planner_intent": _flow_intent_view(planner) if planner else None,
                "executor_intents": [_flow_intent_view(row) for row in executors],
                "linked_intents": [_flow_intent_view(row) for row in rows],
            }
        )
    flows.sort(key=lambda row: row.get("last_updated") or "", reverse=True)
    return {
        "status": "success",
        "broker_url_reachable": True,
        "source": "derived_intent_flows",
        "count": len(flows),
        "flows": flows,
    }


def _persist_events(events: list[dict]) -> None:
    """Append events to the JSONL log file."""
    import json
    try:
        with open(ACTIVITY_LOG_PATH, "a") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")
    except OSError:
        pass  # non-critical


def _load_persisted_events() -> None:
    """Load events from the JSONL log file into the ring buffer on startup."""
    import json
    if not ACTIVITY_LOG_PATH.exists():
        return
    try:
        with open(ACTIVITY_LOG_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    activity_buffer.append(event)
                except json.JSONDecodeError:
                    continue  # Skip corrupt line, don't abort
    except OSError:
        pass


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time dashboard updates."""
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=35.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        logger.debug(f"WebSocket client disconnected: {websocket.client}")
    except asyncio.CancelledError:
        logger.debug(f"WebSocket task cancelled: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error for client {websocket.client}: {e}", exc_info=True)
    finally:
        _ws_clients.discard(websocket)
        logger.debug(f"WebSocket client removed: {websocket.client}. Active clients: {len(_ws_clients)}")


async def _broadcast_ws(event_type: str, data: dict):
    """Broadcast an event to all connected WebSocket clients."""
    if not _ws_clients:
        return
    
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    
    for ws in _ws_clients:
        try:
            await ws.send_text(message)
        except WebSocketDisconnect:
            disconnected.add(ws)
            logger.debug(f"WebSocket client disconnected during broadcast: {ws.client}")
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message to {ws.client}: {e}")
            disconnected.add(ws)
    
    if disconnected:
        _ws_clients -= disconnected
        logger.debug(f"Removed {len(disconnected)} disconnected WebSocket clients. Active: {len(_ws_clients)}")


# ---------------------------------------------------------------------------
# Background poller
# ---------------------------------------------------------------------------

async def _poll_broker() -> None:
    """Periodically poll the broker and record state changes."""
    global _last_snapshot
    while True:
        snapshot = await _broker_snapshot(force_refresh=True)
        dashboard_data = snapshot["dashboard"]
        health_data = snapshot["health"]
        new_snap = _flatten_snapshot(dashboard_data, health_data)
        if _last_snapshot and new_snap:
            events = _detect_changes(_last_snapshot, new_snap)
            if events:
                activity_buffer.extend(events)
                _persist_events(events)
                # Broadcast changes to WebSocket clients
                if _ws_clients:
                    stats_payload = _dashboard_stats_payload(dashboard_data)
                    if stats_payload:
                        await _broadcast_ws("stats", _redact(stats_payload))
                    if dashboard_data:
                        await _broadcast_ws("agents", _redact({
                            "agents": _dashboard_agents(dashboard_data),
                            "count": len(_dashboard_agents(dashboard_data)),
                        }))
                    await _broadcast_ws("activity", {
                        "status": "success",
                        "count": len(activity_buffer),
                        "events": list(activity_buffer),
                    })
        if new_snap:
            _last_snapshot = new_snap
        await asyncio.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# API routes — ALL GET-only
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def api_health():
    """Health check with real data."""
    snapshot = await _broker_snapshot()
    dashboard_data = snapshot["dashboard"]
    health_data = snapshot["health"]
    broker_up = dashboard_data is not None or health_data is not None
    broker_state = "unreachable"
    agents_registered = 0
    if dashboard_data:
        broker = dashboard_data.get("broker", {})
        broker_state = broker.get("status", broker_state)
        agents_registered = broker.get("agents_online", 0)
    if health_data:
        broker_state = health_data.get("state", "paused" if health_data.get("paused") else broker_state)
        agents_registered = max(agents_registered, health_data.get("agents_online", 0))

    return {
        "status": "healthy" if broker_up else "degraded",
        "broker_reachable": broker_up,
        "dashboard_version": DASHBOARD_VERSION,
        "broker_state": broker_state,
        "agents_registered": agents_registered,
        "uptime_seconds": 0,
    }


@app.get("/health")
async def health_alias():
    """Compatibility alias for ProjectX and operator health probes."""
    return await api_health()


@app.get("/api/stats")
async def api_stats():
    """Broker statistics."""
    snapshot = await _broker_snapshot()
    data = _dashboard_stats_payload(snapshot["dashboard"])
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "dashboard_started_at": _started_at,
        }
    return _redact(data)


@app.get("/api/agents")
async def api_agents():
    """Registered agents list (redacted)."""
    snapshot = await _broker_snapshot()
    agents = _dashboard_agents(snapshot["dashboard"])
    if snapshot["dashboard"] is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "agents": {},
            "count": 0,
        }
    return _redact({"agents": agents, "count": len(agents)})


@app.get("/api/activity")
async def api_activity():
    """Recent activity feed from the broker ledger, with local fallback."""
    snapshot = await _broker_snapshot()
    events = _recent_intent_events(snapshot["dashboard"])
    if events:
        return {
            "status": "success",
            "count": len(events),
            "events": events,
        }
    return {
        "status": "success",
        "count": len(activity_buffer),
        "events": list(activity_buffer),
    }


@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 25):
    """Read-only recent broker intent tail for dashboard panels and drill-downs."""
    limit = max(1, min(limit, 100))
    snapshot = await _broker_snapshot()
    if snapshot["dashboard"] is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "intents": [],
            "count": 0,
        }

    intents = _dashboard_recent_intents(snapshot["dashboard"], limit=limit)
    return {
        "status": "success",
        "count": len(intents),
        "intents": _redact(intents),
    }


@app.get("/api/intents/failed")
async def api_intents_failed(limit: int = 50):
    """Failed intent aggregates with recent drill-down rows."""
    broker_payload = await _broker_failed_intents(limit=limit)
    if broker_payload is not None:
        intents = [
            _normalize_intent_detail(intent, lookup_status="success")
            for intent in broker_payload.get("intents", [])
        ]
        summary = broker_payload.get("summary") or _summarize_failed_intents(intents)
        return _redact({
            "status": "success",
            "summary": summary,
            "intents": intents,
            "count": len(intents),
        })

    snapshot = await _broker_snapshot()
    intents = [
        _normalize_intent_detail(intent, lookup_status="snapshot")
        for intent in _dashboard_recent_intents(snapshot["dashboard"], limit=limit)
        if str(intent.get("delivery_status") or "unknown") not in ("delivered", "pending")
    ]
    return _redact({
        "status": "success" if intents else "unreachable",
        "summary": _summarize_failed_intents(intents),
        "intents": intents,
        "count": len(intents),
    })


@app.get("/api/intents/{intent_id}")
async def api_intent_detail(intent_id: str):
    """Proxy broker intent lookups for safe dashboard drill-downs."""
    data, lookup_status = await _broker_intent_detail(intent_id)
    if data is None:
        return {
            "status": lookup_status,
            "intent_id": intent_id,
            "detail": _redact(_normalize_intent_detail({"intent_id": intent_id}, lookup_status=lookup_status)),
        }
    return {
        "status": lookup_status,
        "intent": _redact(data),
        "detail": _redact(_normalize_intent_detail(data, lookup_status=lookup_status)),
    }


@app.get("/api/capabilities")
async def api_capabilities():
    """Capability map: which agents handle which capabilities."""
    snapshot = await _broker_snapshot()
    agents = _dashboard_agents(snapshot["dashboard"])
    if snapshot["dashboard"] is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "capabilities": {},
        }
    cap_map: dict[str, list[str]] = {}
    for agent in agents:
        agent_id = agent.get("agent_id", "unknown")
        caps = agent.get("capabilities", [])
        if isinstance(caps, list):
            for cap in caps:
                cap_map.setdefault(cap, []).append(agent_id)
    return {
        "status": "success",
        "capabilities": cap_map,
    }


@app.get("/api/topology")
async def api_topology():
    """Network topology showing agents and their connection modes."""
    snapshot = await _broker_snapshot()
    agents = _dashboard_agents(snapshot["dashboard"])
    if snapshot["dashboard"] is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "nodes": [],
            "edges": [],
        }
    nodes = [{"id": "broker", "label": "SIMP Broker", "type": "broker"}]
    edges = []
    for agent in agents:
        agent_id = agent.get("agent_id", "unknown")
        endpoint = agent.get("endpoint", "")
        connection_mode = agent.get("connection_mode", agent.get("mode",
            "http" if isinstance(endpoint, str) and endpoint.startswith("http") else "file-based"))
        nodes.append({
            "id": agent_id,
            "label": agent.get("name", agent_id),
            "type": "agent",
            "connection_mode": connection_mode,
            "status": agent.get("status", "unknown"),
            "capabilities": agent.get("capabilities", []),
        })
        edges.append({
            "source": "broker",
            "target": agent_id,
            "connection_mode": connection_mode,
        })
    return {
        "status": "success",
        "nodes": nodes,
        "edges": edges,
    }


@app.get("/api/agents/smoke")
async def api_agents_smoke():
    """Live broker-side reachability sweep for registered HTTP agents."""
    data = await _broker_get("/agents/smoke")
    if data is not None:
        return _redact(data)

    agents = await _broker_registry_agents()
    if not agents:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "results": [],
            "count": 0,
        }
    results = []
    for agent in agents:
        endpoint = str(agent.get("endpoint") or "")
        if endpoint not in {"http", "file-based"} and endpoint.startswith("http"):
            health_url = f"{endpoint.rstrip('/')}/health"
        elif str(agent.get("connection_mode") or "") == "http":
            health_url = "registered-http-endpoint"
        else:
            continue
        results.append(
            {
                "agent_id": agent.get("agent_id"),
                "health_url": health_url,
                "reachable": not bool(agent.get("stale")),
                "error": None if not agent.get("stale") else "Agent appears stale from registry snapshot",
            }
        )
    return {
        "status": "success",
        "broker_url_reachable": True,
        "source": "derived_registry_health",
        "results": results,
        "count": len(results),
    }


@app.get("/api/flows")
async def api_flows(limit: int = 50):
    """Planner/executor and correlated broker flow chains."""
    limit = max(1, min(limit, 200))
    data = await _broker_get(f"/intents/flows?limit={limit}")
    if data is not None:
        return _redact(data)

    intents = await _broker_list_intents(limit=limit)
    return _redact(_derived_flow_payload(intents))


@app.get("/api/tasks")
async def api_tasks():
    """Task ledger view — lists all tasks with failure stats."""
    data = await _broker_get("/tasks")
    if data is None:
        failed_intents = await _broker_list_intents(limit=25, failed_only=True)
        recent_intents = await _broker_list_intents(limit=25)
        derived_intents = failed_intents or recent_intents
        if not derived_intents:
            snapshot = await _broker_snapshot()
            derived_intents = [
                _normalize_intent_detail(intent, lookup_status="snapshot")
                for intent in _dashboard_recent_intents(snapshot["dashboard"], limit=25)
            ]
        return _redact(_derived_task_payload(derived_intents))
    return _redact(data)


@app.get("/api/tasks/queue")
async def api_task_queue():
    """Unclaimed task queue ordered by priority."""
    data = await _broker_get("/tasks/queue")
    if data is None:
        intents = await _broker_list_intents(limit=25)
        queue = [
            _task_from_intent(intent)
            for intent in intents
            if _task_status_from_delivery(str(intent.get("delivery_status") or "unknown")) == "queued"
        ]
        return _redact({
            "status": "success",
            "broker_url_reachable": True,
            "source": "derived_intents",
            "queue": queue,
            "count": len(queue),
        })
    return _redact(data)


@app.get("/api/routing")
async def api_routing():
    """Routing policy and builder pool status."""
    data = await _broker_get("/routing/policy")
    if data is None:
        agents = await _broker_registry_agents()
        if not agents:
            snapshot = await _broker_snapshot()
            agents = _dashboard_agents(snapshot["dashboard"])
        return _redact(_derived_routing_payload(agents))
    return _redact(data)


@app.get("/api/orchestration")
async def api_orchestration():
    """Orchestration status — real data from broker."""
    snapshot = await _broker_snapshot()
    dashboard_data = snapshot["dashboard"]
    if dashboard_data is None:
        return {"status": "unreachable", "orchestration_active": False}
    broker = dashboard_data.get("broker", {})
    agent_queues = broker.get("agent_queues", {})
    task_count = 0
    if isinstance(agent_queues, dict):
        task_count = sum(value for value in agent_queues.values() if isinstance(value, int))

    return {
        "status": "success",
        "orchestration_active": broker.get("status", "").lower() == "running",
        "queue_depth": task_count,
        "intents_routed": broker.get("routed", 0),
        "intents_completed": broker.get("routed", 0),
        "intents_failed": broker.get("failed", 0),
    }


@app.get("/api/computer-use")
async def api_computer_use():
    """ProjectX computer-use status — dynamic from broker."""
    snapshot = await _broker_snapshot()
    if snapshot["dashboard"] is None:
        return {"status": "unreachable", "projectx_available": False}
    projectx_info = snapshot["dashboard"].get("projectx", {})

    return {
        "status": "success",
        "projectx_available": bool(projectx_info) or True,
        "action_tiers": projectx_info.get("action_tiers", {
            "tier_0_observation": ["get_screenshot", "get_active_window", "ocr_screen", "snapshot_state"],
            "tier_1_gui": ["click", "double_click", "type_text", "press", "scroll", "focus_app"],
            "tier_2_shell": ["run_shell"],
            "tier_3_restricted": [],
        }),
        "action_count": projectx_info.get("action_count", 0),
        "log_path": projectx_info.get("log_path", ""),
    }


@app.get("/api/logs")
async def api_logs(limit: int = 100):
    """Structured broker event logs."""
    limit = max(1, min(limit, 500))
    data = await _broker_get(f"/logs?limit={limit}")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "logs": [],
            "count": 0,
        }
    return _redact(data)


@app.get("/api/projectx/system")
async def api_projectx_system():
    data = await _projectx_get("/system/status")
    if data is None:
        return {"status": "unreachable", "projectx_guard_reachable": False}
    return _redact(data)


@app.get("/api/projectx/processes")
async def api_projectx_processes():
    data = await _projectx_get("/system/status")
    if data is None:
        return {"status": "unreachable", "services": []}
    return {
        "status": "success",
        "services": _redact(data.get("stack", {}).get("services", [])),
        "summary": _redact(data.get("stack", {}).get("summary", {})),
        "startup_command": data.get("stack", {}).get("startup_command"),
        "restart_command": data.get("stack", {}).get("restart_command"),
    }


@app.get("/api/projectx/actions")
async def api_projectx_actions():
    data = await _projectx_get("/actions")
    if data is None:
        return {"status": "unreachable", "actions": []}
    return _redact(data)


@app.get("/api/projectx/protocol-facts")
async def api_projectx_protocol_facts():
    data = await _projectx_get("/protocol-facts")
    if data is None:
        return {"status": "unreachable", "protocol_facts": {}}
    return _redact(data)


@app.get("/api/projectx/events")
async def api_projectx_events():
    data = await _projectx_get("/events")
    if data is None:
        return {"status": "unreachable", "events": []}
    return _redact(data)


@app.get("/api/projectx/chat/history")
async def api_projectx_chat_history():
    return {"status": "success", "events": _tail_operator_events(limit=20)}


@app.get("/api/projectx/chat")
async def api_projectx_chat(
    message: str = "",
    job: str = "",
    request_id: str = "",
    source_intent_id: str = "",
    plan_id: str = ""
):
    message = message.strip()
    job = job.strip() or None
    request_id = request_id.strip() or str(uuid.uuid4())
    source_intent_id = source_intent_id.strip() or None
    plan_id = plan_id.strip() or None
    started = time.time()
    
    if not message and not job:
        return {"status": "error", "error": "message_or_job_required"}

    if job:
        allowed_jobs = {
            "native_agent_health_check": {"intent_type": "native_agent_health_check", "params": {"quick": True}},
            "native_agent_repo_scan": {"intent_type": "native_agent_repo_scan", "params": {"sync_protocol_facts": True}},
            "native_agent_task_audit": {"intent_type": "native_agent_task_audit", "params": {"quick": True}},
            "native_agent_security_audit": {"intent_type": "native_agent_security_audit", "params": {"persist": True}},
        }
        if job not in allowed_jobs:
            return {"status": "error", "error": "job_not_allowed", "job": job}
        payload = {
            "source_agent": "dashboard_ui",
            "target_agent": "projectx_native",
            "intent_type": allowed_jobs[job]["intent_type"],
            "params": {
                **allowed_jobs[job]["params"],
                "request_id": request_id,
                "source_intent_id": source_intent_id,
                "plan_id": plan_id,
                "source_agent": "dashboard_ui",
            },
        }
        _append_operator_event(
            request_id=request_id,
            intent_type=job,
            action_type="dashboard.job_request",
            status="received",
            summary=f"Dashboard requested {job}",
            details={"job": job, "source_intent_id": source_intent_id, "plan_id": plan_id},
        )
        broker_response = await _broker_post("/intents/route", payload)
        routing_mode = "broker" if broker_response is not None else "direct"
        response = broker_response.get("delivery_response") if broker_response is not None else None
        if broker_response is None:
            direct_payload = {
                "intent_id": request_id,
                "source_agent": "dashboard_ui",
                "target_agent": "projectx_native",
                "intent_type": allowed_jobs[job]["intent_type"],
                "params": payload["params"],
            }
            response = await _projectx_post("/intents/handle", direct_payload)
        latency_ms = (time.time() - started) * 1000
        _append_operator_event(
            request_id=request_id,
            intent_type=job,
            action_type="dashboard.job_result",
            status="ok" if response else "error",
            summary=f"Dashboard job completed: {job}",
            latency_ms=latency_ms,
            details={
                "response": response or {"status": "unreachable"},
                "routing_mode": routing_mode,
                "broker_intent_id": broker_response.get("intent_id") if broker_response else None,
                "delivery_status": broker_response.get("delivery_status") if broker_response else None,
            },
        )
        return {
            "status": "success" if response else "unreachable",
            "mode": "job",
            "routing_mode": routing_mode,
            "broker_intent_id": broker_response.get("intent_id") if broker_response else None,
            "delivery_status": broker_response.get("delivery_status") if broker_response else None,
            "response": _redact(response),
        }

    payload = {
        "source_agent": "dashboard_ui",
        "target_agent": "projectx_native",
        "intent_type": "projectx_query",
        "params": {
            "question": message,
            "source_agent": "dashboard_ui",
            "request_id": request_id,
            "source_intent_id": source_intent_id,
            "plan_id": plan_id,
        },
    }
    _append_operator_event(
        request_id=request_id,
        intent_type="projectx_query",
        action_type="dashboard.query_received",
        status="received",
        summary=message[:120],
        details={"message": message[:200], "source_intent_id": source_intent_id, "plan_id": plan_id},
    )
    broker_response = await _broker_post("/intents/route", payload)
    routing_mode = "broker" if broker_response is not None else "direct"
    response = broker_response.get("delivery_response") if broker_response is not None else None
    if broker_response is None:
        direct_payload = {
            "intent_id": request_id,
            "source_agent": "dashboard_ui",
            "target_agent": "projectx_native",
            "intent_type": "projectx_query",
            "params": payload["params"],
        }
        response = await _projectx_post("/intents/handle", direct_payload)
    latency_ms = (time.time() - started) * 1000
    _append_operator_event(
        request_id=request_id,
        intent_type="projectx_query",
        action_type="dashboard.query_completed",
        status="ok" if response else "error",
        summary=f"Dashboard query completed for request {request_id}",
        latency_ms=latency_ms,
        details={
            "response": response or {"status": "unreachable"},
            "routing_mode": routing_mode,
            "broker_intent_id": broker_response.get("intent_id") if broker_response else None,
            "delivery_status": broker_response.get("delivery_status") if broker_response else None,
        },
    )
    return {
        "status": "success" if response else "unreachable",
        "mode": "query",
        "routing_mode": routing_mode,
        "broker_intent_id": broker_response.get("intent_id") if broker_response else None,
        "delivery_status": broker_response.get("delivery_status") if broker_response else None,
        "response": _redact(response),
    }


# ---------------------------------------------------------------------------
# Memory Layer proxy endpoints (GET-only, safe for public exposure)
# ---------------------------------------------------------------------------

@app.get("/api/memory/tasks")
async def api_memory_tasks():
    """Task memory files from the memory layer."""
    data = await _broker_get("/memory/tasks")
    if data is None:
        tasks_payload = await api_tasks()
        tasks = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
        return _redact(_derived_memory_tasks(tasks))
    return _redact(data)


@app.get("/api/memory/conversations")
async def api_memory_conversations():
    """Conversation archive from the memory layer."""
    data = await _broker_get("/memory/conversations")
    if data is None:
        return _redact(_derived_memory_conversations())
    return _redact(data)


# ---------------------------------------------------------------------------
# Mesh Bus Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/mesh/stats")
async def api_mesh_stats():
    """Get mesh bus statistics."""
    if not MESH_DASHBOARD_AVAILABLE:
        return {"error": "Mesh dashboard not available", "status": "unavailable"}
    
    try:
        dashboard = MeshDashboard()
        stats = dashboard.fetch_mesh_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Error fetching mesh stats: {e}")
        return {"error": str(e), "status": "error"}


@app.get("/api/mesh/channels")
async def api_mesh_channels():
    """Get mesh channel information."""
    if not MESH_DASHBOARD_AVAILABLE:
        return {"error": "Mesh dashboard not available", "status": "unavailable"}
    
    try:
        dashboard = MeshDashboard()
        channels = dashboard.fetch_channel_data()
        core_channels = dashboard._get_core_channels_info()
        return {
            "status": "success",
            "data": {
                "channels": channels,
                "core_channels": core_channels
            }
        }
    except Exception as e:
        logger.error(f"Error fetching mesh channels: {e}")
        return {"error": str(e), "status": "error"}


@app.get("/api/mesh/events")
async def api_mesh_events(limit: int = 50):
    """Get recent mesh events."""
    if not MESH_DASHBOARD_AVAILABLE:
        return {"error": "Mesh dashboard not available", "status": "unavailable"}
    
    try:
        dashboard = MeshDashboard()
        events = dashboard.fetch_recent_events(limit=limit)
        return {"status": "success", "events": events}
    except Exception as e:
        logger.error(f"Error fetching mesh events: {e}")
        return {"error": str(e), "status": "error"}


@app.get("/api/mesh/dashboard")
async def api_mesh_dashboard():
    """Get complete mesh dashboard data."""
    if not MESH_DASHBOARD_AVAILABLE:
        return {"error": "Mesh dashboard not available", "status": "unavailable"}
    
    try:
        dashboard = MeshDashboard()
        data = dashboard.get_dashboard_data()
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error fetching mesh dashboard data: {e}")
        return {"error": str(e), "status": "error"}


@app.get("/api/mesh/widget")
async def api_mesh_widget():
    """Get HTML widget for mesh dashboard."""
    if not MESH_DASHBOARD_AVAILABLE:
        return {"error": "Mesh dashboard not available", "status": "unavailable"}
    
    try:
        dashboard = MeshDashboard()
        html = dashboard.generate_html_widget()
        return HTMLResponse(html)
    except Exception as e:
        logger.error(f"Error generating mesh widget: {e}")
        return {"error": str(e), "status": "error"}


@app.post("/api/mesh/test-alert")
async def api_mesh_test_alert(request: Request):
    """Send a test alert to mesh bus."""
    try:
        data = await request.json()
        channel = data.get("channel", "safety_alerts")
        message = data.get("message", "Test alert from dashboard")
        
        # Send test alert via broker
        alert_payload = {
            "sender_id": "dashboard",
            "recipient_id": "*",
            "channel": channel,
            "msg_type": "event",
            "payload": {
                "alert_type": "test_alert",
                "severity": "INFO",
                "message": message,
                "source": "dashboard",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recommended_action": "none"
            },
            "priority": "normal",
            "ttl_hops": 10,
            "ttl_seconds": 60
        }
        
        # Send to broker
        broker_response = await _broker_post("/mesh/send", alert_payload)
        
        if broker_response and broker_response.get("success"):
            return {"success": True, "message_id": broker_response.get("message_id")}
        else:
            error = broker_response.get("error", "Unknown error") if broker_response else "No response from broker"
            return {"success": False, "error": error}
            
    except Exception as e:
        logger.error(f"Error sending test alert: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/mesh/export")
async def api_mesh_export():
    """Export mesh data for analysis."""
    if not MESH_DASHBOARD_AVAILABLE:
        return {"error": "Mesh dashboard not available", "status": "unavailable"}
    
    try:
        dashboard = MeshDashboard()
        
        # Get all data
        stats = dashboard.fetch_mesh_stats()
        channels = dashboard.fetch_channel_data()
        events = dashboard.fetch_recent_events(limit=1000)
        dashboard_data = dashboard.get_dashboard_data()
        
        export_data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "channels": channels,
            "events": events,
            "dashboard_data": dashboard_data,
            "export_format": "simp_mesh_v1"
        }
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting mesh data: {e}")
        return {"error": str(e), "status": "error"}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------------
# Sprint 56 — _broker_get helper (stdlib urllib, no requests dependency)
# ---------------------------------------------------------------------------

def _broker_get(path: str, default=None, timeout: float = 3.0):
    """Fetch JSON from the SIMP broker via stdlib urllib.

    Returns parsed JSON on success, *default* on any error.
    Uses only stdlib — no ``requests`` or ``httpx`` dependency.
    """
    import urllib.request
    import urllib.error

    url = f"{BROKER_URL.rstrip('/')}{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body) if body else default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Sprint 56 — Unified A2A / FinancialOps dashboard endpoints
# ---------------------------------------------------------------------------

@app.get("/dashboard/a2a/status")
async def dashboard_a2a_status():
    """A2A compatibility status for the dashboard."""
    agents_data = _broker_get("/agents", default={"agents": []})
    agents_list = agents_data.get("agents", []) if isinstance(agents_data, dict) else []

    return {
        "a2a_capable_agents": agents_list,
        "quota_status": {
            "a2a_route_limit": "30 req/min",
            "payload_limit": "64KB",
        },
        "enforcement_status": {
            "schema_validation": "enabled",
            "rate_limiting": "enabled",
            "payload_limits": "enabled",
            "replay_protection": "planned",
        },
    }


@app.get("/dashboard/financial-ops/status")
async def dashboard_financial_ops_status():
    """FinancialOps connector health and mode status."""
    health = _broker_get("/a2a/agents/financial-ops/connector-health", default={})
    return {
        "mode": "dry_run",
        "live_payments_enabled": False,
        "health": health,
    }


@app.get("/dashboard/financial-ops/proposals")
async def dashboard_financial_ops_proposals():
    """Proposals for dashboard display."""
    data = _broker_get("/a2a/agents/financial-ops/proposals", default={"proposals": [], "count": 0})
    if not isinstance(data, dict):
        data = {"proposals": [], "count": 0}
    return data


@app.get("/dashboard/financial-ops/ledger")
async def dashboard_financial_ops_ledger():
    """Combined ledger for dashboard display."""
    data = _broker_get("/a2a/agents/financial-ops/ledger", default={"simulated": {}, "live": {}})
    if not isinstance(data, dict):
        data = {"simulated": {}, "live": {}}
    return data


@app.get("/dashboard/financial-ops/rollback")
async def dashboard_financial_ops_rollback():
    """Rollback status for dashboard display."""
    data = _broker_get("/a2a/agents/financial-ops/rollback/status", default={"state": "unknown"})
    if not isinstance(data, dict):
        data = {"state": "unknown"}
    return data


@app.get("/dashboard/financial-ops/budget")
async def dashboard_financial_ops_budget():
    """Budget summary for dashboard display."""
    data = _broker_get("/a2a/agents/financial-ops/budget", default={})
    if not isinstance(data, dict):
        data = {}
    return data


@app.get("/dashboard/financial-ops/gates")
async def dashboard_financial_ops_gates():
    """Gate status for dashboard display."""
    data = _broker_get("/a2a/agents/financial-ops/gates", default={})
    if not isinstance(data, dict):
        data = {}
    return data


# Mount static files AFTER explicit routes so /api/* is not shadowed
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        log_level="info",
    )
