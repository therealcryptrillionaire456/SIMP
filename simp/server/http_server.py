"""
SIMP HTTP Server

REST API for SIMP broker, making it easy to test and interact with.
Includes A2A compatibility routes (Sprints 2-6, S1-S9).
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from threading import Thread
import time

from simp.server.broker import SimpBroker, BrokerConfig

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
from simp.compat.event_stream import build_a2a_event, build_a2a_events_list
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

# Max payload for A2A task submissions (64 KB)
_A2A_MAX_PAYLOAD = 64 * 1024


def _require_api_key(f):
    """Decorator: reject requests without a valid X-API-Key header (unless disabled)."""
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if os.environ.get("SIMP_REQUIRE_API_KEY", "true").lower() in ("false", "0", "no"):
            return f(*args, **kwargs)
        key = request.headers.get("X-API-Key", "")
        expected = os.environ.get("SIMP_API_KEY", "")
        if not expected:
            # No key configured — allow (dev mode)
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
    - A2A compatibility (agent cards, task translation, events, security)
    """

    def __init__(self, broker_config: Optional[BrokerConfig] = None, debug: bool = False):
        """Initialize HTTP server"""
        self.app = Flask("SIMP")
        self.broker = SimpBroker(broker_config or BrokerConfig())
        self.debug = debug
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

        # A2A card generator
        self._card_gen = AgentCardGenerator()

        self._setup_routes()
        self._setup_a2a_routes()
        self.logger.info("SIMP HTTP Server initialized")

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health", methods=["GET"])
        def health():
            """Health check endpoint"""
            return jsonify(self.broker.health_check()), 200

        @self.app.route("/agents/register", methods=["POST"])
        def register_agent():
            """Register a new agent"""
            data = request.get_json() or {}

            agent_id = data.get("agent_id")
            agent_type = data.get("agent_type")
            endpoint = data.get("endpoint")
            metadata = data.get("metadata", {})

            if not all([agent_id, agent_type, endpoint]):
                return (
                    jsonify({
                        "status": "error",
                        "error": "Missing required fields: agent_id, agent_type, endpoint"
                    }),
                    400,
                )

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
            import asyncio

            data = request.get_json() or {}

            # Validate intent
            if "target_agent" not in data:
                return (
                    jsonify({
                        "status": "error",
                        "error": "Missing required field: target_agent"
                    }),
                    400,
                )

            # Route intent
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.broker.route_intent(data))
                return jsonify(result), 200
            finally:
                loop.close()

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

    # ------------------------------------------------------------------
    # A2A compatibility routes
    # ------------------------------------------------------------------

    def _setup_a2a_routes(self):
        """Setup A2A compatibility routes (Sprints 2-6, S1-S9)."""

        # --- Well-known agent card (Sprint 1) ---
        @self.app.route("/.well-known/agent-card.json", methods=["GET"])
        def well_known_card():
            card = self._card_gen.build_broker_card(self.broker.agents)
            return jsonify(card), 200

        # --- A2A task submission (Sprint 2) ---
        @self.app.route("/a2a/tasks", methods=["POST"])
        @_require_api_key
        def a2a_submit_task():
            # Payload size check (Sprint 6 — 64KB limit)
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

        # --- ProjectX agent card + tasks (Sprint S2) ---
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

        # --- ProjectX health (Sprint S6) ---
        @self.app.route("/a2a/agents/projectx/health", methods=["GET"])
        def projectx_health():
            try:
                report = build_projectx_health_report(self.broker)
                return jsonify(report), 200
            except Exception:
                return jsonify({"status": "error", "message": "diagnostic unavailable"}), 200

        # --- Events (Sprint S3) ---
        @self.app.route("/a2a/events", methods=["GET"])
        @_require_api_key
        def a2a_events():
            try:
                limit = min(max(int(request.args.get("limit", 50)), 1), 100)
            except (ValueError, TypeError):
                limit = 50

            intent_id_filter = request.args.get("intent_id")

            try:
                # Build records from broker intent_records
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

        # --- Security info (Sprint S5) ---
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

        # --- Financial ops (Sprint S7) ---
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
            # Always record the simulated spend regardless
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

        # --- Connector health (Sprint 42) ---
        @self.app.route("/a2a/agents/financial-ops/connector-health", methods=["GET"])
        def financial_ops_connector_health():
            """Return connector health status (unauthenticated, no secrets)."""
            return jsonify(HEALTH_TRACKER.get_status()), 200

        # --- Proposal routes (Sprint 43) ---
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

        # --- Policy change routes (Sprint 43) ---
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

        # --- Execute approved payment (Sprint 44) ---
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

        # --- Ledger (Sprint 45) ---
        @self.app.route("/a2a/agents/financial-ops/ledger", methods=["GET"])
        @_require_api_key
        def financial_ops_ledger():
            """Combined simulated + live ledger, PII-minimized."""
            sim = SPEND_LEDGER.get_ledger_summary()
            live = LIVE_LEDGER.get_summary()
            return jsonify({
                "simulated": sim,
                "live": live,
                "x-simp": {"pii_minimized": True},
            }), 200

        # --- Reconciliation (Sprint 45) ---
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

        # --- Export (Sprint 45) ---
        @self.app.route("/a2a/agents/financial-ops/export", methods=["GET"])
        @_require_api_key
        def financial_ops_export():
            """Export safe fields only."""
            from simp.compat.approval_queue import APPROVAL_QUEUE
            proposals = APPROVAL_QUEUE.get_all_proposals()
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
        self.logger.info("Server started in background thread")
        return thread


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 5555,
    debug: bool = False
) -> SimpHttpServer:
    """Factory function to create HTTP server"""
    config = BrokerConfig(host=host, port=port)
    return SimpHttpServer(config, debug=debug)
