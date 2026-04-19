
#!/usr/bin/env python3
"""
quantum_mesh_consumer.py — Active mesh listener for quantum_intelligence_prime
 
Subscribes to the mesh, polls for incoming quantum intents,
routes them through quantum_mode_engine.py, sends responses back.
 
Usage:
    python3.10 quantum_mesh_consumer.py
    python3.10 quantum_mesh_consumer.py --broker http://127.0.0.1:5555 --interval 2
"""
 
import sys
import os
import time
import json
import logging
import argparse
import signal
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any
 
import requests
 
# Allow running from simp root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s %(message)s'
)
logger = logging.getLogger("quantum_mesh_consumer")
 
# ─── Config ──────────────────────────────────────────────────────────────────
 
AGENT_ID      = "quantum_intelligence_prime"
AGENT_TYPE    = "quantum"
BROKER_URL    = "http://127.0.0.1:5555"
POLL_INTERVAL = 2.0      # seconds between polls
HEARTBEAT_INTERVAL = 30  # seconds between heartbeats
SUBSCRIBE_CHANNELS = ["quantum", "intent_requests"]
CAPABILITIES = [
    "health_check",
    "get_deployment_status",
    "solve_quantum_problem",
    "optimize_portfolio",
    "evolve_quantum_skills",
]
 
# ─── Engine bootstrap ─────────────────────────────────────────────────────────
 
def _load_engine():
    """Try to load the QuantumModeEngine. Returns None on failure (runs stub mode)."""
    try:
        from quantum_mode_engine import QuantumModeEngine
        engine = QuantumModeEngine(
            config_path=Path("quantum_mode_config.json"),
            dataset_dir="data/quantum_dataset",
            enable_learning=True,
            enable_risk_scoring=True,
        )
        logger.info("QuantumModeEngine loaded ✅")
        return engine
    except Exception as exc:
        logger.warning(f"QuantumModeEngine unavailable ({exc}) — running in stub mode")
        return None
 
 
def _load_integration():
    """Try to load StrayGooseQuantumIntegration."""
    try:
        from stray_goose_quantum_integration import StrayGooseQuantumIntegration
        integration = StrayGooseQuantumIntegration()
        logger.info("StrayGooseQuantumIntegration loaded ✅")
        return integration
    except Exception as exc:
        logger.warning(f"StrayGooseQuantumIntegration unavailable ({exc})")
        return None
 
# ─── Broker helpers ───────────────────────────────────────────────────────────
 
def _post(url: str, payload: dict, timeout: int = 10) -> Optional[dict]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.error(f"POST {url} failed: {exc}")
        return None
 
 
def _get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.error(f"GET {url} failed: {exc}")
        return None
 
 
def register(broker: str) -> bool:
    """Register with broker /agents endpoint."""
    result = _post(f"{broker}/agents/register", {
        "agent_id": AGENT_ID,
        "agent_type": AGENT_TYPE,
        "endpoint": "",          # mesh-native, no HTTP endpoint
        "capabilities": CAPABILITIES,
        "metadata": {
            "mesh_native": True,
            "transport": "mesh",
            "version": "1.0.0",
            "capabilities": CAPABILITIES,
        }
    })
    if result and result.get("status") == "success":
        logger.info(f"Registered with broker as {AGENT_ID} ✅")
        return True
    logger.warning(f"Registration response: {result}")
    return False
 
 
def subscribe(broker: str) -> bool:
    """Subscribe to all quantum channels."""
    ok = True
    for channel in SUBSCRIBE_CHANNELS:
        result = _post(f"{broker}/mesh/subscribe", {
            "agent_id": AGENT_ID,
            "channel": channel,
        })
        if result and result.get("status") == "success":
            logger.info(f"Subscribed to channel '{channel}' ✅")
        else:
            logger.warning(f"Subscribe to '{channel}' failed: {result}")
            ok = False
    return ok
 
 
