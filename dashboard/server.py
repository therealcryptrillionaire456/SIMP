"""
SIMP Monitoring Dashboard — Read-Only FastAPI Backend

Proxies existing SIMP broker endpoints (port 5555) for safe public exposure.
All routes are GET-only. No write operations. No secrets exposed.

Run:
    python dashboard/server.py
    # or: uvicorn dashboard.server:app --host 0.0.0.0 --port 8050
"""

import asyncio
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:5555")
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8050"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))  # seconds
ACTIVITY_BUFFER_SIZE = 100
ACTIVITY_LOG_PATH = Path(__file__).parent / "activity_log.jsonl"

# Fields that must never appear in public responses
SENSITIVE_KEYS = frozenset({
    "api_key", "api_secret", "secret", "token", "password", "credential",
    "private_key", "access_token", "refresh_token", "auth",
})

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI):
    _load_persisted_events()
    task = asyncio.create_task(_poll_broker())
    yield
    task.cancel()


app = FastAPI(
    title="SIMP Dashboard",
    description="Public read-only monitoring dashboard for the SIMP broker.",
    version="1.0.0",
    docs_url=None,   # disable Swagger UI in production
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

activity_buffer: deque[dict] = deque(maxlen=ACTIVITY_BUFFER_SIZE)
_last_snapshot: dict[str, Any] = {}
_started_at = datetime.now(timezone.utc).isoformat()

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
    return obj


async def _broker_get(path: str) -> dict | None:
    """Make a GET request to the broker. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BROKER_URL}{path}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


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


def _flatten_snapshot(status_data: dict | None, health_data: dict | None) -> dict:
    """Build a flat snapshot dict from broker /status and /health responses."""
    snap: dict[str, Any] = {}
    if health_data:
        snap["agents_online"] = health_data.get("agents_online", 0)
        snap["broker_state"] = health_data.get("state", "paused" if health_data.get("paused") else "running")
    if status_data:
        # Handle both nested {broker:{stats:{...}}} and flat structures
        broker = status_data.get("broker", status_data)
        stats = broker.get("stats", broker)
        snap["intents_routed"] = stats.get("intents_routed", 0)
        snap["intents_failed"] = stats.get("intents_failed", 0)
        snap["intents_received"] = stats.get("intents_received", 0)
        if stats.get("agents_online") is not None:
            snap["agents_online"] = stats["agents_online"]
        snap["broker_state"] = broker.get("state", snap.get("broker_state", "unknown"))
    return snap


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
                if line:
                    activity_buffer.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass


# ---------------------------------------------------------------------------
# Background poller
# ---------------------------------------------------------------------------

async def _poll_broker() -> None:
    """Periodically poll the broker and record state changes."""
    global _last_snapshot
    while True:
        status_data = await _broker_get("/status")
        health_data = await _broker_get("/health")
        new_snap = _flatten_snapshot(status_data, health_data)
        if _last_snapshot and new_snap:
            events = _detect_changes(_last_snapshot, new_snap)
            if events:
                activity_buffer.extend(events)
                _persist_events(events)
        if new_snap:
            _last_snapshot = new_snap
        await asyncio.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# API routes — ALL GET-only
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def api_health():
    """Broker health status."""
    data = await _broker_get("/health")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "dashboard_started_at": _started_at,
            "message": "Broker is not responding.",
        }
    return _redact(data)


@app.get("/api/stats")
async def api_stats():
    """Broker statistics."""
    data = await _broker_get("/status")
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
    data = await _broker_get("/agents")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "agents": {},
            "count": 0,
        }
    return _redact(data)


@app.get("/api/activity")
async def api_activity():
    """Recent activity feed from the in-memory ring buffer."""
    return {
        "status": "success",
        "count": len(activity_buffer),
        "events": list(activity_buffer),
    }


@app.get("/api/capabilities")
async def api_capabilities():
    """Capability map: which agents handle which capabilities."""
    data = await _broker_get("/agents")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "capabilities": {},
        }
    agents = data.get("agents", [])
    if isinstance(agents, dict):
        agents = list(agents.values())
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
    data = await _broker_get("/agents")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "nodes": [],
            "edges": [],
        }
    agents = data.get("agents", [])
    if isinstance(agents, dict):
        agents = list(agents.values())
    nodes = [{"id": "broker", "label": "SIMP Broker", "type": "broker"}]
    edges = []
    for agent in agents:
        agent_id = agent.get("agent_id", "unknown")
        endpoint = agent.get("endpoint", "")
        mode = "http" if isinstance(endpoint, str) and endpoint.startswith("http") else "file-based"
        nodes.append({
            "id": agent_id,
            "label": agent.get("name", agent_id),
            "type": "agent",
            "mode": mode,
            "capabilities": agent.get("capabilities", []),
        })
        edges.append({
            "source": "broker",
            "target": agent_id,
            "mode": mode,
        })
    return {
        "status": "success",
        "nodes": nodes,
        "edges": edges,
    }


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


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
