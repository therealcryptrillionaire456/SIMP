#!/usr/bin/env python3
"""
goose_quantum_orchestrator.py  —  Phase 7: Stray Goose Full Quantum Integration

Gives Stray Goose the ability to:
  1. Detect whether a task benefits from quantum acceleration
  2. Dispatch intents to quantum_intelligence_prime via mesh
  3. Receive quantum results and inject them into Goose's working context
  4. Create SIMP work packets from quantum outputs
  5. Route completed quantum work back through the broker

Stray Goose usage:
    from goose_quantum_orchestrator import GooseQuantumOrchestrator
    qo = GooseQuantumOrchestrator()
    result = qo.run("optimize my portfolio for today's trading session")

CLI usage:
    python3.10 goose_quantum_orchestrator.py "query here"
    python3.10 goose_quantum_orchestrator.py --task optimize_portfolio --assets BTC ETH SOL
    python3.10 goose_quantum_orchestrator.py --dispatch-intent solve_quantum_problem --problem "..."
    python3.10 goose_quantum_orchestrator.py --status

Goose profile integration:
    Add to your Goose session's system prompt the contents of GOOSE_SYSTEM_CONTEXT below.
    Then call this script as a tool from within your Goose session.
"""

import sys
import os
import json
import time
import uuid
import logging
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [goose_quantum] %(levelname)s %(message)s"
)
logger = logging.getLogger("goose_quantum_orchestrator")

# ─── Goose system context (paste into Goose session prompt) ──────────────────

GOOSE_SYSTEM_CONTEXT = """
## SIMP Quantum Mesh — Goose Integration

You are operating within the SIMP multi-agent trading mesh. You have quantum
computing capability via quantum_intelligence_prime (QIP).

### When to use quantum acceleration:
- Portfolio allocation / position sizing across BTC, ETH, SOL
- Pattern detection in market data (quantum search speedup)
- Risk estimation (quantum Monte Carlo)
- Strategy optimization (QAOA)
- Arbitrage detection (quantum amplitude estimation)

### How to invoke quantum tools:
```python
from goose_quantum_orchestrator import GooseQuantumOrchestrator
qo = GooseQuantumOrchestrator()

# Optimize portfolio
result = qo.optimize_portfolio(assets=["BTC-USD", "ETH-USD", "SOL-USD"])

# Solve quantum problem
result = qo.solve("problem description here")

# Dispatch any intent
result = qo.dispatch("evolve_quantum_skills", {"skill": "arbitrage_detection"})

# Get QIP status
status = qo.qip_status()
```

### Broker endpoints (all live at http://127.0.0.1:5555):
- GET  /health          — broker health
- GET  /agents          — all 12 registered agents
- GET  /mesh/routing/agents — 4 active mesh agents
- POST /mesh/send       — send intent via mesh
- GET  /mesh/poll       — receive responses
- GET  /mesh/routing/status — mesh mode (currently: preferred)

### Active mesh agents with capabilities:
- quantum_intelligence_prime: solve_quantum_problem, optimize_portfolio, evolve_quantum_skills
- quantumarb_primary: arbitrage detection, market analysis
- projectx_native: repo_scan, code_maintenance, security_audit
- ktc_agent: receipt_processing, crypto_investment, wallet_management

### Revenue pipeline:
gate4_real (Coinbase, $1-$10 live) ← quantum_signal_bridge ← QIP
quantumarb_real (file-based) ← quantum circuit signals ← QIP
bullbear_predictor (:5559) ← quantum ML signals ← QIP
"""

# ─── Config ───────────────────────────────────────────────────────────────────

BROKER_URL      = "http://127.0.0.1:5555"
GOOSE_AGENT_ID  = "goose_orchestrator"
QIP_AGENT_ID    = "quantum_intelligence_prime"
RESPONSE_TIMEOUT = 45   # seconds

