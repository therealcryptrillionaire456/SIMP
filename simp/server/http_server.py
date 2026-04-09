"""
SIMP HTTP Server

REST API for SIMP broker, making it easy to test and interact with.
"""

import asyncio
import functools
import hmac
import json
import logging
import queue
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, Response, stream_with_context
from threading import Thread
import time

from simp.server.broker import SimpBroker, BrokerConfig
from simp.server.request_guards import (
    validate_intent_payload,
    validate_registration_payload,
    sanitize_agent_id,
)
from simp.server.validation import AgentRegistration
from simp.server.rate_limit import RateLimiter
from simp.server.control_auth import require_control_auth
from simp.memory.hooks import MemoryHooks
from simp.memory.conversation_archive import ConversationArchive
from simp.memory.task_memory import TaskMemory
from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.session_bootstrap import SessionBootstrap
from config.config import SimpConfig


def require_api_key(f):
    """Require valid API key for data-plane endpoints."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        config = SimpConfig()
        if not config.REQUIRE_API_KEY:
            return f(*args, **kwargs)

        api_keys_raw = config.API_KEYS
        if not api_keys_raw:
            # No keys configured = open access (log warning once)
            return f(*args, **kwargs)

        valid_keys = {k.strip() for k in api_keys_raw.split(",") if k.strip()}
        if not valid_keys:
            return f(*args, **kwargs)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        provided_key = ""
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            provided_key = request.headers["X-API-Key"]

        if not provided_key:
            return jsonify({"error": "API key required", "hint": "Set Authorization: Bearer <key> or X-API-Key header"}), 401

        # Constant-time comparison against all valid keys
        if not any(hmac.compare_digest(provided_key, k) for k in valid_keys):
            return jsonify({"error": "Invalid API key"}), 403

        return f(*args, **kwargs)
    return decorated


class SimpHttpServer:
    """
    HTTP REST API wrapper for SIMP Broker

    Provides endpoints for:
    - Agent registration
    - Intent routing
    - Response handling
    - Status/metrics
    - Memory layer (conversations, tasks, knowledge index, context packs)
    """

    def __init__(self, broker_config: Optional[BrokerConfig] = None, debug: bool = False):
        """Initialize HTTP server"""
        self.app = Flask("SIMP")
        # Limit request body to 64KB to prevent memory exhaustion
        self.app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 KB
        # Rate limiter
        self.limiter = RateLimiter()

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

        # Setup logging
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

        self._setup_routes()
        self.logger.info("✅ SIMP HTTP Server initialized")

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint"""
            return jsonify(self.broker.health_check()), 200

        @self.app.route("/agents/register", methods=["POST"])
        @require_api_key
        @self.limiter.limit(10)
        def register_agent():
            """Register a new agent"""
            data = request.get_json(force=False, silent=True) or {}

            # Validate registration payload
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

            # Additional Pydantic validation
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
            # Store public_key in metadata for broker to pick up
            public_key = data.get("public_key")
            if public_key:
                metadata["public_key"] = public_key

            success = self.broker.register_agent(agent_id, agent_type, endpoint, metadata)

            if success:
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
        @require_api_key
        def list_agents():
            """List all registered agents"""
            agents = self.broker.list_agents()
            return jsonify({
                "status": "success",
                "count": len(agents),
                "agents": agents
            }), 200

        @self.app.route("/agents/<agent_id>", methods=["GET"])
        @require_api_key
        def get_agent(agent_id):
            """Get agent details"""
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
            """Deregister an agent"""
            ok, err = sanitize_agent_id(agent_id)
            if not ok:
                return jsonify({
                    "status": "error",
                    "error_code": "VALIDATION_FAILED",
                    "error": f"Invalid agent_id: {err}",
                }), 400
            success = self.broker.deregister_agent(agent_id)
            if success:
                return jsonify({
                    "status": "success",
                    "message": f"Agent '{agent_id}' deregistered"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found"
                }), 404

        @self.app.route("/intents/route", methods=["POST"])
        @require_api_key
        @self.limiter.limit(60)
        def route_intent():
            """Route an intent to a target agent"""
            data = request.get_json(force=False, silent=True) or {}

            # Validate intent payload
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

            # Route intent via shared event loop
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
        @require_api_key
        def get_intent_status(intent_id):
            """Get status of an intent"""
            status = self.broker.get_intent_status(intent_id)
            if status:
                return jsonify({"status": "success", "intent": status}), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Intent '{intent_id}' not found"
                }), 404

        @self.app.route("/intents/<intent_id>/response", methods=["POST"])
        @require_api_key
        @self.limiter.limit(60)
        def record_response(intent_id):
            """Record response to an intent"""
            data = request.get_json() or {}
            execution_time = data.get("execution_time_ms", 0.0)

            success = self.broker.record_response(
                intent_id,
                data.get("response", {}),
                execution_time
            )

            if success:
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
        @require_api_key
        @self.limiter.limit(60)
        def record_error(intent_id):
            """Record error for an intent"""
            data = request.get_json() or {}
            error_msg = data.get("error", "Unknown error")
            execution_time = data.get("execution_time_ms", 0.0)

            success = self.broker.record_error(intent_id, error_msg, execution_time)

            if success:
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
        def get_stats():
            """Get broker statistics"""
            return jsonify({
                "status": "success",
                "stats": self.broker.get_statistics()
            }), 200

        @self.app.route("/status", methods=["GET"])
        def get_status():
            """Get broker status"""
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
            """Start the broker"""
            self.broker.start()
            return jsonify({
                "status": "success",
                "message": "Broker started"
            }), 200

        @self.app.route("/control/stop", methods=["POST"])
        @self.limiter.limit(5)
        @require_control_auth
        def stop_broker():
            """Stop the broker and clean up resources"""
            self.broker.stop()
            # Stop the shared async event loop
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            return jsonify({
                "status": "success",
                "message": "Broker stopped"
            }), 200

        # ----- Task Ledger Endpoints (GET-only, read-safe) -----

        @self.app.route("/tasks", methods=["GET"])
        @require_api_key
        def list_tasks():
            """List tasks from the ledger with optional filters."""
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
        @require_api_key
        def get_task(task_id):
            """Get a single task by ID."""
            task = self.broker.task_ledger.get_task(task_id)
            if task:
                return jsonify({"status": "success", "task": task}), 200
            return jsonify({
                "status": "error",
                "error": f"Task '{task_id}' not found",
            }), 404

        @self.app.route("/tasks/queue", methods=["GET"])
        @require_api_key
        def get_task_queue():
            """Get unclaimed tasks ordered by priority."""
            queue = self.broker.task_ledger.get_queue()
            return jsonify({
                "status": "success",
                "count": len(queue),
                "queue": queue,
            }), 200

        @self.app.route("/routing/policy", methods=["GET"])
        @require_api_key
        def get_routing_policy():
            """Return the current routing policy."""
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
        @require_api_key
        def get_logs():
            """Get recent structured broker events."""
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
        @require_api_key
        def list_conversations():
            """List conversations with optional filters."""
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
        @require_api_key
        def get_conversation(conv_id):
            """Get a single conversation by ID."""
            conv = self.conversation_archive.get_conversation(conv_id)
            if conv:
                return jsonify({"status": "success", "conversation": conv}), 200
            return jsonify({
                "status": "error",
                "error": f"Conversation '{conv_id}' not found",
            }), 404

        @self.app.route("/memory/conversations", methods=["POST"])
        @require_api_key
        @self.limiter.limit(30)
        def save_conversation():
            """Save a new conversation record."""
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
        @require_api_key
        def list_memory_tasks():
            """List task memory files."""
            tasks = self.task_memory.list_tasks()
            return jsonify({
                "status": "success",
                "count": len(tasks),
                "tasks": tasks,
            }), 200

        @self.app.route("/memory/tasks/<slug>", methods=["GET"])
        @require_api_key
        def get_memory_task(slug):
            """Get a task memory file by slug."""
            task = self.task_memory.get_task(slug)
            if task:
                return jsonify({"status": "success", "task": task}), 200
            return jsonify({
                "status": "error",
                "error": f"Task memory '{slug}' not found",
            }), 404

        @self.app.route("/memory/index", methods=["GET"])
        @require_api_key
        def get_knowledge_index():
            """Get the full knowledge index."""
            return jsonify({
                "status": "success",
                "index": self.knowledge_index.get_full_index(),
            }), 200

        @self.app.route("/memory/context-pack", methods=["GET"])
        @require_api_key
        def get_context_pack():
            """Generate a context pack."""
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

        # ── Sprint 41: DeerFlow Skills endpoint ──────────────────────────────
        @self.app.route("/skills", methods=["GET"])
        def list_skills():
            """
            List all skills loaded by the DeerFlow SkillLoader.

            Returns skill name, description, tools, intent_types, and file_path
            for every entry currently in the SkillRegistry.  No auth required
            so the dashboard can poll this endpoint freely.
            """
            try:
                from simp.orchestration.orchestration_loop import _get_deerflow_runtime
                df = _get_deerflow_runtime()
                if df:
                    skills = [
                        {
                            "name": s.name,
                            "description": s.description,
                            "tools": s.tools,
                            "intent_types": s.intent_types,
                            "file_path": s.file_path,
                        }
                        for s in df.skill_loader.registry.list_all()
                    ]
                    return jsonify({
                        "status": "success",
                        "count": len(skills),
                        "skills": skills,
                    }), 200
            except Exception as exc:
                self.logger.debug("GET /skills — DeerFlow unavailable: %s", exc)
            return jsonify({
                "status": "success",
                "count": 0,
                "skills": [],
                "message": "DeerFlow upgrades not active",
            }), 200

        # ── Sprint 41: SSE task-stream endpoint ──────────────────────────────
        # Global registry: task_id → list[queue.Queue]
        # Producers (subagent spawner, orchestration loop) push events here;
        # each connected SSE client drains its own queue.
        if not hasattr(self, "_sse_subscribers"):
            self._sse_subscribers: Dict[str, list] = {}
            self._sse_lock = threading.Lock()

        def _sse_publish(task_id: str, event: dict) -> None:
            """Publish an event dict to all SSE subscribers for task_id."""
            with self._sse_lock:
                queues = self._sse_subscribers.get(task_id, [])
            payload = "data: " + json.dumps(event) + "\n\n"
            for q in queues:
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass

        # Expose the publisher on the server instance so other modules can
        # import and call it:  server.sse_publish(task_id, event_dict)
        self.sse_publish = _sse_publish

        # ── Bridge: make the spawner's ws_emitter relay into SSE ─────────────
        # The spawner emits {type, task_id, ...} dicts; translate them to the
        # SSE envelope {event, task_id, data, timestamp} and forward via
        # _sse_publish.  We also try to register this with the DeerFlow runtime
        # immediately (if already loaded) and expose a method for late binding.
        def _spawner_to_sse(event: dict) -> None:
            task_id = event.get("task_id", "")
            if not task_id:
                return
            _sse_publish(task_id, {
                "event": event.get("type", "task_event"),
                "task_id": task_id,
                "data": event,
                "timestamp": datetime.utcnow().isoformat(),
            })

        def _try_register_sse_emitter():
            try:
                from simp.orchestration.orchestration_loop import _get_deerflow_runtime
                df = _get_deerflow_runtime()
                if df:
                    df.set_ws_emitter(_spawner_to_sse)
                    self.logger.info("✅ SSE emitter registered with DeerFlow spawner")
            except Exception as exc:
                self.logger.debug("SSE emitter registration deferred: %s", exc)

        _try_register_sse_emitter()

        def register_sse_with_runtime():
            """
            Call this after the DeerFlow runtime has been initialized to wire
            the SSE relay into the spawner's ws_emitter.  Safe to call multiple times.
            """
            _try_register_sse_emitter()

        self.register_sse_with_runtime = register_sse_with_runtime

        @self.app.route("/tasks/<task_id>/stream", methods=["GET"])
        def stream_task(task_id: str):
            """
            Server-Sent Events stream for a single task.

            Clients connect with:
                EventSource('/tasks/<task_id>/stream')

            Events have the shape:
                { "event": "task_started"|"task_running"|"task_completed"|
                            "task_failed"|"task_timed_out"|"task_cancelled",
                  "task_id": "...",
                  "data": { ... },
                  "timestamp": "<ISO>" }

            The stream closes automatically when a terminal event is received
            (completed / failed / timed_out / cancelled) or after a 5-minute
            no-activity timeout.
            """
            q: queue.Queue = queue.Queue(maxsize=256)
            with self._sse_lock:
                self._sse_subscribers.setdefault(task_id, []).append(q)

            # Also inject any already-known terminal state immediately
            try:
                from simp.orchestration.orchestration_loop import _get_deerflow_runtime
                df = _get_deerflow_runtime()
                if df:
                    status = df.spawner.get_status(task_id)
                    if status and status.get("status") in (
                        "completed", "failed", "timed_out", "cancelled"
                    ):
                        q.put_nowait(
                            "data: " + json.dumps({
                                "event": f"task_{status['status']}",
                                "task_id": task_id,
                                "data": status,
                                "timestamp": datetime.utcnow().isoformat(),
                            }) + "\n\n"
                        )
            except Exception:
                pass

            TERMINAL = {"task_completed", "task_failed", "task_timed_out", "task_cancelled"}
            TIMEOUT_S = 300  # 5-minute inactivity timeout

            def generate():
                try:
                    # Send a heartbeat comment immediately so the client knows
                    # the connection is live.
                    yield ": connected\n\n"
                    deadline = time.time() + TIMEOUT_S
                    while True:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            yield "data: " + json.dumps({
                                "event": "stream_timeout",
                                "task_id": task_id,
                                "timestamp": datetime.utcnow().isoformat(),
                            }) + "\n\n"
                            break
                        try:
                            chunk = q.get(timeout=min(remaining, 15.0))
                            yield chunk
                            # Parse to detect terminal event
                            try:
                                parsed = json.loads(chunk.split("data: ", 1)[1])
                                if parsed.get("event") in TERMINAL:
                                    break
                            except Exception:
                                pass
                            # Reset inactivity deadline on each real event
                            deadline = time.time() + TIMEOUT_S
                        except queue.Empty:
                            # Heartbeat to keep connection alive
                            yield ": heartbeat\n\n"
                finally:
                    with self._sse_lock:
                        bucket = self._sse_subscribers.get(task_id, [])
                        if q in bucket:
                            bucket.remove(q)
                        if not bucket:
                            self._sse_subscribers.pop(task_id, None)

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

    def run(self, host: str = "127.0.0.1", port: int = 5555, threaded: bool = True):
        """
        Run the HTTP server

        Args:
            host: Host to bind to
            port: Port to bind to
            threaded: Run in threaded mode
        """
        self.broker.start(async_loop=self._async_loop)
        self.logger.info(f"🚀 SIMP HTTP Server starting on {host}:{port}")
        self.app.run(host=host, port=port, debug=self.debug, threaded=threaded)

    def run_in_background(self, host: str = "127.0.0.1", port: int = 5555):
        """Run server in background thread"""
        thread = Thread(
            target=self.run,
            args=(host, port),
            daemon=True,
            name="SIMP-HTTP-Server"
        )
        thread.start()
        self.logger.info(f"✅ Server started in background thread")
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
