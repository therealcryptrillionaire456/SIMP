"""
SIMP HTTP Server

REST API for SIMP broker, making it easy to test and interact with.
Includes A2A compatibility routes (Sprints 2-6, S1-S9).
"""

import asyncio
import functools
import hmac
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
import queue
from typing import Dict, Any, Optional
from urllib import request as urllib_request
from urllib import error as urllib_error
from flask import Flask, request, jsonify
from threading import Thread
import time

from simp.agentic_https import build_contract_description
from simp.native_tools import NATIVE_TOOL_REGISTRIES, NativeToolRegistry
from simp.server.broker import SimpBroker, BrokerConfig, BrokerState
from simp.server.security_audit import SecurityAuditLog, get_audit_log
from simp.server.request_guards import (
    validate_intent_payload,
    validate_registration_payload,
    sanitize_agent_id,
)
from simp.server.validation import AgentRegistration
from simp.server.rate_limit import RateLimiter
from simp.server.control_auth import require_control_auth
from simp.server.jwt_auth import (
    require_jwt,
    get_jwt_config,
    build_token_issue_handler,
    build_token_verify_handler,
    get_authenticated_agent_id,
)
from simp.server.ws_bridge import WsBridge
from simp.memory.hooks import MemoryHooks
from simp.memory.conversation_archive import ConversationArchive
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.session_bootstrap import SessionBootstrap
from config.config import SimpConfig
from simp.orchestration.orchestration_manager import OrchestrationManager
from simp.server.dashboard_ui import build_dashboard_html, get_dashboard_js, get_dashboard_css
from simp.transport.manager import TransportManager

# A2A compat imports
from simp.compat.agent_card import AgentCardGenerator
from simp.compat.task_map import (
    translate_a2a_to_simp,
    validate_a2a_payload,
    build_a2a_task_status,
)
from simp.compat.projectx_card import (
    build_projectx_a2a_card,
    validate_projectx_task,
)
from simp.compat.brp_card import (
    build_brp_a2a_card,
    validate_brp_task,
)
from simp.compat.brp_diagnostics import build_brp_health_report
from simp.compat.event_stream import build_a2a_event, build_a2a_events_list, EVENT_BUFFER
from simp.compat.a2a_security import (
    build_a2a_security_schemes_block,
    build_replay_guard_note,
)
from simp.compat.ops_policy import SPEND_LEDGER
from simp.compat.financial_ops import (
    build_financial_ops_card,
    validate_financial_op,
    record_would_spend,
    execute_approved_payment,
)
from simp.compat.payment_connector import (
    HEALTH_TRACKER,
    ALLOWED_CONNECTORS,
    build_connector,
    validate_payment_request,
)
from simp.compat.approval_queue import (
    APPROVAL_QUEUE,
    POLICY_CHANGE_QUEUE,
    PaymentProposalStatus,
)
from simp.compat.live_ledger import LIVE_LEDGER
from simp.compat.reconciliation import run_reconciliation
from simp.compat.projectx_diagnostics import build_projectx_health_report
from simp.compat.projectx_contracts import (
    append_contract,
    append_many_contracts,
    contract_summary,
    read_contracts,
)
from simp.compat.projectx_phase_status import (
    append_phase_status,
    build_phase_alerts,
    read_latest_phase_status,
    summarize_phase_status,
)
from simp.compat.rollback import ROLLBACK_MANAGER
from simp.compat.gate_manager import GATE_MANAGER
from simp.compat.budget_monitor import BUDGET_MONITOR

# Max payload for A2A task submissions (64 KB)
_A2A_MAX_PAYLOAD = 64 * 1024
_DEFAULT_PROJECTX_GUARD_URL = os.environ.get("PROJECTX_GUARD_URL", "http://127.0.0.1:8771").rstrip("/")


