#!/usr/bin/env python3
"""
projectx_quantum_advisor.py  —  Phase 8: ProjectX Quantum Entrainment

Runs alongside projectx_native (:8771).
Subscribes to the projectx maintenance channel on the mesh.
For every maintenance task ProjectX is about to run, this advisor:
  1. Sends task description to quantum_intelligence_prime
  2. Gets quantum-enhanced analysis (pattern matching, optimization, risk)
  3. Writes quantum recommendations to ProjectX's task context
  4. ProjectX incorporates recommendations before executing

Quantum capabilities mapped to ProjectX operations:
  native_agent_repo_scan     → Grover's algorithm pattern search
  native_agent_task_audit    → QAOA task scheduling optimization
  native_agent_security_audit → Quantum random oracle testing
  native_agent_code_maintenance → QIP suggests quantum-native patterns
  projectx_query             → Full quantum knowledge retrieval

DROP INTO:  simp root
RUN:        python3.10 projectx_quantum_advisor.py &

Then ProjectX gains quantum analysis on every maintenance decision.
"""

import sys
import os
import json
import time
import uuid
import logging
import signal
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [projectx_quantum] %(levelname)s %(message)s"
)
logger = logging.getLogger("projectx_quantum_advisor")

# ─── Config ───────────────────────────────────────────────────────────────────

BROKER_URL          = "http://127.0.0.1:5555"
ADVISOR_AGENT_ID    = "projectx_quantum_advisor"
QIP_AGENT_ID        = "quantum_intelligence_prime"
PROJECTX_AGENT_ID   = "projectx_native"
PROJECTX_URL        = "http://127.0.0.1:8771"

POLL_INTERVAL       = 3         # seconds
HEARTBEAT_INTERVAL  = 30
QIP_TIMEOUT         = 30        # seconds to wait for QIP

# ProjectX inbox for quantum recommendations
PROJECTX_QUANTUM_INBOX = Path("data/inboxes/projectx_quantum")

# Capability → quantum analysis type mapping
CAPABILITY_QUANTUM_MAP = {
    "native_agent_repo_scan": {
        "intent": "solve_quantum_problem",
        "template": (
            "Use Grover's search algorithm to find patterns in a Python codebase. "
            "Task: {task_detail}. "
            "Identify: missing registrations, broken imports, unimplemented interfaces. "
            "Return: list of files and patterns to check first (highest probability hits)."
        ),
        "benefit": "Quantum search provides sqrt(N) speedup over classical grep for pattern matching"
    },
    "native_agent_task_audit": {
        "intent": "optimize_portfolio",
        "template": (
            "Use QAOA to optimize task scheduling for SIMP broker. "
            "Current state: {task_detail}. "
            "Objective: minimize total pending intent queue depth (currently 19 pending). "
            "Constraints: BRP mode ENFORCED, dry_run_safe=true. "
            "Return: optimal task execution order and resource allocation."
        ),
        "benefit": "QAOA optimization reduces pending intent backlog faster than greedy scheduling"
    },
    "native_agent_security_audit": {
        "intent": "solve_quantum_problem",
        "template": (
            "Apply quantum random oracle testing to a Python security audit. "
            "Task: {task_detail}. "
            "Check: hardcoded credentials, exposed API keys, insecure transport, "
            "missing auth headers, SQL injection vectors, path traversal. "
            "Use quantum-enhanced pattern detection for obfuscated credential patterns. "
            "Return: prioritized findings with remediation steps."
        ),
        "benefit": "Quantum random oracle explores more attack vectors than classical fuzzing"
    },
    "native_agent_code_maintenance": {
        "intent": "solve_quantum_problem",
        "template": (
            "Analyze Python code for quantum-native refactoring opportunities. "
            "Task: {task_detail}. "
            "Identify: loops that could use quantum speedup, data structures that benefit "
            "from quantum memory, classical ML that could be replaced with quantum ML. "
            "Also: standard code quality issues (N+1, missing error handling, type hints). "
            "Return: prioritized refactoring recommendations with expected impact."
        ),
        "benefit": "QIP identifies quantum-native opportunities alongside classical improvements"
    },
    "native_agent_health_check": {
        "intent": "get_deployment_status",
        "template": "Health check context for quantum deployment validation: {task_detail}",
        "benefit": "QIP validates quantum components are healthy before maintenance proceeds"
    },
    "native_agent_provider_repair": {
        "intent": "solve_quantum_problem",
        "template": (
            "Quantum-assisted provider connection repair. "
            "Provider context: {task_detail}. "
            "Apply quantum amplitude amplification to search the connection parameter space "
            "for valid configurations. Return optimal reconnection strategy."
        ),
        "benefit": "Quantum search finds valid connection parameters faster"
    },
    "projectx_query": {
        "intent": "solve_quantum_problem",
        "template": "Answer this SIMP system query using quantum knowledge retrieval: {task_detail}",
        "benefit": "QIP quantum retrieval returns higher-confidence answers"
    },
}


# ─── Broker helpers ───────────────────────────────────────────────────────────

