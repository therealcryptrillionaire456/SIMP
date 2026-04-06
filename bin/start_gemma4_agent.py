#!/usr/bin/env python3
"""Start the Gemma4 SIMP agent.

Starts an HTTP server wrapping the Gemma4 agent, registers with the broker,
and listens for intents.

Usage:
    python3.10 bin/start_gemma4_agent.py [--port 5010] [--broker http://localhost:5555]

Environment variables:
    GEMMA4_MODEL_ENDPOINT  — Local model API (default: http://localhost:11434)
    GEMMA4_MODEL_NAME      — Model name (default: gemma4:e2b)
    GEMMA4_API_FORMAT      — API format: ollama or openai (default: ollama)
    SIMP_BROKER_URL        — Broker HTTP URL (default: http://127.0.0.1:8080)
    SIMP_API_KEY           — API key for broker auth (optional)
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.agents.gemma4_agent import Gemma4Agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("gemma4_simp")


class AgentHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for SIMP agent protocol."""

    agent = None  # Set by server setup

    def do_GET(self):
        if self.path == "/health":
            health = self.agent.health()
            self._respond(200, health)
        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/intents/handle":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                intent_data = json.loads(body)
                response = self.agent.handle_intent(intent_data)
                self._respond(200, response)
            except json.JSONDecodeError:
                self._respond(400, {"error": "Invalid JSON"})
            except Exception as exc:
                self._respond(500, {"error": str(exc)})
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        logger.info(f"HTTP: {format % args}")


def register_with_broker(broker_url, agent_id, agent_port, api_key=None):
    """Register this agent with the SIMP broker."""
    import httpx
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.post(
            f"{broker_url}/agents/register",
            json={
                "agent_id": agent_id,
                "agent_type": "llm",
                "endpoint": f"http://127.0.0.1:{agent_port}",
                "metadata": {
                    "model": os.environ.get("GEMMA4_MODEL_NAME", "gemma4:e2b"),
                    "capabilities": Gemma4Agent.SUPPORTED_INTENTS,
                },
            },
            headers=headers,
            timeout=10.0,
        )
        if 200 <= resp.status_code < 300:
            logger.info(f"Registered with broker at {broker_url}")
        else:
            logger.warning(f"Registration returned {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.warning(f"Could not register with broker: {exc}")
        logger.info("Agent will run standalone — register manually or wait for broker")


def main():
    parser = argparse.ArgumentParser(description="Gemma4 SIMP Agent")
    parser.add_argument("--port", type=int, default=int(os.environ.get("GEMMA4_AGENT_PORT", 5010)))
    parser.add_argument("--broker", default=os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--agent-id", default="gemma4_local")
    parser.add_argument("--no-register", action="store_true", help="Skip broker registration")
    args = parser.parse_args()

    # Create agent
    agent = Gemma4Agent(
        agent_id=args.agent_id,
        model_endpoint=os.environ.get("GEMMA4_MODEL_ENDPOINT", "http://localhost:11434"),
        model_name=os.environ.get("GEMMA4_MODEL_NAME", "gemma4:e2b"),
        api_format=os.environ.get("GEMMA4_API_FORMAT", "ollama"),
    )

    # Set agent on handler class
    AgentHTTPHandler.agent = agent

    # Start HTTP server
    server = ThreadingHTTPServer(("127.0.0.1", args.port), AgentHTTPHandler)
    logger.info(f"Gemma4 agent starting on port {args.port}")

    # Register with broker
    if not args.no_register:
        api_key = os.environ.get("SIMP_API_KEY", "")
        register_with_broker(args.broker, args.agent_id, args.port, api_key)

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        agent.close()
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
