#!/usr/bin/env python3
"""
Test Agent 1 for SIMP Broker Stress Testing
A simple agent that responds to ping and echo intents for stress testing.
"""

import json
import logging
import signal
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
import uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("test_agent_1")

class TestAgent1:
    """Test Agent 1 for stress testing."""
    
    def __init__(self, agent_id: str = "test_agent_1"):
        self.agent_id = agent_id
        self.supported_intents = ["test", "echo", "health", "stress_test", "planning", "research"]
        self.request_count = 0
        self.start_time = time.time()
        
    def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming intents."""
        self.request_count += 1
        intent_type = intent_data.get("intent_type", "")
        params = intent_data.get("params", {})
        
        # Simulate some processing time (0-100ms)
        processing_time = min(self.request_count % 100, 50) / 1000.0
        time.sleep(processing_time)
        
        logger.debug(f"Handling intent #{self.request_count}: {intent_type}")
        
        if intent_type == "ping":
            return {
                "status": "success",
                "message": f"Pong from {self.agent_id}!",
                "timestamp": time.time(),
                "agent_id": self.agent_id,
                "request_number": self.request_count
            }
        elif intent_type == "echo":
            message = params.get("message", "")
            return {
                "status": "success",
                "echo": message,
                "timestamp": time.time(),
                "agent_id": self.agent_id,
                "request_number": self.request_count
            }
        elif intent_type == "stress_test":
            # Handle stress test with configurable delay
            delay = params.get("delay_ms", 0) / 1000.0
            if delay > 0:
                time.sleep(delay)
            
            workload = params.get("workload", "light")
            if workload == "heavy":
                # Simulate heavy computation
                _ = [i**2 for i in range(10000)]
            
            return {
                "status": "success",
                "message": f"Stress test completed by {self.agent_id}",
                "workload": workload,
                "delay_ms": delay * 1000,
                "timestamp": time.time(),
                "agent_id": self.agent_id,
                "request_number": self.request_count
            }
        elif intent_type == "health":
            uptime = time.time() - self.start_time
            return {
                "status": "healthy",
                "agent_id": self.agent_id,
                "supported_intents": self.supported_intents,
                "request_count": self.request_count,
                "uptime_seconds": uptime,
                "timestamp": time.time()
            }
        else:
            return {
                "status": "error",
                "message": f"Unsupported intent type: {intent_type}",
                "supported_intents": self.supported_intents,
                "timestamp": time.time()
            }
    
    def health(self) -> Dict[str, Any]:
        """Return health status."""
        uptime = time.time() - self.start_time
        return {
            "status": "healthy",
            "agent_id": self.agent_id,
            "supported_intents": self.supported_intents,
            "request_count": self.request_count,
            "uptime_seconds": uptime,
            "timestamp": time.time()
        }


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
        if self.path in {"/intents/handle", "/intents/receive", "/intent"}:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                intent_data = json.loads(body)
                response = self.agent.handle_intent(intent_data)
                self._respond(200, response)
            except json.JSONDecodeError:
                self._respond(400, {"error": "Invalid JSON"})
            except Exception as exc:
                logger.error(f"Error handling intent: {exc}")
                self._respond(500, {"error": str(exc)})
        else:
            self._respond(404, {"error": "Not found"})
    
    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to reduce log noise."""
        logger.debug(f"{self.address_string()} - {format % args}")


def register_with_broker(broker_url: str, agent_id: str, port: int, api_key: str = None) -> bool:
    """Register this agent with the SIMP broker."""
    import httpx
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    registration_data = {
        "agent_id": agent_id,
        "endpoint": f"http://127.0.0.1:{port}",
        "agent_type": "test_agent",
        "metadata": {
            "name": agent_id,
            "description": "Test agent for SIMP broker stress testing",
            "version": "1.0.0",
            "capabilities": ["ping", "echo", "health", "stress_test"],
            "dry_run_safe": True
        },
        "simp_versions": ["1.0"]
    }
    
    try:
        resp = httpx.post(
            f"{broker_url.rstrip('/')}/agents/register",
            json=registration_data,
            headers=headers,
            timeout=10.0
        )
        if 200 <= resp.status_code < 300:
            logger.info(f"✅ Registered with broker at {broker_url}")
            return True
        else:
            logger.warning(f"⚠️ Registration returned {resp.status_code}: {resp.text}")
            return False
    except Exception as exc:
        logger.warning(f"⚠️ Could not register with broker: {exc}")
        return False


def send_heartbeat(broker_url: str, agent_id: str, api_key: str = None):
    """Send heartbeat to broker."""
    import httpx
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        resp = httpx.post(
            f"{broker_url.rstrip('/')}/agents/{agent_id}/heartbeat",
            headers=headers,
            timeout=5.0
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning(f"Heartbeat failed: {exc}")
        return False


def start_heartbeat_loop(broker_url: str, agent_id: str, api_key: str, stop_event: threading.Event, interval_s: int = 30):
    """Send broker heartbeats on a background thread."""
    
    def _loop():
        while not stop_event.is_set():
            send_heartbeat(broker_url, agent_id, api_key)
            stop_event.wait(interval_s)
    
    thread = threading.Thread(target=_loop, daemon=True, name=f"{agent_id}-heartbeat")
    thread.start()
    return thread


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Agent 1 for SIMP broker stress testing")
    parser.add_argument("--port", type=int, default=8889, help="Port to run agent on")
    parser.add_argument("--broker", default="http://127.0.0.1:5555", help="Broker URL")
    parser.add_argument("--agent-id", default="test_agent_1", help="Agent ID")
    parser.add_argument("--no-register", action="store_true", help="Skip broker registration")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create agent
    agent = TestAgent1(agent_id=args.agent_id)
    AgentHTTPHandler.agent = agent
    
    # Start HTTP server
    server = ThreadingHTTPServer(("127.0.0.1", args.port), AgentHTTPHandler)
    logger.info(f"🚀 Test Agent 1 starting on port {args.port} (agent_id: {args.agent_id})")
    
    # Register with broker
    stop_event = threading.Event()
    heartbeat_thread = None
    
    if not args.no_register:
        api_key = None  # No API key needed for now
        if register_with_broker(args.broker, args.agent_id, args.port, api_key):
            heartbeat_thread = start_heartbeat_loop(args.broker, args.agent_id, api_key, stop_event)
        else:
            logger.warning("Failed to register with broker, running in standalone mode")
    
    # Graceful shutdown
    def shutdown(signum=None, frame=None):
        logger.info("Shutting down Test Agent 1...")
        stop_event.set()
        server.shutdown()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=2)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()