# Quantum-relevant keywords for auto-detection
QUANTUM_TRIGGERS = [
    "portfolio", "allocation", "optimize", "quantum", "circuit", "qubit",
    "amplitude", "superposition", "entangle", "arbitrage", "grover", "qae",
    "risk", "monte carlo", "sharpe", "rebalance", "hedge", "position size",
    "btc", "eth", "sol", "crypto", "trade", "signal", "predict", "forecast",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

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


# ─── Core orchestrator ────────────────────────────────────────────────────────

class GooseQuantumOrchestrator:
    """
    The quantum tool layer for Stray Goose.

    Goose calls methods on this class to get quantum results.
    This class handles all mesh communication transparently.
    """

    def __init__(self, broker: str = BROKER_URL, agent_id: str = GOOSE_AGENT_ID):
        self.broker = broker
        self.agent_id = agent_id
        self._registered = False
        self._session_id = str(uuid.uuid4())[:8]
        self._calls_made = 0
        self._results_cache: Dict[str, Any] = {}
        self._ensure_registered()

    def _ensure_registered(self):
        if self._registered:
            return
        r = _post(f"{self.broker}/agents/register", {
            "agent_id": self.agent_id,
            "agent_type": "orchestrator",
            "endpoint": "",
            "capabilities": ["quantum_orchestration", "goose_integration"],
            "metadata": {
                "mesh_native": True,
                "session_id": self._session_id,
                "goose_integration": True,
            }
        })
        if r and r.get("status") == "success":
            # Subscribe to quantum channel
            _post(f"{self.broker}/mesh/subscribe", {
                "agent_id": self.agent_id, "channel": "quantum"
            })
            _post(f"{self.broker}/mesh/subscribe", {
                "agent_id": self.agent_id, "channel": "goose_results"
            })
            self._registered = True
            logger.info(f"GooseQuantumOrchestrator registered (session {self._session_id})")
        else:
            logger.warning(f"Registration failed: {r}")

    def _poll_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Poll the broker queue for this agent."""
        response = _get(
            f"{self.broker}/mesh/poll",
            params={"agent_id": self.agent_id, "max_messages": max_messages},
        )
        if not response or response.get("status") != "success":
            return []
        return response.get("messages", [])

    def _dispatch_and_wait(self, intent: str, problem: str,
                           extra_payload: dict = None,
                           timeout: int = RESPONSE_TIMEOUT) -> Dict[str, Any]:
        """Send intent to QIP, wait for response, return payload."""
        self._ensure_registered()
        self._calls_made += 1

        payload = {
            "intent": intent,
            "problem": problem,
            "session_id": self._session_id,
            "call_index": self._calls_made,
        }
        if extra_payload:
            payload.update(extra_payload)

        send_r = _post(f"{self.broker}/mesh/send", {
            "sender_id": self.agent_id,
            "recipient_id": QIP_AGENT_ID,
            "channel": "quantum",
            "payload": payload,
        })

        if not send_r or send_r.get("status") != "success":
            return {"success": False, "error": f"Send failed: {send_r}"}

        sent_id = send_r.get("message_id", "")
        logger.info(f"Intent '{intent}' dispatched [{sent_id[:8]}], waiting {timeout}s...")

        deadline = time.time() + timeout
        while time.time() < deadline:
            for msg in self._poll_messages():
                p = msg.get("payload", {})
                if (
                    msg.get("sender_id") == QIP_AGENT_ID
                    or p.get("responding_to") == sent_id
                    or p.get("request_id") == payload.get("request_id")
                    or p.get("source") == "quantum_intelligence_prime"
                ):
                    logger.info(f"Response received (success={p.get('success')})")
                    return p
            time.sleep(2)

        return {"success": False, "error": "Response timeout", "timeout_seconds": timeout}

    # ─── Public API (Goose-callable) ──────────────────────────────────────────

    def is_quantum_task(self, query: str) -> Tuple[bool, float]:
        """
        Detect if a query should be routed through quantum acceleration.
        Returns (is_quantum, confidence).
        """
        query_lower = query.lower()
        hits = sum(1 for kw in QUANTUM_TRIGGERS if kw in query_lower)
        confidence = min(1.0, hits * 0.15)
        return confidence >= 0.3, confidence

    def solve(self, problem: str, force: bool = False) -> Dict[str, Any]:
        """
        Solve any problem with quantum acceleration.
        Auto-detects if quantum is appropriate unless force=True.
        """
        is_q, conf = self.is_quantum_task(problem)
        if not is_q and not force:
            return {
                "success": True,
                "quantum_used": False,
                "reason": f"Low quantum relevance ({conf:.0%}) — use force=True to override",
                "result": "Use classical processing for this task."
            }

        result = self._dispatch_and_wait("solve_quantum_problem", problem)
        result["quantum_used"] = True
        result["confidence"] = conf
        return result

    def optimize_portfolio(
        self,
        assets: List[str] = None,
        capital_usd: float = 10.0,
        method: str = "quantum_amplitude_estimation"
    ) -> Dict[str, Any]:
        """
        Get quantum-optimal portfolio allocation.

        Returns:
            {
              "success": True,
              "allocations": {"BTC-USD": 0.40, "ETH-USD": 0.25, "SOL-USD": 0.35},
              "positions_usd": {"BTC-USD": 4.0, "ETH-USD": 2.5, "SOL-USD": 3.5},
              "method": "quantum_amplitude_estimation",
              "result": "full QIP circuit output..."
            }
        """
        if assets is None:
            assets = ["BTC-USD", "ETH-USD", "SOL-USD"]

        problem = (
            f"optimize portfolio allocation across {', '.join(assets)} "
            f"with total capital ${capital_usd:.2f} using {method}. "
            f"Maximize risk-adjusted returns. Current time: {datetime.now(timezone.utc).isoformat()}"
        )

        result = self._dispatch_and_wait("optimize_portfolio", problem, {
            "assets": assets,
            "capital_usd": capital_usd,
            "method": method,
        })

        # Parse allocations from result
        if result.get("success") and result.get("result"):
            import re
            allocs = {}
            for m in re.finditer(
                r"(BTC|ETH|SOL)(?:-USD)?[^0-9]*([0-9]+\.?[0-9]*)\s*%?",
                str(result["result"]), re.IGNORECASE
            ):
                asset = m.group(1).upper() + "-USD"
                val = float(m.group(2))
                if val > 1.0:
                    val /= 100.0
                allocs[asset] = round(val, 4)

            if allocs:
                total = sum(allocs.values())
                if total > 0:
                    allocs = {k: round(v / total, 4) for k, v in allocs.items()}
                result["allocations"] = allocs
                result["positions_usd"] = {
                    k: round(v * capital_usd, 2) for k, v in allocs.items()
                }
            else:
                # Default equal weight
                n = len(assets)
                w = round(1.0 / n, 4)
                result["allocations"] = {a: w for a in assets}
                result["positions_usd"] = {a: round(w * capital_usd, 2) for a in assets}

        return result

    def evolve_skills(self, skill_name: str = "arbitrage_detection") -> Dict[str, Any]:
        """Trigger QIP skill evolution."""
        return self._dispatch_and_wait(
            "evolve_quantum_skills",
            f"evolve and improve skill: {skill_name}",
            {"skill": skill_name}
        )

    def analyze_market(self, description: str) -> Dict[str, Any]:
        """Get quantum market analysis."""
        return self._dispatch_and_wait(
            "solve_quantum_problem",
            f"quantum market analysis: {description}",
        )

    def dispatch(self, intent: str, extra_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Public generic dispatch API advertised in the Goose profile."""
        extra_payload = extra_payload or {}
        problem = extra_payload.pop("problem", intent)
        return self._dispatch_and_wait(intent, problem, extra_payload=extra_payload)

    def qip_status(self) -> Dict[str, Any]:
        """Get QIP health and deployment status."""
        return self._dispatch_and_wait("get_deployment_status", "status check", timeout=15)

    def broker_status(self) -> Dict[str, Any]:
        """Get broker + mesh status."""
        health = _get(f"{self.broker}/health") or {}
        mesh = _get(f"{self.broker}/mesh/routing/status") or {}
        agents = _get(f"{self.broker}/mesh/routing/agents") or {}
        return {
            "broker_health": health,
            "mesh_status": mesh.get("mesh_routing", {}),
            "mesh_agents": list(agents.get("agents", {}).keys()),
        }

    def create_work_packet(self, task_description: str) -> Dict[str, Any]:
        """
        High-level: given a Goose task description, create a SIMP work packet.
        Detects quantum opportunity, routes accordingly, returns executable result.
        """
        is_q, conf = self.is_quantum_task(task_description)
        logger.info(f"Task: '{task_description[:60]}...' | quantum={is_q} ({conf:.0%})")

        if is_q:
            qip_result = self._dispatch_and_wait("solve_quantum_problem", task_description)
            return {
                "type": "quantum_work_packet",
                "status": "completed" if qip_result.get("success") else "requires_review",
                "task": task_description,
                "quantum_result": qip_result,
                "confidence": conf,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "route": "quantum_intelligence_prime",
            }
        else:
            return {
                "type": "classical_work_packet",
                "status": "ready_for_classical_processing",
                "task": task_description,
                "quantum_confidence": conf,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "route": "standard_broker_routing",
            }

    def run(self, query: str) -> str:
        """
        Main entry point for Goose.
        Takes a natural language query, returns a string result.
        """
        packet = self.create_work_packet(query)

        if packet["type"] == "quantum_work_packet":
            qr = packet.get("quantum_result", {})
            if qr.get("success"):
                return (
                    f"[Quantum Result]\n"
                    f"{qr.get('result', 'No result text')}\n\n"
                    f"Metadata: {json.dumps(qr.get('metadata', {}), indent=2)}"
                )
            else:
                return (
                    f"[Quantum Processing — Partial Result]\n"
                    f"Error: {qr.get('error', qr.get('error_code', 'unknown'))}\n"
                    f"The quantum engine processed your query but returned an error. "
                    f"Check that quantum_mesh_consumer.py is running."
                )
        else:
            confidence = packet.get('confidence') or packet.get('quantum_confidence', 0.0)
            return (
                f"[Classical Processing]\n"
                f"This task ({query[:80]}) has low quantum relevance ({confidence:.0%}). "
                f"Route through standard broker agents."
            )


# ─── Goose session config (JSON profile) ─────────────────────────────────────

def generate_goose_profile() -> dict:
    """
    Generate the JSON profile to give Stray Goose quantum capabilities.
    Save this as goose_quantum_profile.json and load at session start.
    """
    return {
        "profile_name": "simp_quantum",
        "version": "1.0.0",
        "description": "Stray Goose quantum-powered SIMP trading mesh integration",
        "broker_url": BROKER_URL,
        "agent_id": GOOSE_AGENT_ID,
        "system_context": GOOSE_SYSTEM_CONTEXT,
        "tools": [
            {
                "name": "quantum_solve",
                "description": "Solve any problem using quantum computing via QIP",
                "command": f"python3.10 {Path(__file__).name} --solve",
                "usage": "quantum_solve <problem description>"
            },
            {
                "name": "quantum_optimize_portfolio",
                "description": "Get quantum-optimal portfolio allocation for BTC/ETH/SOL",
                "command": f"python3.10 {Path(__file__).name} --task optimize_portfolio",
                "usage": "quantum_optimize_portfolio [--assets BTC ETH SOL] [--capital 10.0]"
            },
            {
                "name": "quantum_market_analysis",
                "description": "Quantum market analysis for trading signals",
                "command": f"python3.10 {Path(__file__).name} --task market_analysis",
                "usage": "quantum_market_analysis <market description>"
            },
            {
                "name": "qip_status",
                "description": "Check quantum_intelligence_prime status and capabilities",
                "command": f"python3.10 {Path(__file__).name} --status",
                "usage": "qip_status"
            },
            {
                "name": "dispatch_intent",
                "description": "Dispatch a named intent to any mesh agent",
                "command": f"python3.10 {Path(__file__).name} --dispatch-intent",
                "usage": "dispatch_intent <intent_name> <agent_id> <problem>"
            },
            {
                "name": "broker_status",
                "description": "Get full SIMP broker and mesh status",
                "command": f"python3.10 {Path(__file__).name} --broker-status",
                "usage": "broker_status"
            }
        ],
        "startup_sequence": [
            "python3.10 bin/start_server.py &",
            "sleep 3",
            f"python3.10 quantum_mesh_consumer.py &",
            f"python3.10 quantum_signal_bridge.py &",
            f"python3.10 {Path(__file__).name} --status",
        ],
        "revenue_pipeline": {
            "gate4_real": "Coinbase live trading $1-$10, fed by quantum_signal_bridge",
            "quantumarb_primary": "Mesh-routed arbitrage signals from QIP",
            "bullbear_predictor": "Quantum ML predictions for BTC direction",
        }
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Goose Quantum Orchestrator — SIMP quantum mesh bridge"
    )
    parser.add_argument("query", nargs="?", help="Natural language query to process")
    parser.add_argument("--broker", default=BROKER_URL)
    parser.add_argument("--solve", metavar="PROBLEM", help="Solve a quantum problem")
    parser.add_argument("--task", choices=["optimize_portfolio", "market_analysis", "evolve_skills"],
                        help="Run a specific quantum task")
    parser.add_argument("--assets", nargs="+", default=["BTC-USD", "ETH-USD", "SOL-USD"])
    parser.add_argument("--capital", type=float, default=10.0)
    parser.add_argument("--dispatch-intent", metavar="INTENT",
                        help="Dispatch a named intent to QIP")
    parser.add_argument("--problem", default="")
    parser.add_argument("--status", action="store_true", help="Show QIP + broker status")
    parser.add_argument("--broker-status", action="store_true")
    parser.add_argument("--generate-profile", action="store_true",
                        help="Print Goose profile JSON and exit")
    args = parser.parse_args()

    if args.generate_profile:
        print(json.dumps(generate_goose_profile(), indent=2))
        # Also save it
        profile_path = Path("goose_quantum_profile.json")
        profile_path.write_text(json.dumps(generate_goose_profile(), indent=2))
        print(f"\nSaved to {profile_path}", file=sys.stderr)
        return

    qo = GooseQuantumOrchestrator(broker=args.broker)

    if args.status or args.broker_status:
        status = qo.broker_status()
        qip = qo.qip_status()
        print("\n=== Broker Status ===")
        print(json.dumps(status, indent=2))
        print("\n=== QIP Status ===")
        print(json.dumps(qip, indent=2))

    elif args.solve:
        result = qo.solve(args.solve, force=True)
        print(json.dumps(result, indent=2))

    elif args.task == "optimize_portfolio":
        result = qo.optimize_portfolio(assets=args.assets, capital_usd=args.capital)
        print(json.dumps(result, indent=2))

    elif args.task == "market_analysis":
        problem = args.problem or "BTC ETH SOL short-term price direction"
        result = qo.analyze_market(problem)
        print(json.dumps(result, indent=2))

    elif args.task == "evolve_skills":
        result = qo.evolve_skills()
        print(json.dumps(result, indent=2))

    elif args.dispatch_intent:
        result = qo._dispatch_and_wait(args.dispatch_intent, args.problem or args.dispatch_intent)
        print(json.dumps(result, indent=2))

    elif args.query:
        result = qo.run(args.query)
        print(result)

    else:
        parser.print_help()
        print("\nExamples:")
        print('  python3.10 goose_quantum_orchestrator.py "optimize my BTC ETH SOL portfolio"')
        print('  python3.10 goose_quantum_orchestrator.py --task optimize_portfolio --capital 10')
        print('  python3.10 goose_quantum_orchestrator.py --solve "detect arbitrage opportunity"')
        print('  python3.10 goose_quantum_orchestrator.py --status')
        print('  python3.10 goose_quantum_orchestrator.py --generate-profile')


if __name__ == "__main__":
    main()
