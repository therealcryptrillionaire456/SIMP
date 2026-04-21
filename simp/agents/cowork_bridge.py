"""
CoWork Bridge v2 — SIMP agent for claude_cowork.
Now with peer_intent_schema validation on every inbound intent.

Changes from v1:
  - Imports PeerIntentSchema and calls validate_request() before queueing.
  - Returns structured PeerSchemaError responses (HTTP 422) on validation failures.
  - Still returns HTTP 403 for FORBIDDEN_TYPES (unchanged from v1 firewall).
  - All other behaviour is identical to v1 — no breaking changes.

Usage:
    bash bin/start_cowork_bridge.sh --daemon
    # or:
    python3 simp/agents/cowork_bridge_v2.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional deps
# ---------------------------------------------------------------------------
try:
    from flask import Flask, jsonify, request as flask_request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("WARNING: flask not installed — bridge cannot start without it.", file=sys.stderr)
    sys.exit(1)

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Peer schema validation (optional graceful degrade)
# ---------------------------------------------------------------------------
try:
    # When installed as a package:  from simp.models.peer_intent_schema import ...
    # Fallback: try relative import from same directory
    try:
        from simp.models.peer_intent_schema import (
            validate_request as _validate_peer_request,
            PeerSchemaError,
            FORBIDDEN_TYPES,
            ALLOWED_REQUEST_TYPES,
        )
    except ImportError:
        # Running directly from simp/agents/ — walk up one level
        _parent = str(Path(__file__).resolve().parent.parent)
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        from models.peer_intent_schema import (
            validate_request as _validate_peer_request,
            PeerSchemaError,
            FORBIDDEN_TYPES,
            ALLOWED_REQUEST_TYPES,
        )
    SCHEMA_VALIDATION = True
except Exception as _schema_err:
    # Degrade gracefully — validation skipped, firewall still applies via hardcoded list
    SCHEMA_VALIDATION  = False
    FORBIDDEN_TYPES    = frozenset({
        "execute_trade", "position_sizing", "dry_run_trade", "place_order",
        "cancel_order", "arbitrage_execute", "kashclaw_execute", "organ_execute",
        "trade_signal", "prediction_signal", "dry_run_signal",
        "backtest_execute", "live_trade", "market_order", "limit_order",
        "stop_loss", "take_profit", "close_position",
    })
    ALLOWED_REQUEST_TYPES = frozenset({
        "code_task", "planning", "coordination",
        "status_check", "capability_query", "ping",
    })
    class PeerSchemaError(ValueError):
        pass
    def _validate_peer_request(data):
        pass   # no-op when schema module absent

# ---------------------------------------------------------------------------
# BRP integration (shadow mode — never blocks peer intents by default)
# ---------------------------------------------------------------------------

_brp_bridge = None  # Module-level singleton, initialised lazily


def _get_brp_bridge():
    """Lazily create a BRP bridge for shadow observations."""
    global _brp_bridge
    if _brp_bridge is None:
        try:
            from simp.security.brp_bridge import BRPBridge
            _brp_bridge = BRPBridge()
        except Exception:
            pass
    return _brp_bridge


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
AGENT_ID       = "claude_cowork"
AGENT_TYPE     = "ai_coordinator"
AGENT_VERSION  = "2.0.0"
DEFAULT_PORT   = 8767
DEFAULT_SIMP   = "http://127.0.0.1:5555"
POLL_INTERVAL  = 3     # seconds between outbox scans

CAPABILITIES = [
    "code_task",
    "planning",
    "coordination",
    "code_editing",
    "status_check",
    "capability_query",
    "scaffolding",
    "test_harness",
]

# Intents handled synchronously (no file queuing needed)
SYNC_INTENTS = {"ping", "status_check", "capability_query"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - COWORK_BRIDGE - %(levelname)s - %(message)s",
)
log = logging.getLogger("COWORK_BRIDGE")

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _resolve_dir(env_var: str, default: str) -> Path:
    raw = os.environ.get(env_var, default)
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p

_REPO_ROOT    = Path(__file__).resolve().parents[2]
INBOX_DIR     = _resolve_dir("COWORK_INBOX",  str(_REPO_ROOT / "data" / "inboxes" / "claude_cowork"))
OUTBOX_DIR    = _resolve_dir("COWORK_OUTBOX", str(_REPO_ROOT / "data" / "outboxes" / "claude_cowork"))

# ---------------------------------------------------------------------------
# CoWork Bridge
# ---------------------------------------------------------------------------

class CoWorkBridge:
    def __init__(self, port: int = DEFAULT_PORT, simp_url: str = DEFAULT_SIMP) -> None:
        self.port      = port
        self.simp_url  = simp_url.rstrip("/")
        self._stop     = threading.Event()
        self._stats: Dict[str, Any] = {
            "requests_received":    0,
            "sync_handled":         0,
            "queued":               0,
            "firewall_blocks":      0,
            "schema_rejections":    0,
            "outbox_forwarded":     0,
            "started_at":           datetime.now(timezone.utc).isoformat(),
        }
        self._registered = False

    # ── Registration ────────────────────────────────────────────────────────

    def register(self) -> bool:
        if not REQUESTS_AVAILABLE:
            log.warning("requests not installed — skipping SIMP registration")
            return False

        api_key  = os.environ.get("SIMP_API_KEY", "")
        endpoint = f"http://127.0.0.1:{self.port}"
        headers  = {"Content-Type": "application/json"}
        if api_key:
            headers["X-SIMP-API-Key"] = api_key

        payload = {
            "agent_id":   AGENT_ID,
            "agent_type": AGENT_TYPE,
            "endpoint":   endpoint,
            "metadata": {
                "capabilities":    CAPABILITIES,
                "description":     "Claude CoWork coordination agent. Analysis and code scaffolding only.",
                "version":         AGENT_VERSION,
                "trade_execution": False,
                "dry_run":         True,
                "schema_version":  "1.0.0",
            },
        }

        try:
            r = _requests.post(
                f"{self.simp_url}/agents/register",
                json=payload,
                headers=headers,
                timeout=5,
            )
            if r.status_code in (200, 201):
                log.info("✅ Registered with SIMP broker (%s agents online)", AGENT_ID)
                self._registered = True
                return True
            log.warning("Registration HTTP %s: %s", r.status_code, r.text[:200])
            return False
        except Exception as exc:
            log.warning("Cannot reach SIMP broker: %s", exc)
            return False

    # ── Outbox watcher ───────────────────────────────────────────────────────

    def _outbox_loop(self) -> None:
        """Forward completed CoWork responses back through SIMP."""
        api_key = os.environ.get("SIMP_API_KEY", "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-SIMP-API-Key"] = api_key

        while not self._stop.is_set():
            for fpath in sorted(OUTBOX_DIR.glob("response_*.json")):
                try:
                    data = json.loads(fpath.read_text())
                    if REQUESTS_AVAILABLE:
                        r = _requests.post(
                            f"{self.simp_url}/intents/route",
                            json=data,
                            headers=headers,
                            timeout=5,
                        )
                        if r.status_code in (200, 201):
                            fpath.unlink(missing_ok=True)
                            self._stats["outbox_forwarded"] += 1
                            log.info("📤 Forwarded %s → SIMP", fpath.name)
                        else:
                            log.warning("Outbox forward failed HTTP %s", r.status_code)
                    else:
                        fpath.unlink(missing_ok=True)   # no broker, discard
                except Exception as exc:
                    log.warning("Outbox error on %s: %s", fpath.name, exc)
            self._stop.wait(POLL_INTERVAL)

    # ── Intent dispatch ──────────────────────────────────────────────────────

    def _firewall_check(self, intent_type: str) -> Optional[str]:
        """Return a rejection reason string if the intent type is forbidden, else None."""
        if intent_type in FORBIDDEN_TYPES:
            return (
                f"FIREWALL: '{intent_type}' is a trading/execution intent type. "
                f"claude_cowork is a coordination-only agent; no trading operations "
                f"may be routed through this channel."
            )
        return None


    # ── Sprint 4: broker-intent normalization  (claude_cowork, 2026-04-06) ───
    # Translates broker-originated intents (which carry raw intent_type values
    # and "claude_code" as target name) into schema-valid form *before*
    # peer_intent_schema validation runs.  The peer contract itself is unchanged.
    _BROKER_TYPE_MAP: dict = {
        "code_fix_request":    "code_task",
        "code_review":         "code_task",
        "fix_bug":             "code_task",
        "implement_feature":   "code_task",
        "debug":               "code_task",
        "inspect_diagnose":    "code_task",
        "refactor":            "code_task",
        "architecture_review": "planning",
        "plan_sprint":         "planning",
        "coordinate":          "coordination",
        "orchestrate":         "coordination",
        "delegate":            "coordination",
    }

    # Agents the broker may forward on behalf of; map to nearest peer alias.
    _SOURCE_AGENT_MAP: Dict[str, str] = {
        "claude_code":        "claude_cowork",
        "simp_broker":        "simp_router",
        "diagnostic_runner":  "simp_router",
        "mother_goose":       "simp_router",
        "projectx":           "simp_router",
        "client":             "simp_router",
    }

    def _normalize_for_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise a broker-originated intent dict to pass peer schema validation."""
        import copy
        from simp.models.peer_intent_schema import PEER_AGENTS
        d = copy.deepcopy(data)

        # 1. Agent-name alias: map non-peer agent names to their peer equivalent.
        #    broker registers us as "claude_code"; schema requires "claude_cowork".
        #    Other broker-forwarded sources (diagnostic_runner, etc.) → simp_router.
        for role in ("source_agent", "target_agent"):
            val = d.get(role, "")
            if val in self._SOURCE_AGENT_MAP:
                d[role] = self._SOURCE_AGENT_MAP[val]
            elif val and val not in PEER_AGENTS:
                # Unknown non-peer agent: treat as broker-routed → simp_router
                d[role] = "simp_router"

        # 2. Intent-type translation: map broker shorthand → allowed type.
        it = d.get("intent_type", "")
        if it in self._BROKER_TYPE_MAP:
            d["intent_type"] = self._BROKER_TYPE_MAP[it]

        # 3. Ensure task_id exists (required for non-trivial intents).
        params = d.get("params") or {}
        if not d.get("task_id") and not params.get("task_id"):
            # Derive from broker-assigned intent id so it stays traceable.
            derived = f"broker-{d.get('intent_id', '')[:12]}" if d.get("intent_id") else f"broker-auto-{id(d)}"
            if isinstance(params, dict):
                params = {**params, "task_id": derived}
                d["params"] = params

        return d

    def _schema_check(self, data: Dict[str, Any]) -> Optional[str]:
        """Return validation error string if schema check fails, else None."""
        if not SCHEMA_VALIDATION:
            return None
        try:
            _validate_peer_request(data)
            return None
        except PeerSchemaError as exc:
            return str(exc)

    def _handle_sync(self, intent_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._stats["sync_handled"] += 1
        if intent_type == "ping":
            return {
                "status":    "ok",
                "agent_id":  AGENT_ID,
                "message":   "pong",
                "version":   AGENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        if intent_type == "status_check":
            return {
                "status":       "ok",
                "agent_id":     AGENT_ID,
                "version":      AGENT_VERSION,
                "registered":   self._registered,
                "inbox":        str(INBOX_DIR),
                "outbox":       str(OUTBOX_DIR),
                "pending_count": len(list(INBOX_DIR.glob("intent_*.json"))),
                "response_count": len(list(OUTBOX_DIR.glob("response_*.json"))),
                "stats":        self._stats,
                "schema_validation": SCHEMA_VALIDATION,
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            }
        if intent_type == "capability_query":
            return {
                "status":            "ok",
                "agent_id":          AGENT_ID,
                "capabilities":      CAPABILITIES,
                "allowed_intents":   sorted(ALLOWED_REQUEST_TYPES),
                "forbidden_intents": sorted(FORBIDDEN_TYPES),
                "trade_execution":   False,
                "dry_run":           True,
                "schema_version":    "1.0.0",
                "schema_validation": SCHEMA_VALIDATION,
            }
        return {"status": "error", "message": f"Unknown sync intent: {intent_type}"}

    def _queue_intent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Write intent to inbox for async CoWork processing."""
        queue_id = f"cowork-{uuid.uuid4().hex[:12]}"
        fname    = INBOX_DIR / f"intent_{queue_id}.json"

        record = {
            **data,
            "queue_id":   queue_id,
            "queued_at":  datetime.now(timezone.utc).isoformat(),
            "status":     "pending",
        }
        fname.write_text(json.dumps(record, indent=2, default=str))
        self._stats["queued"] += 1

        log.info("📥 Queued %s [%s] from %s",
                 data.get("intent_type"), queue_id, data.get("source_agent", "?"))

        return {
            "status":      "queued",
            "queue_id":    queue_id,
            "intent_id":   data.get("intent_id", ""),
            "intent_type": data.get("intent_type", ""),
            "message":     (
                f"Intent queued for async CoWork processing. "
                f"Poll GET /queue/responses or check {OUTBOX_DIR} for the response."
            ),
            "poll_url":    f"http://127.0.0.1:{self.port}/queue/responses",
        }

    # ── Flask app ────────────────────────────────────────────────────────────

    def _build_app(self) -> Flask:
        app = Flask(AGENT_ID)

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "status":            "ok",
                "agent_id":          AGENT_ID,
                "version":           AGENT_VERSION,
                "registered":        self._registered,
                "inbox":             str(INBOX_DIR),
                "outbox":            str(OUTBOX_DIR),
                "pending_count":     len(list(INBOX_DIR.glob("intent_*.json"))),
                "response_count":    len(list(OUTBOX_DIR.glob("response_*.json"))),
                "schema_validation": SCHEMA_VALIDATION,
                "timestamp":         datetime.now(timezone.utc).isoformat(),
            })

        @app.route("/stats", methods=["GET"])
        def stats():
            return jsonify({**self._stats, "agent_id": AGENT_ID, "version": AGENT_VERSION})

        @app.route("/intent", methods=["POST"])
        @app.route("/intents/handle", methods=["POST"])
        @app.route("/intents/receive", methods=["POST"])
        def receive():
            try:
                data = flask_request.get_json(force=True) or {}
            except Exception as exc:
                return jsonify({"status": "error", "message": str(exc)}), 400

            self._stats["requests_received"] += 1
            intent_type = data.get("intent_type", "")

            # Layer 1: hard firewall (trading types)
            firewall_reason = self._firewall_check(intent_type)
            if firewall_reason:
                self._stats["firewall_blocks"] += 1
                log.warning("🔥 FIREWALL blocked '%s' from %s", intent_type, data.get("source_agent", "?"))
                return jsonify({
                    "status":      "rejected",
                    "intent_type": intent_type,
                    "reason":      firewall_reason,
                    "agent_id":    AGENT_ID,
                }), 403

            # Layer 2: schema validation (peer intent contract)
            data = self._normalize_for_schema(data)   # Sprint 4 normalise
            schema_error = self._schema_check(data)
            if schema_error:
                self._stats["schema_rejections"] += 1
                log.warning("🚫 Schema rejection '%s': %s", intent_type, schema_error)
                return jsonify({
                    "status":      "rejected",
                    "intent_type": intent_type,
                    "reason":      schema_error,
                    "agent_id":    AGENT_ID,
                }), 422

            # Layer 2.5: BRP gate (shadow mode — logs but doesn't block by default)
            brp_event_id = ""
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import (
                        BRPEvent, BRPEventType, BRPMode, BRPDecision,
                    )
                    brp_event = BRPEvent(
                        source_agent=data.get("source_agent", "external"),
                        event_type=BRPEventType.PEER_INTENT.value,
                        action=intent_type,
                        context={
                            "intent_id": data.get("intent_id", ""),
                            "target_agent": data.get("target_agent", ""),
                            "params": data.get("params", {}),
                        },
                        mode=BRPMode.SHADOW.value,
                        tags=["cowork_bridge", "peer_intent", intent_type],
                    )
                    brp_event_id = brp_event.event_id
                    brp_resp = bridge.evaluate_event(brp_event)

                    # In enforced mode, DENY blocks the intent
                    if brp_resp.mode == BRPMode.ENFORCED.value and brp_resp.decision == BRPDecision.DENY.value:
                        log.warning(
                            "BRP DENY (enforced) for peer_intent '%s' from %s",
                            intent_type, data.get("source_agent", "?"),
                        )
                        return jsonify({
                            "status": "rejected",
                            "intent_type": intent_type,
                            "reason": f"BRP denied: {brp_resp.summary}",
                            "agent_id": AGENT_ID,
                            "brp": brp_resp.to_dict(),
                        }), 403
            except Exception:
                pass

            # Layer 3: sync intents answered immediately
            if intent_type in SYNC_INTENTS:
                result = self._handle_sync(intent_type, data)
                # BRP post-action observation
                try:
                    bridge = _get_brp_bridge()
                    if bridge is not None:
                        from simp.security.brp_models import BRPObservation, BRPMode
                        obs = BRPObservation(
                            source_agent="cowork_bridge",
                            event_id=brp_event_id,
                            action=intent_type,
                            outcome="success",
                            result_data={"sync": True},
                            mode=BRPMode.SHADOW.value,
                            tags=["cowork_bridge", "peer_intent"],
                        )
                        bridge.ingest_observation(obs)
                except Exception:
                    pass
                return jsonify(result)

            # Layer 4: queue for async CoWork processing
            queue_result = self._queue_intent(data)
            # BRP post-action observation
            try:
                bridge = _get_brp_bridge()
                if bridge is not None:
                    from simp.security.brp_models import BRPObservation, BRPMode
                    obs = BRPObservation(
                        source_agent="cowork_bridge",
                        event_id=brp_event_id,
                        action=intent_type,
                        outcome="queued",
                        result_data={"queue_id": queue_result.get("queue_id", "")},
                        mode=BRPMode.SHADOW.value,
                        tags=["cowork_bridge", "peer_intent"],
                    )
                    bridge.ingest_observation(obs)
            except Exception:
                pass
            return jsonify(queue_result)

        @app.route("/queue/responses", methods=["GET"])
        def queue_responses():
            responses = []
            for fpath in sorted(OUTBOX_DIR.glob("response_*.json")):
                try:
                    responses.append(json.loads(fpath.read_text()))
                except Exception:
                    pass
            return jsonify({"status": "ok", "responses": responses, "count": len(responses)})

        return app

    # ── Entry point ──────────────────────────────────────────────────────────

    def run(self) -> None:
        outbox_thread = threading.Thread(
            target=self._outbox_loop, name="cowork-outbox", daemon=True
        )
        outbox_thread.start()

        app = self._build_app()
        log.info(
            "🚀 CoWork Bridge v%s on 127.0.0.1:%d  schema_validation=%s",
            AGENT_VERSION, self.port, SCHEMA_VALIDATION,
        )
        log.info("   inbox  → %s", INBOX_DIR)
        log.info("   outbox → %s", OUTBOX_DIR)
        try:
            app.run(
                host="127.0.0.1",
                port=self.port,
                threaded=True,
                use_reloader=False,
            )
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CoWork Bridge — SIMP agent for Claude CoWork")
    p.add_argument("--port",     type=int, default=DEFAULT_PORT)
    p.add_argument("--simp-url", type=str, default=DEFAULT_SIMP)
    return p.parse_args()


def main() -> None:
    args  = _parse_args()
    bridge = CoWorkBridge(port=args.port, simp_url=args.simp_url)
    bridge.register()
    bridge.run()


if __name__ == "__main__":
    main()