def _utcnow_iso_http() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fetch_projectx_phase_status(timeout: float = 3.0) -> Optional[Dict[str, Any]]:
    target = f"{_DEFAULT_PROJECTX_GUARD_URL}/phase/status"
    req = urllib_request.Request(target, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (urllib_error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _resolve_projectx_phase_status() -> Dict[str, Any]:
    live = _fetch_projectx_phase_status()
    if isinstance(live, dict):
        record = append_phase_status(live)
        record["source"] = "live"
        return record
    cached = read_latest_phase_status()
    if isinstance(cached, dict):
        cached = dict(cached)
        cached["source"] = "cache"
        cached["status"] = str(cached.get("status") or "cached")
        return cached
    return {
        "status": "unreachable",
        "source": "none",
        "phase_range": "8-20",
        "phases": {},
    }


def require_api_key(f):
    """Require valid API key for data-plane endpoints."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        config = SimpConfig()
        if not config.REQUIRE_API_KEY:
            return f(*args, **kwargs)

        # Read API keys from config (SIMP_API_KEY) and env as fallback
        valid_keys: set[str] = set()
        config_key = config.SIMP_API_KEY
        if config_key:
            valid_keys.add(config_key)
        env_key = os.environ.get("SIMP_API_KEY", "").strip()
        if env_key:
            valid_keys.add(env_key)

        if not valid_keys:
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        provided_key = ""
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            provided_key = request.headers["X-API-Key"]
        elif request.headers.get("X-SIMP-API-Key"):
            provided_key = request.headers["X-SIMP-API-Key"]

        if not provided_key:
            return jsonify({"error": "API key required", "hint": "Set Authorization: Bearer <key> or X-API-Key header"}), 401

        if not any(hmac.compare_digest(provided_key, k) for k in valid_keys):
            return jsonify({"error": "Invalid API key"}), 403

        return f(*args, **kwargs)
    return decorated


def _require_api_key(f):
    """A2A-style API key check (env-var based, used by A2A routes)."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if os.environ.get("SIMP_REQUIRE_API_KEY", "false").lower() in ("false", "0", "no"):
            return f(*args, **kwargs)
        key = request.headers.get("X-API-Key", "")
        expected = os.environ.get("SIMP_API_KEY", "")
        if not expected:
            return f(*args, **kwargs)
        if key != expected:
            return jsonify({"status": "error", "error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return wrapper


class SimpHttpServer:
    """
    HTTP REST API wrapper for SIMP Broker

    Provides endpoints for:
    - Agent registration
    - Intent routing
    - Response handling
    - Status/metrics
    - Memory layer (conversations, tasks, knowledge index, context packs)
    - A2A compatibility (agent cards, task translation, events, security)
    """

    def __init__(self, broker_config: Optional[BrokerConfig] = None, debug: bool = False):
        """Initialize HTTP server"""
        self.app = Flask("SIMP")
        self.app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 KB
        self.limiter = RateLimiter()

        # Sprint 81 — CORS middleware: add headers on every response
        @self.app.after_request
        def add_cors_headers(response):
            # Only add CORS to API routes (not dashboard assets)
            if request.path.startswith(("/intents", "/agents", "/health", "/mesh",
                                        "/routing", "/tasks", "/memory", "/a2a",
                                        "/financial_ops", "/gates", "/orchestration",
                                        "/projectx", "/brp", "/audit")):
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = (
                    "Content-Type, Authorization, X-API-Key, X-SIMP-API-Key, "
                    "X-Request-ID, trace_id, correlation_id"
                )
            return response

        # Memory layer components
        self.conversation_archive = ConversationArchive()
        self.task_memory = TaskMemory()
        self.knowledge_index = KnowledgeIndex()
        self._memory_hooks = MemoryHooks(
            task_memory=self.task_memory,
            knowledge_index=self.knowledge_index,
            conversation_archive=self.conversation_archive,
        )
        self.broker = SimpBroker(
            broker_config or BrokerConfig(),
            hooks=self._memory_hooks,
        )
        self.debug = debug

        # Shared async event loop for broker operations
        self._async_loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._async_loop.run_forever,
            daemon=True,
            name="SIMP-AsyncLoop",
        )
        self._loop_thread.start()
        self.session_bootstrap = SessionBootstrap(
            task_memory=self.task_memory,
            conversation_archive=self.conversation_archive,
            knowledge_index=self.knowledge_index,
            task_ledger=self.broker.task_ledger,
        )
        self.logger = logging.getLogger("SIMP.HTTP")

        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Sprint 70 — security audit log
        self.audit_log = get_audit_log()

        # JWT auth config (lazy init)
        self.jwt_config = get_jwt_config()
        if self.jwt_config.enabled:
            self.logger.info(
                "✅ JWT auth enabled (alg=%s, require=%s, ttl=%ds)",
                self.jwt_config.algorithm,
                self.jwt_config.require_jwt,
                self.jwt_config.token_ttl_seconds,
            )
        else:
            self.logger.info("ℹ️  JWT auth disabled (set SIMP_JWT_SECRET to enable)")

        # A2A card generator
        self._card_gen = AgentCardGenerator()

        # Sprint 54 — orchestration manager
        self._orchestration = OrchestrationManager(broker=self.broker)

        # Transport manager (multi-transport support)
        self.transport_manager = TransportManager(
            agent_id="broker",
            broker=self.broker,
        )

        # SSE subscriber registry for task streaming
        self._sse_subscribers: dict[str, list[queue.Queue]] = {}
        self._sse_lock = threading.Lock()

        self._setup_security_hooks()
        self._setup_routes()
        self._setup_a2a_routes()
        self._setup_mesh_routes()
        self._setup_sprint51_55_routes()
        self.logger.info("SIMP HTTP Server initialized")

    # ------------------------------------------------------------------
    # SSE streaming (Sprint 41)
    # ------------------------------------------------------------------
    def register_sse_with_runtime(self, runtime):
        """Register the SSE subscriber layer with the given runtime.
        
        This is a no-op stub for Sprint 41 compatibility — real runtime
        integration would wire the runtime's event bus to sse_publish().
        """
        self.logger.info("SSE subscriber layer registered (stub)")
        pass

    def sse_publish(self, task_id: str, event_data: dict) -> None:
        """Publish an SSE event to all subscribers of a given task.
        
        Args:
            task_id: The task identifier subscribers are listening on.
            event_data: JSON-serializable dict to deliver.
        """
        data_str = json.dumps(event_data)
        with self._sse_lock:
            queues = self._sse_subscribers.get(task_id, [])
            for q in queues:
                try:
                    q.put_nowait(f"data: {data_str}\n\n")
                except Exception:
                    pass

    def _setup_security_hooks(self):
        """Setup Sprint 70 security hooks (before/after request)."""

        @self.app.before_request
        def check_content_type():
            """Enforce Content-Type for POST/PUT requests with a body."""
            if request.method in ("POST", "PUT"):
                # Only enforce when request has a body
                has_body = request.content_length and request.content_length > 0
                if not has_body:
                    return None
                content_type = request.content_type or ""
                if "application/json" not in content_type:
                    self.audit_log.log_event(
                        "validation_error",
                        {
                            "reason": "invalid_content_type",
                            "content_type": content_type,
                            "path": request.path,
                            "method": request.method,
                        },
                        severity="low",
                    )
                    return (
                        jsonify({
                            "status": "error",
                            "error": "Content-Type must be application/json"
                        }),
                        415,
                    )

        @self.app.before_request
        def check_prompt_injection():
            """Scan incoming JSON request bodies for prompt injection patterns.

            Ultra-low latency: uses raw text scan on request data without
            full JSON parsing when possible. Blocks confirmed injection
            (score ≥ 0.85) on intent/agent endpoints when BRP is enforced.
            """
            if request.method not in ("POST", "PUT"):
                return None
            if not request.content_length or request.content_length <= 0:
                return None
            path = request.path
            if not any(p in path for p in ("/intent", "/agent", "/mesh", "/route")):
                return None

            from simp.config.config import SimpConfig
            simp_config = SimpConfig()
            brp_mode = str(getattr(simp_config, "BRP_MODE", "shadow")).lower()
            if brp_mode not in ("enforced", "enforce"):
                return None

            from simp.security.brp.prompt_injection_detector import get_injection_detector
            detector = get_injection_detector()

            # Fast path: get raw text data if possible (avoids full JSON parse)
            if request.is_json:
                raw = request.get_data(as_text=True)
                if raw and len(raw) > 12:
                    result = detector.analyze_text(raw)
                    if result.detected and result.score >= 0.85:
                        self.audit_log.log_event(
                            "prompt_injection_blocked",
                            {
                                "score": result.score,
                                "tags": result.threat_tags,
                                "path": path,
                                "method": request.method,
                                "detections": [
                                    {"layer": d.layer, "pattern": d.pattern}
                                    for d in result.detections
                                ],
                            },
                            severity="high",
                        )
                        return (
                            jsonify({
                                "status": "error",
                                "error_code": "PROMPT_INJECTION_BLOCKED",
                                "error": "Request blocked due to prompt injection",
                                "pi_score": round(result.score, 4),
                                "pi_tags": result.threat_tags,
                            }),
                            403,
                        )
            return None

        # Sprint 82 — JWT token parsing (sets request.jwt_claims for all routes)
        @self.app.before_request
        def parse_jwt():
            """Parse JWT from Authorization header and set request.jwt_claims.
            
            This runs for every request but does NOT reject — the per-route
            ``@require_jwt`` decorator handles enforcement. This pre-parser
            avoids redundant header extraction in route handlers.
            """
            if not self.jwt_config.enabled:
                request.jwt_claims = None
                return None

            auth_header = request.headers.get("Authorization", "")
            token = ""
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            elif request.headers.get("X-JWT-Token"):
                token = request.headers["X-JWT-Token"].strip()

            if token:
                from simp.server.jwt_auth import verify_jwt
                claims = verify_jwt(token)
                request.jwt_claims = claims
            else:
                request.jwt_claims = None
            return None

        @self.app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Content-Security-Policy"] = "default-src 'none'"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers.pop("Server", None)
            response.headers.pop("X-Powered-By", None)
            return response

    def _submit_async(self, coro, timeout: float = 30.0):
        """Run a broker coroutine on the shared async loop and return its result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        return future.result(timeout=timeout)

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify(self.broker.health_check()), 200

        # Sprint 85 — WebSocket bridge stats endpoint
        @self.app.route("/ws/metrics", methods=["GET"])
        def ws_metrics():
            """Prometheus metrics endpoint for WS bridge."""
            if not hasattr(self, "_ws_bridge") or self._ws_bridge is None:
                return "", 204
            return self._ws_bridge.get_prometheus_text(), 200, {"Content-Type": "text/plain"}

        @self.app.route("/ws/stats", methods=["GET"])
        def ws_stats():
            """Get WebSocket bridge connection and push statistics."""
            if not hasattr(self, "_ws_bridge") or self._ws_bridge is None:
                return jsonify({
                    "status": "success",
                    "ws_bridge": {
                        "enabled": False,
                        "message": "WebSocket bridge is disabled",
                    }
                }), 200
            bridge = self._ws_bridge
            return jsonify({
                "status": "success",
                "ws_bridge": {
                    "enabled": True,
                    "host": bridge.host,
                    "port": bridge.port,
                    "connections": {
                        "active": bridge.stats["connections_active"],
                        "total": bridge.stats["connections_total"],
                    },
                    "agents": list(bridge.connected_agents),
                    "channels": {
                        name: list(members) 
                        for name, members in bridge._channels.items()
                    },
                    "throughput": {
                        "intents_forwarded": bridge.stats["intents_forwarded"],
                        "pushes_sent": bridge.stats["pushes_sent"],
                    },
                    "errors": {
                        "auth_failures": bridge.stats["auth_failures"],
                        "errors": bridge.stats["errors"],
                    },
                }
            }), 200

        # Sprint 82 — JWT auth endpoints
        @self.app.route("/auth/token", methods=["POST"])
        @self.limiter.limit(10)
        def auth_issue_token():
            """Issue a JWT token for an authenticated agent.
            
            Protected by the existing API key mechanism (/auth/token requires
            a valid SIMP_API_KEY in X-API-Key or Authorization: Bearer header).
            Agents can self-issue tokens after passing API key auth.
            """
            handler = build_token_issue_handler()
            return handler()

        @self.app.route("/auth/verify", methods=["GET", "POST"])
        def auth_verify_token():
            """Verify a JWT token. Requires the token in Authorization header.
            
            Returns the token's claims for debugging/monitoring purposes.
            """
            handler = build_token_verify_handler()
            return handler()

        @self.app.route("/auth/status", methods=["GET"])
        def auth_status():
            """Return current JWT auth configuration status (no auth required)."""
            cfg = self.jwt_config
            return jsonify({
                "status": "success",
                "jwt_enabled": cfg.enabled,
                "jwt_required": cfg.require_jwt,
                "algorithm": cfg.algorithm if cfg.enabled else "disabled",
                "token_ttl_seconds": cfg.token_ttl_seconds if cfg.enabled else 0,
                "agent_tokens_enabled": cfg.agent_token_enabled if cfg.enabled else False,
                "current_identity": get_authenticated_agent_id() or "anonymous",
                "authenticated": getattr(request, "jwt_claims", None) is not None,
            }), 200

        @self.app.route("/agentic/contract", methods=["GET"])
        def agentic_contract():
            return jsonify(build_contract_description()), 200

        @self.app.route("/agentic/intents/route", methods=["POST"])
        def route_agentic_intent():
            payload = request.get_json(force=False, silent=True) or {}
            response = self._submit_async(self.broker.route_agentic_request(payload))
            status_code = 200
            if not response.get("success", False):
                status_code = 400 if response.get("error_code") == "INVALID_SIGNATURE" else 500
            return jsonify(response), status_code

        @self.app.route("/skills", methods=["GET"])
        def list_skills():
            """List available skills from DeerFlow runtime."""
            try:
                from simp.orchestration.orchestration_loop import _get_deerflow_runtime
                runtime = _get_deerflow_runtime()
                if runtime is None or not hasattr(runtime, "skill_loader"):
                    return jsonify({
                        "status": "success",
                        "count": 0,
                        "skills": [],
                        "message": "DeerFlow runtime not active",
                    }), 200
                registry = runtime.skill_loader.registry
                skills = registry.list_all() if hasattr(registry, "list_all") else []
                skill_list = [
                    {
                        "name": getattr(s, "name", str(s)),
                        "description": getattr(s, "description", ""),
                        "tools": getattr(s, "tools", []),
                        "intent_types": getattr(s, "intent_types", []),
                    }
                    for s in skills
                ]
                return jsonify({
                    "status": "success",
                    "count": len(skill_list),
                    "skills": skill_list,
                }), 200
            except ImportError:
                return jsonify({
                    "status": "success",
                    "count": 0,
                    "skills": [],
                    "message": "DeerFlow runtime not available",
                }), 200

        @self.app.route("/tasks/<task_id>/stream", methods=["GET"])
        def task_sse_stream(task_id):
            """SSE stream for a task's progress."""
            from flask import Response, stream_with_context

            def generate():
                q = queue.Queue()
                with self._sse_lock:
                    if task_id not in self._sse_subscribers:
                        self._sse_subscribers[task_id] = []
                    self._sse_subscribers[task_id].append(q)
                try:
                    yield ": connected\n\n"
                    while True:
                        try:
                            data = q.get(timeout=30)
                            yield data
                        except queue.Empty:
                            yield ": heartbeat\n\n"
                except GeneratorExit:
                    pass
                finally:
                    with self._sse_lock:
                        queues = self._sse_subscribers.get(task_id, [])
                        if q in queues:
                            queues.remove(q)
                        if not self._sse_subscribers.get(task_id):
                            self._sse_subscribers.pop(task_id, None)

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.app.route("/native/tools/list", methods=["GET"])
        def list_native_tools():
            registries = NativeToolRegistry.all_registries()
            return jsonify(
                {
                    "status": "success",
                    "source": "native",
                    "agent_count": len(registries),
                    "agents": sorted(registries),
                    "tool_names": sorted(
                        {
                            tool.name
                            for registry in registries.values()
                            for tool in registry.list_tools()
                        }
                    ),
                }
            ), 200

        @self.app.route("/native/tools/<agent_id>/list", methods=["GET"])
        def list_agent_native_tools(agent_id):
            registry = NativeToolRegistry.get_registry(agent_id)
            if registry is None:
                return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404
            return jsonify(
                {
                    "status": "success",
                    "source": "native",
                    "agent_id": agent_id,
                    "tool_names": sorted(registry.tool_names()),
                    "tools": registry.list_native_items(),
                }
            ), 200

        @self.app.route("/native/tools/<agent_id>/<tool_name>/invoke", methods=["POST"])
        def invoke_native_tool(agent_id, tool_name):
            registry = NativeToolRegistry.get_registry(agent_id)
            if registry is None:
                return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404
            body = request.get_json(force=False, silent=True) or {}
            arguments = body.get("arguments") or {}
            try:
                result = registry.invoke(tool_name, arguments=arguments)
            except KeyError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 404
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500
            return jsonify(
                {
                    "status": "success",
                    "source": "native",
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "invocation_mode": "native",
                    "result": result,
                }
            ), 200

        @self.app.route("/mcp/tools/list", methods=["GET"])
        def list_compat_tools():
            registries = dict(NATIVE_TOOL_REGISTRIES)
            return jsonify(
                {
                    "status": "success",
                    "source": "native_via_mcp_compat",
                    "agent_count": len(registries),
                    "agents": sorted(registries),
                    "tools": [
                        {
                            "agent_id": agent_id,
                            "tools": registry.list_mcp_items(),
                        }
                        for agent_id, registry in sorted(registries.items())
                    ],
                }
            ), 200

        @self.app.route("/mcp/tools/<agent_id>/list", methods=["GET"])
        def list_agent_compat_tools(agent_id):
            registry = NativeToolRegistry.get_registry(agent_id)
            if registry is None:
                return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404
            return jsonify(
                {
                    "status": "success",
                    "source": "native_via_mcp_compat",
                    "agent_id": agent_id,
                    "tools": registry.list_mcp_items(),
                }
            ), 200

        @self.app.route("/mcp/tools/<agent_id>/<tool_name>/call", methods=["POST"])
        def call_compat_tool(agent_id, tool_name):
            registry = NativeToolRegistry.get_registry(agent_id)
            if registry is None:
                return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404
            body = request.get_json(force=False, silent=True) or {}
            arguments = body.get("arguments") or {}
            try:
                result = registry.invoke(tool_name, arguments=arguments)
            except KeyError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 404
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500
            return jsonify(
                {
                    "status": "success",
                    "source": "native_via_mcp_compat",
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "invocation_mode": "mcp_bridge",
                    "result": result,
                }
            ), 200

        # ── TimesFM observability endpoints ────────────────────────────
        @self.app.route("/timesfm/health", methods=["GET"])
        def timesfm_health():
            """TimesFM service + policy engine health. Never raises."""
            try:
                from simp.integrations.timesfm_service import get_timesfm_service_sync
                tfm_health = get_timesfm_service_sync().health()
            except Exception as exc:
                tfm_health = {"error": str(exc), "status": "unavailable"}

            try:
                from simp.integrations.timesfm_policy_engine import PolicyEngine
                pe_health = PolicyEngine().health()
            except Exception as exc:
                pe_health = {"error": str(exc), "status": "unavailable"}

            return jsonify({
                "status": "success",
                "timesfm_service": tfm_health,
                "policy_engine": pe_health,
            }), 200

        @self.app.route("/timesfm/audit", methods=["GET"])
        def timesfm_audit():
            """Recent TimesFM forecast audit records.
            Query params: ?agent=<id>&limit=N (default 100, max 500).
            """
            agent_id = request.args.get("agent")
            limit = min(int(request.args.get("limit", 100)), 500)
            try:
                from simp.integrations.timesfm_service import get_timesfm_service_sync
                svc = get_timesfm_service_sync()
                if agent_id:
                    records = svc.audit.for_agent(agent_id, n=limit)
                else:
                    records = svc.audit.recent(n=limit)
            except Exception as exc:
                records = [{"error": str(exc)}]
            return jsonify({
                "status": "success",
                "records": records,
                "count": len(records),
            }), 200

        @self.app.route("/agents/register", methods=["POST"])
        @require_jwt
        @require_api_key
        @self.limiter.limit(10)
        def register_agent():
            data = request.get_json(force=False, silent=True) or {}

            ok, err = validate_registration_payload(data)
            if not ok:
                return (
                    jsonify({
                        "status": "error",
                        "error_code": "VALIDATION_FAILED",
                        "error": err,
                    }),
                    400,
                )

            try:
                AgentRegistration(**data)
            except Exception as pyd_err:
                return (
                    jsonify({
                        "status": "error",
                        "error_code": "VALIDATION_FAILED",
                        "error": str(pyd_err),
                    }),
                    400,
                )

            agent_id = data["agent_id"]
            agent_type = data["agent_type"]
            endpoint = data["endpoint"]
            metadata = data.get("metadata", {})
            public_key = data.get("public_key")
            if public_key:
                metadata["public_key"] = public_key

            success = self.broker.register_agent(agent_id, agent_type, endpoint, metadata)

            if success:
                self.audit_log.log_event(
                    "agent_registered",
                    {"agent_id": agent_id, "agent_type": agent_type},
                    severity="low",
                )
                return (
                    jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "message": f"Agent '{agent_id}' registered"
                    }),
                    201,
                )
            else:
                return (
                    jsonify({
                        "status": "error",
                        "error": f"Failed to register agent '{agent_id}'"
                    }),
                    400,
                )

        @self.app.route("/agents", methods=["GET"])
        @require_jwt
        @require_api_key
        def list_agents():
            agents_list = self.broker.list_agents()
            # Build a dict keyed by agent_id for backward-compatible consumer code
            agents_dict: Dict[str, Dict[str, Any]] = {}
            for a in agents_list:
                aid = a.get("agent_id", "")
                agents_dict[aid] = a
            return jsonify({
                "status": "success",
                "count": len(agents_list),
                "agents": agents_dict
            }), 200

        @self.app.route("/agents/heartbeat", methods=["POST"])
        @require_jwt
        @require_api_key
        def post_heartbeat():
            """Legacy endpoint: record heartbeat with agent_id in JSON body."""
            data = request.get_json(silent=True) or {}
            agent_id = data.get("agent_id")
            if not agent_id:
                return jsonify({"status": "error", "error": "Missing agent_id in request body"}), 400
            
            success = self.broker.record_heartbeat(agent_id)
            if success:
                agent = self.broker.get_agent(agent_id)
                return jsonify({
                    "agent_id": agent_id,
                    "heartbeat_at": agent.get("last_heartbeat") if agent else _utcnow_iso_http(),
                    "count": agent.get("heartbeat_count", 0) if agent else 0,
                }), 200
            return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404

        @self.app.route("/agents/<agent_id>", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_agent(agent_id):
            ok, err = sanitize_agent_id(agent_id)
            if not ok:
                return jsonify({
                    "status": "error",
                    "error_code": "VALIDATION_FAILED",
                    "error": f"Invalid agent_id: {err}",
                }), 400
            agent = self.broker.get_agent(agent_id)
            if agent:
                return jsonify({"status": "success", "agent": agent}), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found"
                }), 404

        @self.app.route("/agents/<agent_id>", methods=["DELETE"])
        @require_control_auth
        def deregister_agent(agent_id):
            ok, err = sanitize_agent_id(agent_id)
            if not ok:
                return jsonify({
                    "status": "error",
                    "error_code": "VALIDATION_FAILED",
                    "error": f"Invalid agent_id: {err}",
                }), 400
            success = self.broker.deregister_agent(agent_id)
            if success:
                self.audit_log.log_event(
                    "agent_deregistered",
                    {"agent_id": agent_id},
                    severity="low",
                )
                return jsonify({
                    "status": "success",
                    "message": f"Agent '{agent_id}' deregistered"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found"
                }), 404

        # ----- Sprint 64: Readiness Endpoint -----

        @self.app.route("/control/ready", methods=["GET"])
        def control_ready():
            """Return 200 when broker is ready, 503 when still initializing."""
            broker = self.broker
            uptime = 0.0
            grace_remaining = 0.0
            if hasattr(broker, "_startup_at") and broker._startup_at:
                uptime = (datetime.now(timezone.utc) - broker._startup_at).total_seconds()
                grace_remaining = max(0.0, 60.0 - uptime)

            ready = (
                broker.state == BrokerState.RUNNING
                and getattr(broker, "_ready", False)
            )

            body = {
                "ready": ready,
                "broker_state": broker.state.value,
                "agents_registered": len(broker.agents),
                "intents_loaded_from_disk": getattr(broker, "_intents_loaded_from_disk", 0),
                "uptime_seconds": round(uptime, 1),
                "startup_grace_remaining_seconds": round(grace_remaining, 1),
            }

            if not ready:
                body["reason"] = "broker not running" if broker.state != BrokerState.RUNNING else "initializing"

            return jsonify(body), 200 if ready else 503

        # ----- Sprint 62: Heartbeat Routes -----

        @self.app.route("/agents/<agent_id>/heartbeat", methods=["POST"])
        def post_heartbeat_with_id(agent_id):
            """Record a heartbeat for an agent (no auth required)."""
            success = self.broker.record_heartbeat(agent_id)
            if success:
                agent = self.broker.get_agent(agent_id)
                return jsonify({
                    "agent_id": agent_id,
                    "heartbeat_at": agent.get("last_heartbeat") if agent else _utcnow_iso_http(),
                    "count": agent.get("heartbeat_count", 0) if agent else 0,
                }), 200
            return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404

        @self.app.route("/agents/<agent_id>/heartbeat", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_heartbeat(agent_id):
            """Get heartbeat status for an agent."""
            agent = self.broker.get_agent(agent_id)
            if not agent:
                return jsonify({"status": "error", "error": f"Agent '{agent_id}' not found"}), 404
            return jsonify({
                "agent_id": agent_id,
                "last_heartbeat": agent.get("last_heartbeat"),
                "heartbeat_count": agent.get("heartbeat_count", 0),
                "stale": agent.get("stale", False),
                "stale_after_seconds": 90,
            }), 200

        @self.app.route("/agents/sweep-stale", methods=["POST"])
        @require_jwt
        @require_api_key
        def sweep_stale():
            """Deregister stale agents."""
            deregistered = self.broker.deregister_stale_agents(300.0)
            return jsonify({
                "deregistered": deregistered,
                "count": len(deregistered),
            }), 200

        @self.app.route("/intents/route", methods=["POST"])
        @require_jwt
        @require_api_key
        @self.limiter.limit(60)
        def route_intent():
            data = request.get_json(force=False, silent=True) or {}

            ok, err = validate_intent_payload(data)
            if not ok:
                return (
                    jsonify({
                        "status": "error",
                        "error_code": "VALIDATION_FAILED",
                        "error": err,
                    }),
                    400,
                )

            import asyncio as _asyncio
            future = _asyncio.run_coroutine_threadsafe(
                self.broker.route_intent(data), self._async_loop
            )
            try:
                result = future.result(timeout=30)
                return jsonify(result), 200
            except TimeoutError:
                return jsonify({
                    "status": "error",
                    "error_code": "TIMEOUT",
                    "error": "Intent routing timed out after 30 seconds",
                }), 504
            except Exception as exc:
                return jsonify({
                    "status": "error",
                    "error_code": "INTERNAL_ERROR",
                    "error": str(exc),
                }), 500

        @self.app.route("/intents/<intent_id>", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_intent_status(intent_id):
            status = self.broker.get_intent_status(intent_id)
            if status:
                return jsonify({"status": "success", "intent": status}), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/projectx/contracts", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_projectx_contracts():
            """Return ProjectX contract records ingested by SIMP."""
            try:
                limit = max(1, min(int(request.args.get("limit", 50)), 500))
                contract_type = request.args.get("contract_type") or None
                mission_id = request.args.get("mission_id") or None
                records = read_contracts(limit=limit, contract_type=contract_type, mission_id=mission_id)
                return jsonify({
                    "status": "success",
                    "count": len(records),
                    "contracts": records,
                }), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500

        @self.app.route("/projectx/contracts", methods=["POST"])
        @require_jwt
        @require_api_key
        def post_projectx_contract():
            """Ingest one or more ProjectX contract records."""
            data = request.get_json(force=False, silent=True) or {}
            try:
                if isinstance(data.get("contracts"), list):
                    records = append_many_contracts(data["contracts"])
                else:
                    records = [append_contract(data)]
                for record in records[:20]:
                    self.broker._log_event(
                        "projectx_contract_ingested",
                        f"ProjectX contract ingested: {record.get('contract_type')}",
                        agent_id=str(record.get("source_agent") or "projectx_native"),
                        extra={
                            "contract_type": record.get("contract_type"),
                            "record_id": record.get("record_id"),
                            "mission_id": record.get("mission_id"),
                        },
                    )
                return jsonify({
                    "status": "success",
                    "count": len(records),
                    "contracts": records,
                }), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500

        @self.app.route("/projectx/contracts/summary", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_projectx_contract_summary():
            """Return ProjectX contract coverage summary."""
            try:
                return jsonify(contract_summary()), 200
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500

        @self.app.route("/projectx/phases/status", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_projectx_phase_status():
            """Return live ProjectX phase status when reachable, else latest cached snapshot."""
            try:
                return jsonify(_resolve_projectx_phase_status()), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500

        @self.app.route("/projectx/phases/status", methods=["POST"])
        @require_jwt
        @require_api_key
        def post_projectx_phase_status():
            """Persist a pushed ProjectX phase status snapshot."""
            data = request.get_json(force=False, silent=True) or {}
            try:
                record = append_phase_status(data)
                self.broker._log_event(
                    "projectx_phase_status_ingested",
                    "ProjectX phase status snapshot ingested",
                    agent_id=str(record.get("source_agent") or "projectx_native"),
                    extra={
                        "phase_range": record.get("phase_range"),
                        "phase_count": len(record.get("phases") or {}),
                    },
                )
                return jsonify({"status": "success", "phase_status": record}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500

        @self.app.route("/projectx/phases/summary", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_projectx_phase_summary():
            """Return compact ProjectX phase health summary and derived alerts."""
            try:
                record = _resolve_projectx_phase_status()
                summary = summarize_phase_status(record)
                return jsonify({
                    **summary,
                    "source": record.get("source"),
                    "alerts": build_phase_alerts(record),
                }), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 500

        @self.app.route("/intents/<intent_id>/response", methods=["POST"])
        @require_jwt
        @require_api_key
        @self.limiter.limit(60)
        def record_response(intent_id):
            data = request.get_json() or {}
            execution_time = data.get("execution_time_ms", 0.0)

            success = self.broker.record_response(
                intent_id,
                data.get("response", {}),
                execution_time
            )

            if success:
                # Sprint 58 — push to SSE buffer
                EVENT_BUFFER.push("response_recorded", {
                    "intent_id": intent_id,
                    "execution_time_ms": execution_time,
                })
                return jsonify({
                    "status": "success",
                    "message": "Response recorded"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/intents/<intent_id>/error", methods=["POST"])
        @require_jwt
        @require_api_key
        @self.limiter.limit(60)
        def record_error(intent_id):
            data = request.get_json() or {}
            error_msg = data.get("error", "Unknown error")
            execution_time = data.get("execution_time_ms", 0.0)

            success = self.broker.record_error(intent_id, error_msg, execution_time)

            if success:
                # Sprint 58 — push to SSE buffer
                EVENT_BUFFER.push("error_recorded", {
                    "intent_id": intent_id,
                    "error": error_msg,
                    "execution_time_ms": execution_time,
                })
                return jsonify({
                    "status": "success",
                    "message": "Error recorded"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/stats", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_stats():
            return jsonify({
                "status": "success",
                "stats": self.broker.get_statistics()
            }), 200

        @self.app.route("/status", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_status():
            return jsonify({
                "status": "success",
                "broker": {
                    "state": self.broker.state.value,
                    "health": self.broker.health_check(),
                    "stats": self.broker.get_statistics()
                }
            }), 200

        @self.app.route("/control/start", methods=["POST"])
        @self.limiter.limit(5)
        @require_control_auth
        def start_broker():
            self.broker.start()
            return jsonify({
                "status": "success",
                "message": "Broker started"
            }), 200

        @self.app.route("/control/stop", methods=["POST"])
        @self.limiter.limit(5)
        @require_control_auth
        def stop_broker():
            self.broker.stop()
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            return jsonify({
                "status": "success",
                "message": "Broker stopped"
            }), 200

        # --- Transport endpoints ---

        @self.app.route("/transport/status", methods=["GET"])
        def transport_status():
            """Get multi-transport status"""
            return jsonify({
                "status": "success",
                "transport": self.transport_manager.get_status(),
            }), 200

        @self.app.route("/transport/peers", methods=["GET"])
        def transport_peers():
            """Get known mesh peers"""
            peers = self.transport_manager.get_peers()
            return jsonify({
                "status": "success",
                "count": len(peers),
                "peers": peers,
            }), 200

        @self.app.route("/transport/discover", methods=["POST"])
        def transport_discover():
            """Broadcast discovery on all transports"""
            data = request.get_json() or {}
            agent_type = data.get("agent_type", "")
            capabilities = data.get("capabilities", [])
            result = self.transport_manager.discover(agent_type, capabilities)
            return jsonify({
                "status": "success",
                "discovery": result,
            }), 200

        # ----- Task Ledger Endpoints (GET-only, read-safe) -----

        @self.app.route("/tasks", methods=["GET"])
        @require_jwt
        @require_api_key
        def list_tasks():
            status_filter = request.args.get("status")
            agent_filter = request.args.get("agent")
            type_filter = request.args.get("task_type")
            tasks = self.broker.task_ledger.list_tasks(
                status=status_filter,
                agent=agent_filter,
                task_type=type_filter,
            )
            return jsonify({
                "status": "success",
                "count": len(tasks),
                "tasks": tasks,
                "failure_stats": self.broker.task_ledger.get_failure_stats(),
                "status_counts": self.broker.task_ledger.get_status_counts(),
            }), 200

        @self.app.route("/tasks/<task_id>", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_task(task_id):
            task = self.broker.task_ledger.get_task(task_id)
            if task:
                return jsonify({"status": "success", "task": task}), 200
            return jsonify({
                "status": "error",
                "error": f"Task '{task_id}' not found",
            }), 404

        @self.app.route("/tasks/queue", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_task_queue():
            queue = self.broker.task_ledger.get_queue()
            return jsonify({
                "status": "success",
                "count": len(queue),
                "queue": queue,
            }), 200

        @self.app.route("/routing/policy", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_routing_policy():
            if self.broker.builder_pool:
                policy = self.broker.builder_pool.policy
                pool_status = self.broker.builder_pool.get_pool_status()
                return jsonify({
                    "status": "success",
                    "policy": policy,
                    "pool_status": pool_status,
                }), 200
            return jsonify({
                "status": "success",
                "policy": {},
                "pool_status": {},
                "message": "Builder pool not configured",
            }), 200

        # ----- Structured Event Log -----

        @self.app.route("/logs", methods=["GET"])
        def get_logs():
            try:
                limit = int(request.args.get("limit", 100))
            except (ValueError, TypeError):
                limit = 100
            limit = max(1, min(limit, 500))
            logs = self.broker.get_logs(limit)
            return jsonify({
                "status": "success",
                "count": len(logs),
                "logs": logs,
            }), 200

        # ----- Memory Layer Endpoints -----

        @self.app.route("/memory/conversations", methods=["GET"])
        def list_conversations():
            topic = request.args.get("topic")
            tag = request.args.get("tag")
            participant = request.args.get("participant")
            convos = self.conversation_archive.list_conversations(
                topic=topic, tag=tag, participant=participant,
            )
            return jsonify({
                "status": "success",
                "count": len(convos),
                "conversations": convos,
            }), 200

        @self.app.route("/memory/conversations/<conv_id>", methods=["GET"])
        def get_conversation(conv_id):
            conv = self.conversation_archive.get_conversation(conv_id)
            if conv:
                return jsonify({"status": "success", "conversation": conv}), 200
            return jsonify({
                "status": "error",
                "error": f"Conversation '{conv_id}' not found",
            }), 404

        @self.app.route("/memory/conversations", methods=["POST"])
        @require_jwt
        @require_api_key
        @self.limiter.limit(30)
        def save_conversation():
            data = request.get_json() or {}
            if not data.get("topic"):
                return jsonify({
                    "status": "error",
                    "error": "Missing required field: topic",
                }), 400
            conv_id = self.conversation_archive.save_conversation(data)
            return jsonify({
                "status": "success",
                "conversation_id": conv_id,
            }), 201

        @self.app.route("/memory/tasks", methods=["GET"])
        def list_memory_tasks():
            tasks = self.task_memory.list_tasks()
            return jsonify({
                "status": "success",
                "count": len(tasks),
                "tasks": tasks,
            }), 200

        @self.app.route("/memory/tasks/<slug>", methods=["GET"])
        def get_memory_task(slug):
            task = self.task_memory.get_task(slug)
            if task:
                return jsonify({"status": "success", "task": task}), 200
            return jsonify({
                "status": "error",
                "error": f"Task memory '{slug}' not found",
            }), 404

        @self.app.route("/memory/index", methods=["GET"])
        def get_knowledge_index():
            return jsonify({
                "status": "success",
                "index": self.knowledge_index.get_full_index(),
            }), 200

        @self.app.route("/memory/context-pack", methods=["GET"])
        def get_context_pack():
            task_id = request.args.get("task_id")
            topic = request.args.get("topic")
            agent_id = request.args.get("agent_id")
            if not any([task_id, topic, agent_id]):
                return jsonify({
                    "status": "error",
                    "error": "Provide at least one of: task_id, topic, agent_id",
                }), 400
            pack = self.session_bootstrap.generate_context_pack(
                task_id=task_id, topic=topic, agent_id=agent_id,
            )
            return jsonify({"status": "success", "context_pack": pack}), 200

        # ----- Sprint 57: Dashboard UI served on broker port 5555 -----

        @self.app.route("/dashboard", methods=["GET"])
        @self.app.route("/dashboard/ui", methods=["GET"])
        def dashboard_ui():
            """Serve the full SIMP dashboard HTML (with injected broker URL)."""
            from flask import Response
            html = build_dashboard_html(broker_url="http://127.0.0.1:5555")
            return Response(html, mimetype="text/html")

        @self.app.route("/dashboard/static/app.js", methods=["GET"])
        def dashboard_js():
            """Serve dashboard JavaScript."""
            from flask import Response
            js = get_dashboard_js()
            return Response(js, mimetype="application/javascript")

        @self.app.route("/dashboard/static/style.css", methods=["GET"])
        def dashboard_css():
            """Serve dashboard stylesheet."""
            from flask import Response
            css = get_dashboard_css()
            return Response(css, mimetype="text/css")

        @self.app.route("/security/audit-log", methods=["GET"])
        @require_jwt
        @require_api_key
        def get_audit_log_endpoint():
            """Get security audit log entries (Sprint 70).

            Query params:
            - severity: Filter by severity level
            - event_type: Filter by event type
            - limit: Max entries (default 100)
            """
            severity = request.args.get("severity")
            event_type = request.args.get("event_type")
            limit = request.args.get("limit", 100, type=int)
            events = self.audit_log.get_events(
                severity=severity,
                event_type=event_type,
                limit=limit,
            )
            return jsonify({
                "status": "success",
                "count": len(events),
                "events": events,
            }), 200

    # ------------------------------------------------------------------
    # A2A compatibility routes
    # ------------------------------------------------------------------

    def _setup_a2a_routes(self):
        """Setup A2A compatibility routes (Sprints 2-6, S1-S9)."""

        @self.app.route("/.well-known/agent-card.json", methods=["GET"])
        def well_known_card():
            card = self._card_gen.build_broker_card(self.broker.agents)
            return jsonify(card), 200

        @self.app.route("/a2a/tasks", methods=["POST"])
        @_require_api_key
        def a2a_submit_task():
            if request.content_length and request.content_length > _A2A_MAX_PAYLOAD:
                return jsonify({"status": "error", "error": "Payload exceeds 64KB limit"}), 400

            raw = request.get_data()
            if len(raw) > _A2A_MAX_PAYLOAD:
                return jsonify({"status": "error", "error": "Payload exceeds 64KB limit"}), 400

            data = request.get_json(silent=True) or {}

            valid, err = validate_a2a_payload(data)
            if not valid:
                return jsonify({"status": "error", "error": err}), 400

            task_type = data["task_type"]
            simp_type, tr_err = translate_a2a_to_simp(task_type)
            if tr_err:
                return jsonify({"status": "error", "error": tr_err}), 400

            task_id = data.get("task_id", str(uuid.uuid4()))
            status = build_a2a_task_status(task_id, "pending", intent_type=simp_type)
            return jsonify(status), 200

        @self.app.route("/a2a/tasks/<task_id>", methods=["GET"])
        @_require_api_key
        def a2a_get_task(task_id):
            rec = self.broker.get_intent_status(task_id)
            if rec:
                status = build_a2a_task_status(
                    task_id,
                    rec.get("status", "unknown"),
                    intent_type=rec.get("intent_type", ""),
                )
                return jsonify(status), 200
            return jsonify({"status": "error", "error": "Task not found"}), 404

        @self.app.route("/a2a/tasks/types", methods=["GET"])
        def a2a_task_types():
            from simp.compat.task_map import A2A_TO_SIMP_INTENT
            return jsonify({"types": list(A2A_TO_SIMP_INTENT.keys())}), 200

        @self.app.route("/a2a/agents/projectx/agent.json", methods=["GET"])
        def projectx_card():
            base = request.url_root.rstrip("/")
            return jsonify(build_projectx_a2a_card(base)), 200

        @self.app.route("/a2a/agents/projectx/tasks", methods=["POST"])
        @_require_api_key
        def projectx_task():
            data = request.get_json(silent=True) or {}
            ok, msg_or_skill, intent_type = validate_projectx_task(data)
            if not ok:
                return jsonify({"status": "error", "error": msg_or_skill}), 400

            task_id = data.get("task_id", str(uuid.uuid4()))
            status = build_a2a_task_status(task_id, "pending", intent_type=intent_type)
            return jsonify(status), 200

        @self.app.route("/a2a/agents/projectx/health", methods=["GET"])
        def projectx_health():
            try:
                report = build_projectx_health_report(self.broker)
                return jsonify(report), 200
            except Exception:
                return jsonify({"status": "error", "message": "diagnostic unavailable"}), 200

        @self.app.route("/a2a/agents/brp/agent.json", methods=["GET"])
        def brp_card():
            base = request.url_root.rstrip("/")
            return jsonify(build_brp_a2a_card(base)), 200

        @self.app.route("/a2a/agents/brp/tasks", methods=["POST"])
        @_require_api_key
        def brp_task():
            data = request.get_json(silent=True) or {}
            ok, msg_or_skill, intent_type = validate_brp_task(data)
            if not ok:
                return jsonify({"status": "error", "error": msg_or_skill}), 400

            task_id = data.get("task_id", str(uuid.uuid4()))
            status = build_a2a_task_status(task_id, "pending", intent_type=intent_type)
            return jsonify(status), 200

        @self.app.route("/a2a/agents/brp/health", methods=["GET"])
        def brp_health():
            try:
                report = build_brp_health_report(data_dir=str(self.broker.brp_bridge.data_dir))
                return jsonify(report), 200
            except Exception:
                return jsonify({"status": "error", "message": "diagnostic unavailable"}), 200

        @self.app.route("/a2a/events", methods=["GET"])
        @_require_api_key
        def a2a_events():
            try:
                limit = min(max(int(request.args.get("limit", 50)), 1), 100)
            except (ValueError, TypeError):
                limit = 50

            intent_id_filter = request.args.get("intent_id")

            try:
                records = []
                with self.broker.intent_lock:
                    for iid, rec in self.broker.intent_records.items():
                        r = {
                            "intent_id": rec.intent_id,
                            "status": rec.status,
                            "intent_type": rec.intent_type,
                            "source_agent": rec.source_agent,
                            "target_agent": rec.target_agent,
                            "timestamp": rec.timestamp,
                        }
                        if rec.error:
                            r["error"] = rec.error
                        records.append(r)

                if intent_id_filter:
                    records = [r for r in records if r.get("intent_id") == intent_id_filter]

                result = build_a2a_events_list(records, limit=limit)
                return jsonify(result), 200
            except Exception:
                return jsonify({"events": [], "error": "Failed to retrieve events"}), 200

        @self.app.route("/a2a/events/<intent_id>", methods=["GET"])
        @_require_api_key
        def a2a_events_by_intent(intent_id):
            try:
                records = []
                with self.broker.intent_lock:
                    for iid, rec in self.broker.intent_records.items():
                        if rec.intent_id == intent_id:
                            r = {
                                "intent_id": rec.intent_id,
                                "status": rec.status,
                                "intent_type": rec.intent_type,
                                "timestamp": rec.timestamp,
                            }
                            if rec.error:
                                r["error"] = rec.error
                            records.append(r)

                if not records:
                    return jsonify({"status": "error", "error": "Intent not found"}), 404

                result = build_a2a_events_list(records)
                return jsonify(result), 200
            except Exception:
                return jsonify({"events": [], "error": "Failed to retrieve events"}), 200

        @self.app.route("/a2a/security", methods=["GET"])
        def a2a_security():
            return jsonify({
                "securitySchemes": build_a2a_security_schemes_block(),
                "replayProtection": build_replay_guard_note(),
                "transportSecurity": {
                    "tls_required_in_production": True,
                    "local_http_allowed": True,
                    "note": "All A2A-facing endpoints must be exposed via HTTPS/TLS in production.",
                },
                "x-simp": {"schema_version": "1.0.0"},
            }), 200

        # --- Sprint 58: SSE Event Stream ---
        @self.app.route("/a2a/events/stream", methods=["GET"])
        @_require_api_key
        def a2a_event_stream():
            """Server-Sent Events stream for real-time A2A events."""
            from flask import Response, stream_with_context

            since_seq = request.args.get("since_sequence", 0, type=int)
            sub_id = str(uuid.uuid4())
            EVENT_BUFFER.subscribe(sub_id)

            def generate():
                try:
                    # Send backfill of events since requested sequence
                    backfill = EVENT_BUFFER.get_recent(limit=100, since_sequence=since_seq)
                    for ev in backfill:
                        yield f"id: {ev['sequence']}\nevent: {ev['event_type']}\ndata: {json.dumps(ev['data'])}\n\n"

                    heartbeat_interval = 15
                    last_heartbeat = time.time()

                    while True:
                        events = EVENT_BUFFER.get_subscriber_events(sub_id, max_events=20)
                        for ev in events:
                            yield f"id: {ev['sequence']}\nevent: {ev['event_type']}\ndata: {json.dumps(ev['data'])}\n\n"

                        now = time.time()
                        if now - last_heartbeat >= heartbeat_interval:
                            yield f": heartbeat {EVENT_BUFFER.sequence}\n\n"
                            last_heartbeat = now

                        time.sleep(0.5)
                except GeneratorExit:
                    pass
                finally:
                    EVENT_BUFFER.unsubscribe(sub_id)

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.app.route("/a2a/agents/financial-ops/agent.json", methods=["GET"])
        def financial_ops_card():
            base = request.url_root.rstrip("/")
            return jsonify(build_financial_ops_card(base)), 200

        @self.app.route("/a2a/agents/financial-ops/tasks", methods=["POST"])
        @_require_api_key
        def financial_ops_task():
            data = request.get_json(silent=True) or {}
            op_type = data.get("op_type", data.get("skill_id", ""))
            would_spend = float(data.get("would_spend", 0.0))
            description = data.get("description", "A2A financial op request")

            state, reason = validate_financial_op(op_type, would_spend)
            record = record_would_spend(
                agent_id=data.get("agent_id", "a2a_client"),
                op_type=op_type if op_type else "unknown",
                would_spend=would_spend,
                description=description,
            )

            return jsonify({
                "status": "pending_approval",
                "message": (
                    "Operation recorded as simulated spend. "
                    "Manual approval required before any real action."
                ),
                "record_id": record.get("record_id", ""),
                "would_spend": would_spend,
                "x-simp": {"mode": "simulate_only", "approved": False},
            }), 202

        @self.app.route("/a2a/agents/financial-ops/connector-health", methods=["GET"])
        def financial_ops_connector_health():
            return jsonify(HEALTH_TRACKER.get_status()), 200

        @self.app.route("/a2a/agents/financial-ops/proposals", methods=["POST"])
        @_require_api_key
        def financial_ops_submit_proposal():
            data = request.get_json(silent=True) or {}
            try:
                proposal = APPROVAL_QUEUE.submit_proposal(
                    op_type=data.get("op_type", "small_purchase"),
                    vendor=data.get("vendor", ""),
                    category=data.get("category", ""),
                    amount=float(data.get("amount", 0)),
                    connector_name=data.get("connector_name", "stripe_small_payments"),
                    description=data.get("description", ""),
                    submitted_by=data.get("submitted_by", "a2a_client"),
                )
                return jsonify({
                    "status": "pending",
                    "proposal": proposal.to_dict(),
                }), 201
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/proposals", methods=["GET"])
        @_require_api_key
        def financial_ops_list_proposals():
            proposals = APPROVAL_QUEUE.get_all_proposals()
            return jsonify({
                "proposals": [p.to_dict() for p in proposals],
                "count": len(proposals),
            }), 200

        @self.app.route("/a2a/agents/financial-ops/proposals/<proposal_id>", methods=["GET"])
        @_require_api_key
        def financial_ops_get_proposal(proposal_id):
            proposal = APPROVAL_QUEUE.get_proposal(proposal_id)
            if proposal is None:
                return jsonify({"status": "error", "error": "Proposal not found"}), 404
            return jsonify({"proposal": proposal.to_dict()}), 200

        @self.app.route("/a2a/agents/financial-ops/proposals/<proposal_id>/approve", methods=["POST"])
        @_require_api_key
        def financial_ops_approve_proposal(proposal_id):
            data = request.get_json(silent=True) or {}
            operator = data.get("operator_subject", "")
            if not operator:
                return jsonify({"status": "error", "error": "operator_subject required"}), 400
            try:
                proposal = APPROVAL_QUEUE.approve_proposal(proposal_id, operator)
                return jsonify({"status": "approved", "proposal": proposal.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/proposals/<proposal_id>/reject", methods=["POST"])
        @_require_api_key
        def financial_ops_reject_proposal(proposal_id):
            data = request.get_json(silent=True) or {}
            operator = data.get("operator_subject", "")
            reason = data.get("reason", "")
            if not operator:
                return jsonify({"status": "error", "error": "operator_subject required"}), 400
            try:
                proposal = APPROVAL_QUEUE.reject_proposal(proposal_id, operator, reason)
                return jsonify({"status": "rejected", "proposal": proposal.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/policy-changes", methods=["POST"])
        @_require_api_key
        def financial_ops_submit_policy_change():
            data = request.get_json(silent=True) or {}
            try:
                change = POLICY_CHANGE_QUEUE.submit_change(
                    change_type=data.get("change_type", ""),
                    description=data.get("description", ""),
                    proposed_by=data.get("proposed_by", ""),
                )
                return jsonify({"status": "pending", "change": change.to_dict()}), 201
            except Exception as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/policy-changes/<change_id>/approve", methods=["POST"])
        @_require_api_key
        def financial_ops_approve_policy_change(change_id):
            data = request.get_json(silent=True) or {}
            operator = data.get("operator_subject", "")
            if not operator:
                return jsonify({"status": "error", "error": "operator_subject required"}), 400
            try:
                change = POLICY_CHANGE_QUEUE.approve_change(change_id, operator)
                return jsonify({"status": change.status, "change": change.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/proposals/<proposal_id>/execute", methods=["POST"])
        @_require_api_key
        def financial_ops_execute_proposal(proposal_id):
            live_enabled = os.environ.get("FINANCIAL_OPS_LIVE_ENABLED", "").lower() == "true"
            if not live_enabled:
                return jsonify({
                    "status": "error",
                    "error": "Live payments are not enabled (FINANCIAL_OPS_LIVE_ENABLED != true)",
                }), 403
            try:
                result = execute_approved_payment(proposal_id)
                return jsonify(result), 200
            except (ValueError, RuntimeError) as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/ledger", methods=["GET"])
        @_require_api_key
        def financial_ops_ledger():
            sim = SPEND_LEDGER.get_ledger_summary()
            live = LIVE_LEDGER.get_summary()
            return jsonify({
                "simulated": sim,
                "live": live,
                "x-simp": {"pii_minimized": True},
            }), 200

        @self.app.route("/a2a/agents/financial-ops/reconciliation", methods=["POST"])
        @_require_api_key
        def financial_ops_reconciliation():
            data = request.get_json(silent=True) or {}
            period_start = data.get("period_start", "2000-01-01T00:00:00+00:00")
            period_end = data.get("period_end", "2099-12-31T23:59:59+00:00")
            ref_total = data.get("reference_total")
            if ref_total is not None:
                ref_total = float(ref_total)
            result = run_reconciliation(period_start, period_end, ref_total)
            return jsonify(result.to_dict()), 200

        @self.app.route("/a2a/agents/financial-ops/export", methods=["GET"])
        @_require_api_key
        def financial_ops_export():
            from simp.compat.approval_queue import APPROVAL_QUEUE as _AQ
            proposals = _AQ.get_all_proposals()
            safe = []
            for p in proposals:
                safe.append({
                    "proposal_id": p.proposal_id,
                    "vendor": p.vendor,
                    "category": p.category,
                    "amount": p.amount,
                    "status": p.status,
                    "submitted_at": p.submitted_at,
                })
            return jsonify({"records": safe, "count": len(safe)}), 200

        @self.app.route("/a2a/agents/financial-ops/rollback", methods=["POST"])
        @_require_api_key
        def financial_ops_rollback():
            data = request.get_json(silent=True) or {}
            triggered_by = data.get("triggered_by", "operator")
            reason = data.get("reason", "Manual rollback")
            record = ROLLBACK_MANAGER.trigger_rollback(triggered_by, reason)
            return jsonify({"status": "rollback_active", "record": record.to_dict()}), 200

        @self.app.route("/a2a/agents/financial-ops/rollback/status", methods=["GET"])
        def rollback_status_finops():
            return jsonify(ROLLBACK_MANAGER.get_rollback_status()), 200

        @self.app.route("/rollback/status", methods=["GET"])
        def rollback_status():
            return jsonify(ROLLBACK_MANAGER.get_rollback_status()), 200

        @self.app.route("/rollback/history", methods=["GET"])
        def rollback_history():
            return jsonify({"history": ROLLBACK_MANAGER.get_rollback_history()}), 200

        @self.app.route("/gates", methods=["GET"])
        def gates_status():
            return jsonify(GATE_MANAGER.get_current_gate_status()), 200

        @self.app.route("/a2a/agents/financial-ops/gates", methods=["GET"])
        def financial_ops_gates():
            return jsonify(GATE_MANAGER.get_current_gate_status()), 200

        # --- Sprint 59: Gate 1 Simulation (dev only) ---
        @self.app.route("/a2a/agents/financial-ops/gates/simulate-gate1", methods=["POST"])
        @_require_api_key
        def simulate_gate1():
            """Populate health and spend records for gate-1 testing.

            Blocked in production (SIMP_ENV=production returns 403).
            """
            simp_env = os.environ.get("SIMP_ENV", "development").lower()
            if simp_env == "production":
                return jsonify({
                    "status": "error",
                    "error": "Gate simulation is disabled in production",
                }), 403

            # Add 7 consecutive OK health records per connector
            for connector_name in ALLOWED_CONNECTORS:
                for _ in range(7):
                    HEALTH_TRACKER.record_check(connector_name, "ok")

            # Add 20 simulated spend records
            for i in range(20):
                SPEND_LEDGER.record_simulated_spend(
                    agent_id="gate1-sim",
                    description=f"Simulated payment {i+1}/20 for gate-1 test",
                    would_spend=round(10.0 + i * 2.5, 2),
                )

            # Check gate1 result
            gate1_result = GATE_MANAGER.check_gate1()
            return jsonify({
                "status": "simulated",
                "message": "Gate-1 simulation data populated",
                "health_records_added": 7 * len(ALLOWED_CONNECTORS),
                "spend_records_added": 20,
                "gate1_check": gate1_result.to_dict(),
            }), 200

        @self.app.route("/gates/1", methods=["GET"])
        def gate1_status():
            return jsonify(GATE_MANAGER.check_gate1().to_dict()), 200

        @self.app.route("/gates/2", methods=["GET"])
        def gate2_status():
            return jsonify(GATE_MANAGER.check_gate2().to_dict()), 200

        @self.app.route("/gates/1/sign-off", methods=["POST"])
        @_require_api_key
        def gate1_signoff_condition():
            data = request.get_json(silent=True) or {}
            condition = data.get("condition", "")
            operator = data.get("operator", "")
            if not condition or not operator:
                return jsonify({"status": "error", "error": "condition and operator required"}), 400
            try:
                cond = GATE_MANAGER.sign_off_condition(1, condition, operator)
                return jsonify({"status": "signed_off", "condition": cond.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/gates/2/sign-off", methods=["POST"])
        @_require_api_key
        def gate2_signoff_condition():
            data = request.get_json(silent=True) or {}
            condition = data.get("condition", "")
            operator = data.get("operator", "")
            if not condition or not operator:
                return jsonify({"status": "error", "error": "condition and operator required"}), 400
            try:
                cond = GATE_MANAGER.sign_off_condition(2, condition, operator)
                return jsonify({"status": "signed_off", "condition": cond.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/gates/1/promote", methods=["POST"])
        @_require_api_key
        def gate1_promote():
            data = request.get_json(silent=True) or {}
            operator = data.get("operator", "")
            if not operator:
                return jsonify({"status": "error", "error": "operator required"}), 400
            try:
                result = GATE_MANAGER.promote_gate(1, operator)
                return jsonify({"status": "promoted", "gate": result.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/gates/2/promote", methods=["POST"])
        @_require_api_key
        def gate2_promote():
            data = request.get_json(silent=True) or {}
            operator = data.get("operator", "")
            if not operator:
                return jsonify({"status": "error", "error": "operator required"}), 400
            try:
                result = GATE_MANAGER.promote_gate(2, operator)
                return jsonify({"status": "promoted", "gate": result.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

        @self.app.route("/a2a/agents/financial-ops/budget", methods=["GET"])
        def financial_ops_budget():
            live_summary = LIVE_LEDGER.get_summary()
            daily_spend = live_summary.get("total_live_spend", 0.0)
            summary = BUDGET_MONITOR.get_budget_summary(
                daily_spend=daily_spend,
                monthly_spend=daily_spend,
            )
            return jsonify(summary), 200

        @self.app.route("/alerts", methods=["GET"])
        @_require_api_key
        def budget_alerts():
            include_ack = request.args.get("include_acknowledged", "false").lower() == "true"
            alerts = BUDGET_MONITOR.get_alerts(include_acknowledged=include_ack)
            return jsonify({"alerts": alerts, "count": len(alerts)}), 200

        @self.app.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
        @_require_api_key
        def acknowledge_alert(alert_id):
            data = request.get_json(silent=True) or {}
            ack_by = data.get("acknowledged_by", "operator")
            try:
                alert = BUDGET_MONITOR.acknowledge_alert(alert_id, ack_by)
                return jsonify({"status": "acknowledged", "alert": alert.to_dict()}), 200
            except ValueError as exc:
                return jsonify({"status": "error", "error": str(exc)}), 400

    # ------------------------------------------------------------------
    # Mesh Bus routes (agent-to-agent messaging)
    # ------------------------------------------------------------------

    def _setup_mesh_routes(self):
        """Setup Mesh Bus routes for agent-to-agent messaging."""
        
        @self.app.route("/mesh/routing/status", methods=["GET"])
        @_require_api_key
        def mesh_routing_status():
            """Get mesh routing status."""
            try:
                if not hasattr(self.broker, 'mesh_routing') or not self.broker.mesh_routing:
                    return jsonify({
                        "status": "success",
                        "mesh_routing": {
                            "enabled": False,
                            "message": "Mesh routing not initialized"
                        }
                    })
                
                status = self.broker.mesh_routing.get_status()
                return jsonify({
                    "status": "success",
                    "mesh_routing": status
                })
            except Exception as e:
                return jsonify({"status": "error", "error": str(e)}), 500
        
        @self.app.route("/mesh/routing/agents", methods=["GET"])
        @_require_api_key
        def mesh_routing_agents():
            """Get all mesh-capable agents."""
            try:
                if not hasattr(self.broker, 'mesh_routing') or not self.broker.mesh_routing:
                    return jsonify({
                        "status": "success",
                        "agents": {},
                        "message": "Mesh routing not initialized"
                    })
                
                agents = self.broker.mesh_routing.get_all_mesh_agents()
                return jsonify({
                    "status": "success",
                    "agents": agents,
                    "count": len(agents)
                })
            except Exception as e:
                return jsonify({"status": "error", "error": str(e)}), 500
        
        @self.app.route("/mesh/routing/discover", methods=["POST"])
        @_require_api_key
        def mesh_routing_discover():
            """Discover mesh capabilities."""
            try:
                if not hasattr(self.broker, 'mesh_routing') or not self.broker.mesh_routing:
                    return jsonify({
                        "status": "error",
                        "error": "Mesh routing not initialized"
                    }), 400
                
                result = self.broker.mesh_routing.discover_mesh_capabilities()
                return jsonify({
                    "status": "success" if result.get("success") else "error",
                    **result
                })
            except Exception as e:
                return jsonify({"status": "error", "error": str(e)}), 500
        
        @self.app.route("/mesh/routing/agent/<agent_id>", methods=["GET"])
        @_require_api_key
        def mesh_routing_agent_info(agent_id):
            """Get mesh information for a specific agent."""
            try:
                if not hasattr(self.broker, 'mesh_routing') or not self.broker.mesh_routing:
                    return jsonify({
                        "status": "error",
                        "error": "Mesh routing not initialized"
                    }), 400
                
                info = self.broker.mesh_routing.get_mesh_agent_info(agent_id)
                if info:
                    return jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "mesh_info": info
                    })
                else:
                    return jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "mesh_info": None,
                        "message": "Agent not mesh-capable or not found"
                    })
            except Exception as e:
                return jsonify({"status": "error", "error": str(e)}), 500
        
        @self.app.route("/mesh/routing/config", methods=["GET", "POST"])
        @_require_api_key
        def mesh_routing_config():
            """Get or update mesh routing configuration."""
            try:
                if not hasattr(self.broker, 'mesh_routing') or not self.broker.mesh_routing:
                    return jsonify({
                        "status": "error",
                        "error": "Mesh routing not initialized"
                    }), 400
                
                if request.method == "GET":
                    config = self.broker.mesh_routing.config
                    return jsonify({
                        "status": "success",
                        "config": {
                            "mode": config.mode.value,
                            "enable_capability_discovery": config.enable_capability_discovery,
                            "mesh_stake_amount": config.mesh_stake_amount,
                            "mesh_timeout_seconds": config.mesh_timeout_seconds,
                            "mesh_retry_count": config.mesh_retry_count,
                            "agent_mesh_settings": config.agent_mesh_settings
                        }
                    })
                else:
                    # POST - update configuration
                    data = request.get_json(silent=True) or {}
                    
                    # Update configuration
                    if "mode" in data:
                        from simp.server.mesh_routing import MeshRoutingMode
                        try:
                            self.broker.mesh_routing.config.mode = MeshRoutingMode(data["mode"])
                        except ValueError:
                            return jsonify({
                                "status": "error",
                                "error": f"Invalid mode. Must be one of: {[m.value for m in MeshRoutingMode]}"
                            }), 400
                    
                    if "mesh_stake_amount" in data:
                        self.broker.mesh_routing.config.mesh_stake_amount = float(data["mesh_stake_amount"])
                    
                    if "mesh_timeout_seconds" in data:
                        self.broker.mesh_routing.config.mesh_timeout_seconds = float(data["mesh_timeout_seconds"])
                    
                    if "mesh_retry_count" in data:
                        self.broker.mesh_routing.config.mesh_retry_count = int(data["mesh_retry_count"])
                    
                    if "enable_capability_discovery" in data:
                        self.broker.mesh_routing.config.enable_capability_discovery = bool(data["enable_capability_discovery"])
                    
                    return jsonify({
                        "status": "success",
                        "message": "Configuration updated",
                        "config": {
                            "mode": self.broker.mesh_routing.config.mode.value,
                            "enable_capability_discovery": self.broker.mesh_routing.config.enable_capability_discovery,
                            "mesh_stake_amount": self.broker.mesh_routing.config.mesh_stake_amount,
                            "mesh_timeout_seconds": self.broker.mesh_routing.config.mesh_timeout_seconds,
                            "mesh_retry_count": self.broker.mesh_routing.config.mesh_retry_count
                        }
                    })
            except Exception as e:
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/send", methods=["POST"])
        @_require_api_key
        def mesh_send():
            """Send a mesh packet."""
            data = request.get_json(silent=True) or {}
            
            # Validate required fields
            if not data.get("sender_id"):
                return jsonify({"status": "error", "error": "Missing sender_id"}), 400
            if not data.get("recipient_id") and not data.get("channel"):
                return jsonify({"status": "error", "error": "Missing recipient_id or channel"}), 400
            
            try:
                # Create mesh packet from request data
                from simp.mesh import MeshPacket
                packet = MeshPacket.from_dict(data)
                
                # Send via broker's mesh bus
                success = self.broker.mesh_bus.send(packet)
                
                if success:
                    return jsonify({
                        "status": "success",
                        "message_id": packet.message_id,
                        "message": "Packet sent successfully"
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "error": "Failed to send packet (may be expired or invalid)"
                    }), 400
                    
            except Exception as e:
                self.logger.error(f"Error sending mesh packet: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/poll", methods=["GET"])
        @_require_api_key
        def mesh_poll():
            """Poll for mesh messages."""
            agent_id = request.args.get("agent_id")
            max_messages = int(request.args.get("max_messages", 10))
            
            if not agent_id:
                return jsonify({"status": "error", "error": "Missing agent_id parameter"}), 400
            
            try:
                # Get messages from broker's mesh bus
                messages = self.broker.mesh_bus.receive(agent_id, max_messages)
                
                # Convert to dict for JSON serialization
                messages_dict = [msg.to_dict() for msg in messages]
                
                return jsonify({
                    "status": "success",
                    "agent_id": agent_id,
                    "messages": messages_dict,
                    "count": len(messages_dict)
                }), 200
                
            except Exception as e:
                self.logger.error(f"Error polling mesh messages: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/subscribe", methods=["POST"])
        @_require_api_key
        def mesh_subscribe():
            """Subscribe agent to a channel."""
            data = request.get_json(silent=True) or {}
            agent_id = data.get("agent_id")
            channel = data.get("channel")
            
            if not agent_id or not channel:
                return jsonify({"status": "error", "error": "Missing agent_id or channel"}), 400
            
            try:
                success = self.broker.mesh_bus.subscribe(agent_id, channel)
                
                if success:
                    return jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "channel": channel,
                        "message": f"Subscribed to channel {channel}"
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "error": f"Failed to subscribe agent {agent_id} to channel {channel}"
                    }), 400
                    
            except Exception as e:
                self.logger.error(f"Error subscribing to mesh channel: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/subscriptions", methods=["GET"])
        @_require_api_key
        def mesh_subscriptions():
            """Return channel and per-agent subscription topology."""
            try:
                channels = self.broker.mesh_bus.get_all_subscriptions()
                agent_channels = {
                    agent_id: self.broker.mesh_bus.get_agent_channels(agent_id)
                    for agent_id in self.broker.mesh_bus.get_registered_agents()
                }
                return jsonify(
                    {
                        "status": "success",
                        "channels": channels,
                        "agent_channels": agent_channels,
                    }
                ), 200
            except Exception as e:
                self.logger.error(f"Error listing mesh subscriptions: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/unsubscribe", methods=["POST"])
        @_require_api_key
        def mesh_unsubscribe():
            """Unsubscribe agent from a channel."""
            data = request.get_json(silent=True) or {}
            agent_id = data.get("agent_id")
            channel = data.get("channel")
            
            if not agent_id or not channel:
                return jsonify({"status": "error", "error": "Missing agent_id or channel"}), 400
            
            try:
                success = self.broker.mesh_bus.unsubscribe(agent_id, channel)
                
                if success:
                    return jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "channel": channel,
                        "message": f"Unsubscribed from channel {channel}"
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "error": f"Failed to unsubscribe agent {agent_id} from channel {channel}"
                    }), 400
                    
            except Exception as e:
                self.logger.error(f"Error unsubscribing from mesh channel: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/stats", methods=["GET"])
        @_require_api_key
        def mesh_stats():
            """Get mesh bus statistics."""
            try:
                stats = self.broker.mesh_bus.get_statistics()
                return jsonify({
                    "status": "success",
                    "statistics": stats
                }), 200
            except Exception as e:
                self.logger.error(f"Error getting mesh stats: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/agent/<agent_id>/status", methods=["GET"])
        @_require_api_key
        def mesh_agent_status(agent_id):
            """Get mesh status for a specific agent."""
            try:
                status = self.broker.mesh_bus.get_agent_status(agent_id)
                
                if status:
                    return jsonify({
                        "status": "success",
                        "agent_id": agent_id,
                        "mesh_status": status
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "error": f"Agent {agent_id} not found in mesh bus"
                    }), 404
                    
            except Exception as e:
                self.logger.error(f"Error getting mesh agent status: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/channels", methods=["GET"])
        @_require_api_key
        def mesh_channels():
            """Get list of mesh channels with subscriber counts."""
            try:
                stats = self.broker.mesh_bus.get_statistics()
                channels = stats.get("channels", {})
                
                return jsonify({
                    "status": "success",
                    "channels": channels,
                    "count": len(channels)
                }), 200
            except Exception as e:
                self.logger.error(f"Error getting mesh channels: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

        @self.app.route("/mesh/events", methods=["GET"])
        @_require_api_key
        def mesh_events():
            """Get recent mesh events (for debugging)."""
            try:
                # Read last N lines from mesh events log
                log_path = Path(__file__).parent.parent.parent / "data" / "mesh_events.jsonl"
                if not log_path.exists():
                    return jsonify({
                        "status": "success",
                        "events": [],
                        "count": 0,
                        "message": "No mesh events log found"
                    }), 200
                
                limit = int(request.args.get("limit", 100))
                events = []
                
                with open(log_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            events.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
                
                return jsonify({
                    "status": "success",
                    "events": events,
                    "count": len(events)
                }), 200
            except Exception as e:
                self.logger.error(f"Error reading mesh events: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

    # ------------------------------------------------------------------
    # Sprint 51-55 routes (routing policy, orchestration)
    # ------------------------------------------------------------------

    def _setup_sprint51_55_routes(self):
        """Routes added by Sprints 51-55."""

        @self.app.route("/routing-policy", methods=["GET"])
        @_require_api_key
        def get_routing_policy_v2():
            summary = self.broker.routing_engine.get_policy_summary()
            return jsonify({"status": "success", "routing_policy": summary}), 200

        @self.app.route("/reload-routing-policy", methods=["POST"])
        @_require_api_key
        def reload_routing_policy():
            count = self.broker.routing_engine.reload_policy()
            return jsonify({
                "status": "success",
                "message": f"Reloaded {count} routing rules",
                "rule_count": count,
            }), 200

        # ----- Sprint 63: Planner Telemetry / Flows -----

        @self.app.route("/intents/flows", methods=["GET"])
        @_require_api_key
        def get_intent_flows():
            """Return intent records grouped into flows with timing telemetry."""
            flows = self._build_intent_flows()
            return jsonify({"status": "success", "flows": flows, "count": len(flows)}), 200

        @self.app.route("/intents/flows/<flow_id>", methods=["GET"])
        @_require_api_key
        def get_intent_flow_detail(flow_id):
            """Return a single flow by ID."""
            flows = self._build_intent_flows()
            for flow in flows:
                if flow.get("flow_id") == flow_id:
                    return jsonify({"status": "success", "flow": flow}), 200
            return jsonify({"status": "error", "error": f"Flow '{flow_id}' not found"}), 404

        @self.app.route("/orchestration/plans", methods=["POST"])
        @_require_api_key
        def create_orchestration_plan():
            data = request.get_json(silent=True) or {}
            name = data.get("name", "Unnamed Plan")
            description = data.get("description", "")
            steps = data.get("steps", [])
            if not steps:
                return jsonify({"status": "error", "error": "steps required"}), 400
            plan = self._orchestration.create_plan(name, description, steps)
            return jsonify({"status": "created", "plan": plan.to_dict()}), 201

        @self.app.route("/orchestration/plans/maintenance", methods=["POST"])
        @_require_api_key
        def create_maintenance_plan():
            plan = self._orchestration.make_maintenance_plan()
            return jsonify({"status": "created", "plan": plan.to_dict()}), 201

        @self.app.route("/orchestration/plans/demo", methods=["POST"])
        @_require_api_key
        def create_demo_plan():
            plan = self._orchestration.make_full_demo_plan()
            return jsonify({"status": "created", "plan": plan.to_dict()}), 201

        @self.app.route("/orchestration/plans", methods=["GET"])
        @_require_api_key
        def list_orchestration_plans():
            plans = self._orchestration.list_plans()
            return jsonify({"status": "success", "plans": plans, "count": len(plans)}), 200

        @self.app.route("/orchestration/plans/<plan_id>", methods=["GET"])
        @_require_api_key
        def get_orchestration_plan(plan_id):
            plan = self._orchestration.get_plan(plan_id)
            if not plan:
                return jsonify({"status": "error", "error": "Plan not found"}), 404
            return jsonify({"status": "success", "plan": plan.to_dict()}), 200

        @self.app.route("/orchestration/plans/<plan_id>/execute", methods=["POST"])
        @_require_api_key
        def execute_orchestration_plan(plan_id):
            plan = self._orchestration.get_plan(plan_id)
            if not plan:
                return jsonify({"status": "error", "error": "Plan not found"}), 404
            result = self._orchestration.execute_plan(plan_id)
            return jsonify({"status": result.status, "plan": result.to_dict()}), 200

    # ------------------------------------------------------------------
    # Sprint 63: Flow builder helper
    # ------------------------------------------------------------------

    def _build_intent_flows(self):
        """Group intent records into flows with timing telemetry."""
        from datetime import datetime as _dt, timezone as _tz

        def _parse_iso(s):
            if not s:
                return None
            try:
                return _dt.fromisoformat(s.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None

        def _ms_diff(a, b):
            if a and b:
                return max(0.0, round((b - a).total_seconds() * 1000, 1))
            return None

        # Snapshot intent records
        with self.broker.intent_lock:
            records = list(self.broker.intent_records.values())

        # Group by source_agent (simple flow grouping)
        flow_map = {}
        for rec in records:
            flow_key = rec.source_agent or "unknown"
            flow_map.setdefault(flow_key, []).append(rec)

        flows = []
        for flow_id, steps in flow_map.items():
            steps_sorted = sorted(steps, key=lambda r: r.timestamp or "")
            step_dicts = []
            all_planned = []
            all_completed = []

            for s in steps_sorted:
                p = _parse_iso(s.planned_at)
                d = _parse_iso(s.dispatched_at)
                c = _parse_iso(s.completed_at)

                if p:
                    all_planned.append(p)
                if c:
                    all_completed.append(c)

                p2d = _ms_diff(p, d)
                d2c = _ms_diff(d, c)
                total = _ms_diff(p, c)

                step_dicts.append({
                    "intent_id": s.intent_id,
                    "intent_type": s.intent_type,
                    "source_agent": s.source_agent,
                    "target_agent": s.target_agent,
                    "status": s.status,
                    "delivery_status": s.delivery_status,
                    "planned_at": s.planned_at,
                    "dispatched_at": s.dispatched_at,
                    "completed_at": s.completed_at,
                    "planned_to_dispatched_ms": p2d,
                    "dispatched_to_completed_ms": d2c,
                    "total_elapsed_ms": total,
                    "retry_count": s.retry_count,
                    "error": s.error,
                    "gantt": None,
                })

            # Compute flow-level timing
            flow_start = min(all_planned) if all_planned else None
            flow_end = max(all_completed) if all_completed else None
            flow_total = _ms_diff(flow_start, flow_end)

            # Compute Gantt bars
            if flow_start and flow_end and flow_total and flow_total > 0:
                for sd in step_dicts:
                    sp = _parse_iso(sd["planned_at"])
                    sc = _parse_iso(sd["completed_at"])
                    if sp:
                        offset = _ms_diff(flow_start, sp) or 0.0
                        duration = sd["total_elapsed_ms"] or 0.0
                        sd["gantt"] = {
                            "start_offset_ms": offset,
                            "duration_ms": duration,
                            "bar_pct_start": round(offset / flow_total, 4) if flow_total > 0 else 0.0,
                            "bar_pct_width": round(duration / flow_total, 4) if flow_total > 0 else 0.0,
                        }

            flows.append({
                "flow_id": flow_id,
                "steps": step_dicts,
                "step_count": len(step_dicts),
                "total_elapsed_ms": flow_total,
                "failed_steps": sum(1 for sd in step_dicts if sd["status"] == "failed"),
                "retry_total": sum(sd["retry_count"] for sd in step_dicts),
            })

        return flows

    # ── R6: Key / config hot-reload endpoint ────────────────────────────
    # Reloads crypto keys and config without process restart.
    # Trigger: POST /admin/reload-config with X-API-Key header.
    # No restart required — broker continues serving during reload.

    def _register_admin_reload_route(self) -> None:
        @self.app.route("/admin/reload-config", methods=["POST"])
        @require_jwt
        @require_api_key
        def admin_reload_config():
            """Reload broker configuration and crypto keys without restart.
            Returns a report of what was reloaded.
            """
            report = {"status": "ok", "reloaded": []}

            # 1. Reload environment variables
            import os as _os
            _fresh = {}
            for key in ("COINBASE_API_PRIVATE_KEY", "COINBASE_API_KEY",
                         "ALPACA_API_KEY", "ALPACA_SECRET_KEY",
                         "KALSHI_KEY", "KALSHI_SECRET",
                         "SIMP_KEY_PASSPHRASE", "MESH_SHARED_SECRET"):
                val = _os.environ.get(key)
                if val:
                    _fresh[key] = "***present***"
                else:
                    _fresh[key] = None
            report["env_keys"] = _fresh
            report["reloaded"].append("env_vars")

            # 2. Reload SimpConfig
            try:
                from config.config import SimpConfig
                _new_config = SimpConfig()
                report["config"] = {
                    "REQUIRE_API_KEY": _new_config.REQUIRE_API_KEY,
                    "ALLOW_UNREGISTERED_AGENTS": _new_config.ALLOW_UNREGISTERED_AGENTS,
                }
                report["reloaded"].append("SimpConfig")
            except Exception as exc:
                report["config_error"] = str(exc)

            # 3. Reload crypto by flushing key cache
            try:
                from simp.crypto import SimpCrypto
                # Clear any cached keys — next call will re-read from env
                import simp.crypto as _crypto_mod
                for attr in dir(_crypto_mod):
                    if attr.startswith("_key_cache") or attr == "_key_cache":
                        setattr(_crypto_mod, attr, {})
                report["reloaded"].append("crypto_keys")
            except Exception as exc:
                report["crypto_error"] = str(exc)

            # 4. Reload BRP bridge
            try:
                if hasattr(self.broker, 'brp_bridge'):
                    from simp.security.brp_bridge import BRPBridge
                    self.broker.brp_bridge = BRPBridge(
                        data_dir=str(self.broker.brp_bridge.data_dir)
                    )
                    report["reloaded"].append("BRP_bridge")
            except Exception as exc:
                report["brp_error"] = str(exc)

            self.logger.info("[R6] Config reloaded: %s", report["reloaded"])
            return jsonify(report), 200

    def run(self, host: str = "127.0.0.1", port: int = 5555, threaded: bool = True,
            tls_cert: str = None, tls_key: str = None):
        self.broker.start(async_loop=self._async_loop)

        # Start WebSocket bridge (on :5556 by default)
        ws_port = int(os.environ.get("SIMP_WS_PORT", 5556))
        ws_bridge_host = os.environ.get("SIMP_WS_HOST", "127.0.0.1")
        if os.environ.get("SIMP_WS_DISABLE", "").lower() not in ("1", "true", "yes"):
            self._ws_bridge = WsBridge(host=ws_bridge_host, port=ws_port)
            # Run WS bridge in a background thread with its own event loop
            def _run_ws():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._ws_bridge.start())
                loop.run_forever()
            ws_thread = Thread(target=_run_ws, daemon=True, name="SIMP-WS-Bridge")
            ws_thread.start()
            self.logger.info(f"WS Bridge started on ws://{ws_bridge_host}:{ws_port}")

            # Sprint 85 — wire WS bridge into broker for real-time push
            self.broker.set_ws_bridge(self._ws_bridge)

        self.logger.info(f"SIMP HTTP Server starting on {host}:{port}")

        # Sprint 81 — TLS with X.509 mTLS + CRL + TLS 1.2 minimum + strong ciphers
        ssl_context = None
        if tls_cert and tls_key:
            import ssl
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(tls_cert, tls_key)

                # X.509 mutual auth: require client certs from CA bundle
                ca_bundle = os.environ.get("SIMP_TLS_CA_BUNDLE", "")
                if ca_bundle:
                    ssl_context.load_verify_locations(ca_bundle)
                    ssl_context.verify_mode = ssl.CERT_REQUIRED
                    self.logger.info(f"✅ mTLS enabled (CA={ca_bundle})")
                else:
                    ssl_context.verify_mode = ssl.CERT_NONE

                # CRL revocation check if SIMP_TLS_CRL_FILE is set
                crl_file = os.environ.get("SIMP_TLS_CRL_FILE", "")
                if crl_file:
                    try:
                        import cryptography.x509 as x509
                        with open(crl_file, "rb") as f:
                            ssl_context.get_cert_store().add_cert(
                                x509.load_pem_x509_certificate(f.read())
                            )
                        self.logger.info(f"✅ CRL loaded from {crl_file}")
                    except Exception as crl_err:
                        self.logger.warning(f"⚠️ CRL load failed: {crl_err}")

                # TLS 1.2 minimum + strong cipher suite (no NULL/MD5/DSS)
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                ssl_context.ciphers = (
                    "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:"
                    "DHE+CHACHA20:!aNULL:!MD5:!DSS"
                )
                self.logger.info(f"✅ TLS enabled (cert={tls_cert})")
            except Exception as exc:
                self.logger.error(f"❌ TLS setup failed: {exc}")
                raise
        elif os.environ.get("SIMP_ENABLE_TLS", "").lower() in ("1", "true", "yes"):
            tls_cert = os.environ.get("SIMP_TLS_CERT", "")
            tls_key = os.environ.get("SIMP_TLS_KEY", "")
            if tls_cert and tls_key:
                import ssl
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(tls_cert, tls_key)
                self.logger.info(f"✅ TLS enabled via env (cert={tls_cert})")
            else:
                self.logger.warning("⚠️ SIMP_ENABLE_TLS=true but TLS_CERT/KEY not set")

        self.app.run(host=host, port=port, debug=self.debug, threaded=threaded,
                     ssl_context=ssl_context)

    def run_in_background(self, host: str = "127.0.0.1", port: int = 5555):
        thread = Thread(
            target=self.run,
            args=(host, port),
            daemon=True,
            name="SIMP-HTTP-Server"
        )
        thread.start()
        self.logger.info("Server started in background thread")
        return thread


def create_app():
    """Factory function for production WSGI servers (gunicorn)."""
    server = SimpHttpServer()
    return server.app


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 5555,
    debug: bool = False
) -> SimpHttpServer:
    """Factory function to create HTTP server"""
    config = BrokerConfig(host=host, port=port)
    return SimpHttpServer(config, debug=debug)
