"""
SIMP Agent Server

HTTP server wrapper for SIMP agents that receive intents from the broker.
Provides /health and /intents/handle endpoints.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from flask import Flask, request, jsonify


class SimpAgentServer:
    """HTTP server wrapper for SIMP agents that receive intents."""

    def __init__(
        self,
        agent,
        host: str = "127.0.0.1",
        port: int = 8000,
    ):
        self.agent = agent
        self.host = host
        self.port = port
        self.app = Flask(f"SIMP-Agent-{agent.agent_id}")
        self.logger = logging.getLogger(f"SIMP.AgentServer.{agent.agent_id}")
        self.logger.setLevel(logging.INFO)

        self.intents_handled = 0
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "status": "ok",
                "agent_id": self.agent.agent_id,
                "intents_handled": self.intents_handled,
            })

        @self.app.route("/intents/handle", methods=["POST"])
        def handle_intent():
            """Receive and process an intent from the broker."""
            intent_data = request.get_json()
            if not intent_data:
                return jsonify({
                    "status": "error",
                    "error_code": "INVALID_PAYLOAD",
                    "error_message": "Request body must be JSON",
                }), 400

            intent_type = intent_data.get("intent_type")
            params = intent_data.get("params", {})

            if not intent_type:
                return jsonify({
                    "status": "error",
                    "error_code": "MISSING_INTENT_TYPE",
                    "error_message": "intent_type is required",
                }), 400

            # Look up handler on the agent
            handler_name = f"handle_{intent_type}"
            handler = self.agent.intent_handlers.get(intent_type)

            if handler is None and hasattr(self.agent, handler_name):
                handler = getattr(self.agent, handler_name)

            if handler is None:
                return jsonify({
                    "status": "error",
                    "error_code": "HANDLER_NOT_FOUND",
                    "error_message": f"No handler for intent type: {intent_type}",
                }), 404

            try:
                if asyncio.iscoroutinefunction(handler):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(handler(params))
                    finally:
                        loop.close()
                else:
                    result = handler(params)

                self.intents_handled += 1
                return jsonify(result)

            except Exception as exc:
                self.logger.error(f"Handler error: {exc}")
                return jsonify({
                    "status": "error",
                    "error_code": "HANDLER_ERROR",
                    "error_message": str(exc),
                }), 500

    def run(self, threaded: bool = True):
        """Run the agent server."""
        self.logger.info(
            f"SIMP Agent Server starting: {self.agent.agent_id} "
            f"on {self.host}:{self.port}"
        )
        self.app.run(host=self.host, port=self.port, threaded=threaded)