def heartbeat(broker: str):
    """Send heartbeat to broker."""
    _post(f"{broker}/agents/heartbeat", {
        "agent_id": AGENT_ID,
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
 
 
def poll_messages(broker: str, channel: str) -> list:
    """Poll for messages on a channel. Returns list of message dicts."""
    result = _get(f"{broker}/mesh/poll", params={
        "agent_id": AGENT_ID,
        "channel": channel,
        "max_messages": 10,
    })
    if result and result.get("status") == "success":
        return result.get("messages", [])
    return []
 
 
def send_response(broker: str, recipient_id: str, channel: str, payload: dict):
    """Send a response message back into the mesh."""
    _post(f"{broker}/mesh/send", {
        "sender_id": AGENT_ID,
        "recipient_id": recipient_id,
        "channel": channel,
        "payload": payload,
    })
 
# ─── Intent processing ────────────────────────────────────────────────────────
 
def _stub_response(intent: str, problem: str) -> dict:
    """Fallback when quantum engine is unavailable."""
    return {
        "success": True,
        "source": "quantum_stub",
        "intent": intent,
        "result": f"[STUB] Quantum engine offline. Would process: {problem}",
        "note": "Install qiskit + set SIMP_USE_REAL_HARDWARE=1 for live execution",
    }
 
 
def process_intent(
    msg: dict,
    engine,
    integration,
    broker: str,
) -> None:
    """Process a single mesh message as a quantum intent."""
    payload    = msg.get("payload", {})
    sender_id  = msg.get("sender_id", "unknown")
    channel    = msg.get("channel", "quantum")
    msg_id     = msg.get("message_id", "?")
 
    intent  = payload.get("intent", "solve_quantum_problem")
    problem = payload.get("problem", payload.get("query", str(payload)))
 
    logger.info(f"[{msg_id[:8]}] intent={intent!r} from={sender_id}")
 
    # ── Route by intent type ──────────────────────────────────────────────
    try:
        if intent == "health_check":
            response = {
                "success": True,
                "agent_id": AGENT_ID,
                "status": "online",
                "engine_available": engine is not None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
 
        elif intent in ("solve_quantum_problem", "optimize_portfolio", "evolve_quantum_skills"):
            if integration:
                result = integration.process_query(problem, force_quantum=True)
                response = {
                    "success": result.get("success", False),
                    "intent": intent,
                    "result": result.get("result", ""),
                    "metadata": result.get("metadata", {}),
                    "source": "quantum_intelligence_prime",
                }
            elif engine:
                result = engine.process_query(problem)
                response = {
                    "success": result.get("success", False),
                    "intent": intent,
                    "result": result,
                    "source": "quantum_intelligence_prime",
                }
            else:
                response = _stub_response(intent, problem)
 
        elif intent == "get_deployment_status":
            response = {
                "success": True,
                "agent_id": AGENT_ID,
                "engine_mode": "simulator" if not os.environ.get("SIMP_USE_REAL_HARDWARE") else "real_hardware",
                "engine_available": engine is not None,
                "integration_available": integration is not None,
                "subscribed_channels": SUBSCRIBE_CHANNELS,
                "capabilities": CAPABILITIES,
            }
 
        else:
            logger.warning(f"Unknown intent {intent!r} — passing to integration")
            if integration:
                result = integration.process_query(f"{intent}: {problem}")
                response = {"success": True, "intent": intent, "result": result}
            else:
                response = _stub_response(intent, problem)
 
    except Exception as exc:
        logger.error(f"Error processing intent {intent!r}: {exc}", exc_info=True)
        response = {
            "success": False,
            "intent": intent,
            "error": str(exc),
            "source": "quantum_intelligence_prime",
        }
 
    # ── Send response back ────────────────────────────────────────────────
    response["responding_to"] = msg_id
    response["timestamp"] = datetime.now(timezone.utc).isoformat()
    send_response(broker, sender_id, channel, response)
    logger.info(f"[{msg_id[:8]}] → response sent to {sender_id} (success={response.get('success')})")
 
# ─── Main loop ────────────────────────────────────────────────────────────────
 
class QuantumMeshConsumer:
    def __init__(self, broker: str = BROKER_URL, poll_interval: float = POLL_INTERVAL):
        self.broker = broker
        self.poll_interval = poll_interval
        self._running = False
        self._engine = None
        self._integration = None
 
    def start(self):
        logger.info(f"Quantum mesh consumer starting — broker={self.broker}")
        self._engine = _load_engine()
        self._integration = _load_integration()
 
        register(self.broker)
        subscribe(self.broker)
 
        self._running = True
        last_heartbeat = 0.0
 
        logger.info("Polling mesh for quantum intents... (Ctrl+C to stop)")
 
        while self._running:
            now = time.time()
 
            # Heartbeat
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                heartbeat(self.broker)
                last_heartbeat = now
 
            # Poll all subscribed channels
            for channel in SUBSCRIBE_CHANNELS:
                messages = poll_messages(self.broker, channel)
                for msg in messages:
                    process_intent(msg, self._engine, self._integration, self.broker)
 
            time.sleep(self.poll_interval)
 
    def stop(self):
        self._running = False
        logger.info("Quantum mesh consumer stopped.")
 
 
def main():
    parser = argparse.ArgumentParser(description="Quantum Intelligence Prime — mesh consumer")
    parser.add_argument("--broker", default=BROKER_URL)
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL)
    args = parser.parse_args()
 
    consumer = QuantumMeshConsumer(broker=args.broker, poll_interval=args.interval)
 
    def _shutdown(sig, frame):
        logger.info("Shutdown signal received")
        consumer.stop()
        sys.exit(0)
 
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
 
    consumer.start()
 
 
if __name__ == "__main__":
    main()
 


