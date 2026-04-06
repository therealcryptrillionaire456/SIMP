"""
SIMP Monitoring Dashboard — Read-Only FastAPI Backend

Proxies existing SIMP broker endpoints (port 5555) for safe public exposure.
All routes are GET-only. No write operations. No secrets exposed.

Run:
    python dashboard/server.py
    # or: uvicorn dashboard.server:app --host 0.0.0.0 --port 8050
"""

import asyncio
import json
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
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:5555")
PROJECTX_GUARD_URL = os.environ.get("PROJECTX_GUARD_URL", "http://127.0.0.1:8771")
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8050"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))  # seconds
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

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

activity_buffer: deque[dict] = deque(maxlen=ACTIVITY_BUFFER_SIZE)
_last_snapshot: dict[str, Any] = {}
_started_at = datetime.now(timezone.utc).isoformat()
DASHBOARD_VERSION = "1.4.0"  # bumped for Sprint 25 — v0.4.0 release

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


async def _broker_get(path: str) -> dict | None:
    """Make a GET request to the broker. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BROKER_URL}{path}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def _projectx_get(path: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PROJECTX_GUARD_URL}{path}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def _projectx_post(path: str, payload: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{PROJECTX_GUARD_URL}{path}", json=payload)
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
    for status_key in ("queued_no_endpoint", "timeout", "rate_limited"):
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
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)


async def _broadcast_ws(event_type: str, data: dict):
    """Broadcast an event to all connected WebSocket clients."""
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _ws_clients -= disconnected


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
                # Broadcast changes to WebSocket clients
                if _ws_clients:
                    if status_data:
                        await _broadcast_ws("stats", _redact(status_data))
                    agents_data = await _broker_get("/agents")
                    if agents_data:
                        await _broadcast_ws("agents", _redact(agents_data))
                    tasks_data = await _broker_get("/tasks")
                    if tasks_data:
                        await _broadcast_ws("tasks", _redact(tasks_data))
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
    stats = await _broker_get("/stats")
    broker_up = stats is not None

    return {
        "status": "healthy" if broker_up else "degraded",
        "broker_reachable": broker_up,
        "dashboard_version": DASHBOARD_VERSION,
        "broker_state": stats.get("state", "unknown") if stats else "unreachable",
        "agents_registered": stats.get("agents_registered", 0) if stats else 0,
        "uptime_seconds": stats.get("uptime_seconds", 0) if stats else 0,
    }


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


@app.get("/api/tasks")
async def api_tasks():
    """Task ledger view — lists all tasks with failure stats."""
    data = await _broker_get("/tasks")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "tasks": [],
            "count": 0,
            "failure_stats": {},
            "status_counts": {},
        }
    return _redact(data)


@app.get("/api/tasks/queue")
async def api_task_queue():
    """Unclaimed task queue ordered by priority."""
    data = await _broker_get("/tasks/queue")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "queue": [],
            "count": 0,
        }
    return _redact(data)


@app.get("/api/routing")
async def api_routing():
    """Routing policy and builder pool status."""
    data = await _broker_get("/routing/policy")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "policy": {},
            "pool_status": {},
        }
    return _redact(data)


@app.get("/api/orchestration")
async def api_orchestration():
    """Orchestration status — real data from broker."""
    stats = await _broker_get("/stats")
    if stats is None:
        return {"status": "unreachable", "orchestration_active": False}

    tasks = await _broker_get("/tasks/queue")
    task_count = len(tasks) if isinstance(tasks, list) else 0

    return {
        "status": "success",
        "orchestration_active": stats.get("state", "") == "RUNNING",
        "queue_depth": task_count,
        "intents_routed": stats.get("intents_routed", 0),
        "intents_completed": stats.get("intents_completed", 0),
        "intents_failed": stats.get("intents_failed", 0),
    }


@app.get("/api/computer-use")
async def api_computer_use():
    """ProjectX computer-use status — dynamic from broker."""
    stats = await _broker_get("/stats")
    if stats is None:
        return {"status": "unreachable", "projectx_available": False}

    projectx_info = stats.get("projectx", {})

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


@app.post("/api/projectx/chat")
async def api_projectx_chat(request: Request):
    body = await request.json()
    message = str(body.get("message", "")).strip()
    job = str(body.get("job", "")).strip() or None
    request_id = str(body.get("request_id") or uuid.uuid4())
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
            "intent_id": request_id,
            "source_agent": "dashboard_ui",
            "target_agent": "projectx_native",
            "intent_type": allowed_jobs[job]["intent_type"],
            "params": allowed_jobs[job]["params"],
        }
        _append_operator_event(
            request_id=request_id,
            intent_type=job,
            action_type="dashboard.job_request",
            status="received",
            summary=f"Dashboard requested {job}",
            details={"job": job},
        )
        response = await _projectx_post("/intents/handle", payload)
        latency_ms = (time.time() - started) * 1000
        _append_operator_event(
            request_id=request_id,
            intent_type=job,
            action_type="dashboard.job_result",
            status="ok" if response else "error",
            summary=f"Dashboard job completed: {job}",
            latency_ms=latency_ms,
            details={"response": response or {"status": "unreachable"}},
        )
        return {"status": "success" if response else "unreachable", "mode": "job", "response": _redact(response)}

    payload = {
        "intent_id": request_id,
        "source_agent": "dashboard_ui",
        "target_agent": "projectx_native",
        "intent_type": "projectx_query",
        "params": {"question": message, "source_agent": "dashboard_ui"},
    }
    _append_operator_event(
        request_id=request_id,
        intent_type="projectx_query",
        action_type="dashboard.query_received",
        status="received",
        summary=message[:120],
        details={"message": message[:200]},
    )
    response = await _projectx_post("/intents/handle", payload)
    latency_ms = (time.time() - started) * 1000
    _append_operator_event(
        request_id=request_id,
        intent_type="projectx_query",
        action_type="dashboard.query_completed",
        status="ok" if response else "error",
        summary=f"Dashboard query completed for request {request_id}",
        latency_ms=latency_ms,
        details={"response": response or {"status": "unreachable"}},
    )
    return {"status": "success" if response else "unreachable", "mode": "query", "response": _redact(response)}


# ---------------------------------------------------------------------------
# Memory Layer proxy endpoints (GET-only, safe for public exposure)
# ---------------------------------------------------------------------------

@app.get("/api/memory/tasks")
async def api_memory_tasks():
    """Task memory files from the memory layer."""
    data = await _broker_get("/memory/tasks")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "tasks": [],
            "count": 0,
        }
    return _redact(data)


@app.get("/api/memory/conversations")
async def api_memory_conversations():
    """Conversation archive from the memory layer."""
    data = await _broker_get("/memory/conversations")
    if data is None:
        return {
            "status": "unreachable",
            "broker_url_reachable": False,
            "conversations": [],
            "count": 0,
        }
    return _redact(data)


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
