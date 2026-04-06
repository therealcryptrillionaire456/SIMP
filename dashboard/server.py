"""
SIMP Dashboard Server — Sprint S8 (Sprint 38)

FastAPI-based dashboard with A2A Compatibility panel.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

logger = logging.getLogger("SIMP.Dashboard")

# Regex for secret redaction
_STRING_REDACTION_PATTERNS = [
    "api_key", "token", "secret", "password", "credential", "bearer", "private_key",
]

app = FastAPI(title="SIMP Dashboard")


def _escape_html(s: str) -> str:
    """Escape HTML special characters."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Broker reference (set at startup)
# ---------------------------------------------------------------------------
_broker = None


def set_broker(broker: Any) -> None:
    global _broker
    _broker = broker


# ---------------------------------------------------------------------------
# A2A status endpoint
# ---------------------------------------------------------------------------

@app.get("/dashboard/a2a/status")
def a2a_status():
    """Return A2A compatibility status for the dashboard."""
    from simp.compat.policy_map import get_agent_security_schemes

    agents_list: List[Dict[str, Any]] = []

    if _broker and hasattr(_broker, "agents"):
        for aid, info in _broker.agents.items():
            agent_type = info.get("agent_type", "unknown")
            schemes = get_agent_security_schemes(info)
            status = "active" if info.get("status") == "online" else "inactive"
            if agent_type == "financial_ops":
                status = "planned"
            agents_list.append({
                "agent_id": aid,
                "agent_type": agent_type,
                "security_schemes": schemes,
                "resource_limits": {},
                "status": status,
            })

    # Recent A2A tasks (last 10 from intent records)
    recent_tasks: List[Dict[str, Any]] = []
    if _broker and hasattr(_broker, "intent_records"):
        records = list(_broker.intent_records.values())[-10:]
        for rec in records:
            recent_tasks.append({
                "intent_id": rec.intent_id,
                "intent_type": rec.intent_type,
                "status": rec.status,
                "timestamp": rec.timestamp,
            })

    return JSONResponse({
        "a2a_capable_agents": agents_list,
        "recent_a2a_tasks": recent_tasks,
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
    })


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(html_path, "r") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>SIMP Dashboard</h1><p>index.html not found.</p>")
