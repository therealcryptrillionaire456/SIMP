"""
SIMP HTTP Server

REST API for SIMP broker, making it easy to test and interact with.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from threading import Thread
import time

from simp.server.broker import SimpBroker, BrokerConfig
from simp.server.security_audit import SecurityAuditLog, get_audit_log

# Lazy import to avoid circular imports; used in route handlers
_validation_models_loaded = False
_AgentRegistrationRequest = None
_IntentRouteRequest = None


def _load_validation_models():
    global _validation_models_loaded, _AgentRegistrationRequest, _IntentRouteRequest
    if not _validation_models_loaded:
        from simp.server.validation import AgentRegistrationRequest, IntentRouteRequest
        _AgentRegistrationRequest = AgentRegistrationRequest
        _IntentRouteRequest = IntentRouteRequest
        _validation_models_loaded = True


class SimpHttpServer:
    """
    HTTP REST API wrapper for SIMP Broker

    Provides endpoints for:
    - Agent registration
    - Intent routing
    - Response handling
    - Status/metrics
    - Security audit log
    """

    def __init__(self, broker_config: Optional[BrokerConfig] = None, debug: bool = False):
        """Initialize HTTP server"""
        self.app = Flask("SIMP")
        self.broker = SimpBroker(broker_config or BrokerConfig())
        self.debug = debug
        self.logger = logging.getLogger("SIMP.HTTP")
        self.audit_log = get_audit_log()

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

        self._setup_hooks()
        self._setup_routes()
        self.logger.info("SIMP HTTP Server initialized")

    def _setup_hooks(self):
        """Setup before_request and after_request hooks"""

        @self.app.before_request
        def check_content_type():
            """Enforce Content-Type for POST/PUT requests"""
            if request.method in ("POST", "PUT"):
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

        @self.app.after_request
        def add_security_headers(response):
            """Add security headers to all responses"""
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Content-Security-Policy"] = "default-src 'none'"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

            # Remove server info headers
            response.headers.pop("Server", None)
            response.headers.pop("X-Powered-By", None)

            return response

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint"""
            return jsonify(self.broker.health_check()), 200

        @self.app.route("/agents/register", methods=["POST"])
        def register_agent():
            """Register a new agent"""
            _load_validation_models()
            data = request.get_json() or {}

            # Pydantic validation
            try:
                validated = _AgentRegistrationRequest(**data)
            except Exception as e:
                self.audit_log.log_event(
                    "validation_error",
                    {"path": "/agents/register", "errors": str(e)},
                    severity="medium",
                )
                return (
                    jsonify({
                        "status": "error",
                        "error": f"Validation error: {e}"
                    }),
                    400,
                )

            success = self.broker.register_agent(
                validated.agent_id, validated.agent_type,
                validated.endpoint, validated.metadata
            )

            if success:
                self.audit_log.log_event(
                    "agent_registered",
                    {"agent_id": validated.agent_id, "agent_type": validated.agent_type},
                    severity="low",
                )
                return (
                    jsonify({
                        "status": "success",
                        "agent_id": validated.agent_id,
                        "message": f"Agent '{validated.agent_id}' registered"
                    }),
                    201,
                )
            else:
                return (
                    jsonify({
                        "status": "error",
                        "error": f"Failed to register agent '{validated.agent_id}'"
                    }),
                    400,
                )

        @self.app.route("/agents", methods=["GET"])
        def list_agents():
            """List all registered agents"""
            agents = self.broker.list_agents()
            return jsonify({
                "status": "success",
                "count": len(agents),
                "agents": agents
            }), 200

        @self.app.route("/agents/<agent_id>", methods=["GET"])
        def get_agent(agent_id):
            """Get agent details"""
            agent = self.broker.get_agent(agent_id)
            if agent:
                return jsonify({"status": "success", "agent": agent}), 200
            else:
                return jsonify({
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found"
                }), 404

        @self.app.route("/agents/<agent_id>", methods=["DELETE"])
        def deregister_agent(agent_id):
            """Deregister an agent"""
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

        @self.app.route("/intents/route", methods=["POST"])
        def route_intent():
            """Route an intent to a target agent"""
            _load_validation_models()
            data = request.get_json() or {}

            # Pydantic validation
            try:
                validated = _IntentRouteRequest(**data)
            except Exception as e:
                self.audit_log.log_event(
                    "intent_rejected",
                    {"path": "/intents/route", "errors": str(e)},
                    severity="medium",
                )
                return (
                    jsonify({
                        "status": "error",
                        "error": f"Validation error: {e}"
                    }),
                    400,
                )

            # Build intent data from validated model
            intent_data = validated.model_dump(exclude_none=True)

            # Route intent — use asyncio.run() per-call for thread safety
            try:
                result = asyncio.run(self.broker.route_intent(intent_data))
                return jsonify(result), 200
            except Exception as e:
                self.logger.error(f"Error routing intent: {e}")
                return jsonify({
                    "status": "error",
                    "error": str(e)
                }), 500

        @self.app.route("/intents/<intent_id>", methods=["GET"])
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
        def start_broker():
            """Start the broker"""
            self.broker.start()
            return jsonify({
                "status": "success",
                "message": "Broker started"
            }), 200

        @self.app.route("/control/stop", methods=["POST"])
        def stop_broker():
            """Stop the broker"""
            self.broker.stop()
            return jsonify({
                "status": "success",
                "message": "Broker stopped"
            }), 200

        @self.app.route("/security/audit-log", methods=["GET"])
        def get_audit_log_endpoint():
            """Get security audit log entries.

            Query params:
            - severity: Filter by severity level
            - event_type: Filter by event type
            - limit: Max number of entries (default 100)
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

    def run(self, host: str = "127.0.0.1", port: int = 5555, threaded: bool = True):
        """
        Run the HTTP server

        Args:
            host: Host to bind to
            port: Port to bind to
            threaded: Run in threaded mode
        """
        self.broker.start()
        self.logger.info(f"SIMP HTTP Server starting on {host}:{port}")
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
        self.logger.info(f"Server started in background thread")
        return thread


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 5555,
    debug: bool = False
) -> SimpHttpServer:
    """Factory function to create HTTP server"""
    config = BrokerConfig(host=host, port=port)
    return SimpHttpServer(config, debug=debug)