def _post(url, payload, timeout=10):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"POST {url}: {e}")
        return None


def _get(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"GET {url}: {e}")
        return None


def _poll_messages(broker: str, agent_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
    """Poll mesh messages for an agent."""
    result = _get(
        f"{broker}/mesh/poll",
        params={"agent_id": agent_id, "max_messages": max_messages},
    )
    if not result or result.get("status") != "success":
        return []
    return result.get("messages", [])


# ─── Setup ────────────────────────────────────────────────────────────────────

def setup(broker: str):
    PROJECTX_QUANTUM_INBOX.mkdir(parents=True, exist_ok=True)

    _post(f"{broker}/agents/register", {
        "agent_id": ADVISOR_AGENT_ID,
        "agent_type": "quantum_advisor",
        "endpoint": "",
        "simp_versions": ["1.0"],
        "capabilities": [
            "quantum_task_advisory",
            "maintenance_pre_flight",
            "quantum_code_analysis",
            "quantum_security_review",
        ],
        "metadata": {
            "mesh_native": True,
            "advises": PROJECTX_AGENT_ID,
            "qip_powered": True,
        }
    })
    logger.info(f"Registered as {ADVISOR_AGENT_ID}")

    for ch in ["projectx_tasks", "maintenance_requests", "quantum_advisory"]:
        _post(f"{broker}/mesh/subscribe", {"agent_id": ADVISOR_AGENT_ID, "channel": ch})
        logger.info(f"Subscribed to '{ch}'")

    # Also subscribe the advisor to ProjectX's output channel so we can intercept
    _post(f"{broker}/mesh/subscribe", {"agent_id": ADVISOR_AGENT_ID, "channel": "system_health"})


def heartbeat(broker: str):
    _post(f"{broker}/agents/heartbeat", {
        "agent_id": ADVISOR_AGENT_ID,
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ─── QIP consultation ─────────────────────────────────────────────────────────

def consult_qip(broker: str, capability: str, task_detail: str) -> Dict[str, Any]:
    """
    Consult QIP for pre-flight analysis on a ProjectX task.
    Returns quantum recommendation dict.
    """
    mapping = CAPABILITY_QUANTUM_MAP.get(capability, CAPABILITY_QUANTUM_MAP["projectx_query"])
    intent = mapping["intent"]
    problem = mapping["template"].format(task_detail=task_detail)

    send_r = _post(f"{broker}/mesh/send", {
        "sender_id": ADVISOR_AGENT_ID,
        "recipient_id": QIP_AGENT_ID,
        "channel": "quantum",
        "payload": {
            "intent": intent,
            "problem": problem,
            "context": {
                "requesting_agent": PROJECTX_AGENT_ID,
                "capability": capability,
                "advisor": ADVISOR_AGENT_ID,
            }
        }
    })

    if not send_r or send_r.get("status") != "success":
        return {"success": False, "error": "QIP dispatch failed"}

    sent_id = send_r.get("message_id", "")
    deadline = time.time() + QIP_TIMEOUT

    while time.time() < deadline:
        for msg in _poll_messages(broker, ADVISOR_AGENT_ID):
            p = msg.get("payload", {})
            if (
                msg.get("sender_id") == QIP_AGENT_ID
                or p.get("source") == "quantum_intelligence_prime"
                or p.get("responding_to") == sent_id
            ):
                return {
                    "success": p.get("success", False),
                    "capability": capability,
                    "quantum_benefit": mapping["benefit"],
                    "intent_used": intent,
                    "result": p.get("result", ""),
                    "metadata": p.get("metadata", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        time.sleep(2)

    return {
        "success": False,
        "capability": capability,
        "error": "QIP timeout",
        "fallback": "Proceed with classical analysis only"
    }


# ─── Recommendation delivery ──────────────────────────────────────────────────

def deliver_recommendation(capability: str, task_id: str,
                           recommendation: Dict[str, Any], broker: str):
    """Write quantum recommendation to ProjectX inbox and mesh."""
    rec_doc = {
        "recommendation_id": str(uuid.uuid4()),
        "for_capability": capability,
        "for_task_id": task_id,
        "from": ADVISOR_AGENT_ID,
        "qip_powered": True,
        "recommendation": recommendation,
        "apply_before_execution": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # File delivery
    fname = PROJECTX_QUANTUM_INBOX / f"rec_{capability}_{int(time.time())}.json"
    try:
        fname.write_text(json.dumps(rec_doc, indent=2))
        logger.info(f"Recommendation written: {fname.name}")
    except Exception as e:
        logger.error(f"File write failed: {e}")

    # Mesh delivery to ProjectX
    _post(f"{broker}/mesh/send", {
        "sender_id": ADVISOR_AGENT_ID,
        "recipient_id": PROJECTX_AGENT_ID,
        "channel": "maintenance_requests",
        "payload": {
            "intent": "quantum_pre_flight_result",
            "task_id": task_id,
            "recommendation": rec_doc,
        }
    })


# ─── Proactive scanning ───────────────────────────────────────────────────────

def run_proactive_scan(broker: str):
    """
    Proactive: don't wait for ProjectX to ask.
    Periodically ask QIP to scan the SIMP system state and generate
    maintenance recommendations for ProjectX to execute.
    """
    system_state = _get(f"{broker}/status") or {}
    agents_response = _get(f"{broker}/agents") or {}
    agents = agents_response.get("agents", [])

    # Identify stale/degraded agents
    stale_agents = []
    for a in agents:
        if isinstance(a, dict):
            agent_id = a.get("agent_id")
            if a.get("stale") or a.get("status") not in ("online", "active"):
                stale_agents.append(agent_id)

    pending_intents = (system_state.get("broker", {})
                       .get("stats", {}).get("pending_intents", 0))

    problem = (
        f"SIMP system maintenance scan. "
        f"Broker stats: {pending_intents} pending intents. "
        f"Stale/degraded agents: {stale_agents}. "
        f"Registered agents: {[a.get('agent_id') for a in agents if isinstance(a, dict) and a.get('agent_id')]}. "
        f"Using quantum pattern detection: identify the top 3 maintenance actions "
        f"ProjectX should execute to restore full system health. "
        f"Return prioritized action list with expected impact."
    )

    send_r = _post(f"{broker}/mesh/send", {
        "sender_id": ADVISOR_AGENT_ID,
        "recipient_id": QIP_AGENT_ID,
        "channel": "quantum",
        "payload": {
            "intent": "solve_quantum_problem",
            "problem": problem,
            "context": {"scan_type": "proactive_maintenance"},
        }
    })

    if send_r and send_r.get("status") == "success":
        logger.info("Proactive scan dispatched to QIP")


# ─── Main loop ────────────────────────────────────────────────────────────────

class ProjectXQuantumAdvisor:
    def __init__(self, broker: str = BROKER_URL):
        self.broker = broker
        self._running = False
        self._advice_count = 0
        self._last_proactive = 0.0
        self.PROACTIVE_INTERVAL = 300   # scan every 5 minutes

    def start(self):
        logger.info(f"ProjectX Quantum Advisor starting — broker={self.broker}")
        setup(self.broker)
        self._running = True
        last_heartbeat = 0.0

        logger.info("Advisor active. Intercepting ProjectX tasks for quantum pre-flight...")

        while self._running:
            now = time.time()

            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                heartbeat(self.broker)
                last_heartbeat = now

            # Proactive system scan
            if now - self._last_proactive >= self.PROACTIVE_INTERVAL:
                run_proactive_scan(self.broker)
                self._last_proactive = now

            # Poll for ProjectX task requests
            for msg in _poll_messages(self.broker, ADVISOR_AGENT_ID):
                payload = msg.get("payload", {})
                sender = msg.get("sender_id", "")
                channel = msg.get("channel", "")

                if channel not in {"projectx_tasks", "maintenance_requests", "system_health"}:
                    continue

                # Only act on ProjectX messages
                if sender != PROJECTX_AGENT_ID and payload.get("agent") != PROJECTX_AGENT_ID:
                    continue

                capability = payload.get("capability", payload.get("intent", "projectx_query"))
                task_detail = payload.get("task", payload.get("description", str(payload)))
                task_id = payload.get("task_id", str(uuid.uuid4())[:8])

                logger.info(f"ProjectX task intercepted: capability={capability!r}")

                rec = consult_qip(self.broker, capability, task_detail)
                deliver_recommendation(capability, task_id, rec, self.broker)
                self._advice_count += 1
                logger.info(
                    f"Advice #{self._advice_count} delivered for '{capability}' "
                    f"(qip_success={rec.get('success')})"
                )

            time.sleep(POLL_INTERVAL)

    def stop(self):
        self._running = False
        logger.info(f"ProjectX Quantum Advisor stopped. Total advice given: {self._advice_count}")


def main():
    parser = argparse.ArgumentParser(
        description="ProjectX Quantum Advisor — QIP-powered maintenance pre-flight"
    )
    parser.add_argument("--broker", default=BROKER_URL)
    parser.add_argument("--test-capability", metavar="CAPABILITY",
                        help="Test quantum analysis for a specific capability")
    parser.add_argument("--task-detail", default="general system maintenance",
                        help="Task detail for test")
    parser.add_argument("--proactive-scan", action="store_true",
                        help="Run one proactive system scan and exit")
    args = parser.parse_args()

    if args.test_capability:
        setup(args.broker)
        result = consult_qip(args.broker, args.test_capability, args.task_detail)
        print(json.dumps(result, indent=2))
        return

    if args.proactive_scan:
        setup(args.broker)
        run_proactive_scan(args.broker)
        # Wait briefly for response
        time.sleep(10)
        print(json.dumps({"messages": _poll_messages(args.broker, ADVISOR_AGENT_ID)}, indent=2))
        return

    advisor = ProjectXQuantumAdvisor(broker=args.broker)

    def _shutdown(sig, frame):
        advisor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    advisor.start()


if __name__ == "__main__":
    main()
