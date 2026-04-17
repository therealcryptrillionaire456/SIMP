#!/usr/bin/env python3
"""
SIMP Phase 3 Activation Script
================================
Wires QuantumArb to the live mesh and activates quantum intelligence.

Run from: /Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp
Usage:    python3.10 activate_phase3.py [--quantum] [--verbose]

Flags:
  --quantum   Also activate PennyLane local quantum simulation
  --verbose   Full debug logging
"""

import sys
import os
import time
import argparse
import logging
import threading
import socket
import json
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def activate_quantumarb_mesh(broker_url: str = "http://127.0.0.1:5555"):
    """Phase 3: Wire QuantumArb to the mesh bus."""
    print("\n🔌 Activating QuantumArb → Mesh integration...")

    from simp.organs.quantumarb.enhanced_mesh_integration import EnhancedQuantumArbMeshIntegration

    integration = EnhancedQuantumArbMeshIntegration(
        agent_id="quantumarb_primary",
        broker_url=broker_url,
        enable_security=True,
        enable_discovery=True,
    )

    # Register custom handlers
    def on_safety_command(command):
        print(f"  ⚠️  Safety command received: {command.command} — {command.reason}")

    def on_trade_event(event):
        print(f"  💰 Trade event: {event.event_type.value} | {event.symbol} @ {event.price}")

    integration.register_safety_command_handler(on_safety_command)
    integration.register_trade_event_handler(on_trade_event)

    success = integration.start()
    if success:
        print("  ✅ QuantumArb mesh integration LIVE")
        print("     Broadcasting to: trade_updates, trade_events")
        print("     Listening on:    safety_alerts, system_commands")
    else:
        print("  ❌ QuantumArb mesh integration failed to start")
        print("     Is the broker running at", broker_url, "?")

    return integration if success else None


def activate_trust_graph():
    """Wire L4 TrustGraph into live state."""
    print("\n🧠 Activating L4 TrustGraph...")

    from simp.mesh.trust_graph import get_trust_graph
    tg = get_trust_graph(autostart=True)
    snap = tg.snapshot()
    # snapshot() returns {"timestamp":..., "agent_count":..., "agents":{id: dict}}
    agents = snap.get("agents", {})
    count = snap.get("agent_count", len(agents))
    print(f"  ✅ TrustGraph live — {count} agents scored")
    for agent_id, entry in list(agents.items())[:5]:
        score = entry.get('effective_score', entry.get('trust_score', 0.0))
        delta = entry.get('delta', 0.0)
        receipts = entry.get('sent_deliveries', 0) + entry.get('recv_deliveries', 0)
        print(f"     {agent_id}: score={score:.2f}  delta={delta:+.2f}  receipts={receipts}")
    if count > 5:
        print(f"     ... and {count - 5} more")
    return tg


def activate_brp_gateway():
    """Wire BRP Mesh Gateway for packet-level screening."""
    print("\n🛡️  Activating BRP Mesh Gateway...")

    from simp.mesh.brp_mesh_gateway import get_brp_mesh_gateway
    gw = get_brp_mesh_gateway()
    status = gw.get_status()
    stats = status.get("stats", {})
    print(f"  ✅ BRP gateway active  (dry_run={status.get('dry_run', False)})")
    print(f"     Screened packets: {stats.get('packets_screened', 0)}")
    print(f"     Denied packets:   {stats.get('packets_denied', 0)}")
    print(f"     Active blocks:    {status.get('blocklist_count', 0)}")
    print(f"     BRP engine:       {'loaded' if status.get('brp_loaded') else 'lazy (loads on first threat)'}")
    return gw


def activate_pennylane():
    """Activate local quantum simulation via PennyLane."""
    print("\n⚛️  Activating PennyLane quantum simulator...")

    try:
        import pennylane  # noqa: F401
    except ImportError:
        print("  ⚠️  PennyLane not installed. Run:")
        print("     pip install pennylane --break-system-packages")
        print("  (or inside venv: pip install pennylane)")
        return None

    try:
        from simp.organs.quantum.quantum_adapter import PennyLaneAdapter
        adapter = PennyLaneAdapter()
        connected = adapter.connect()
        if connected:
            health = adapter.health_check()
            print(f"  ✅ PennyLane connected — backend: {health.get('backend', 'default.qubit')}")
            print(f"     Status: {health.get('status', 'unknown')}")
            print(f"     Algorithms: {', '.join(health.get('algorithms', []))}")
        else:
            print("  ❌ PennyLane connection failed")
        return adapter if connected else None
    except Exception as e:
        print(f"  ❌ PennyLane activation error: {e}")
        return None


def activate_quantum_intelligence(pennylane_adapter=None):
    """Activate QuantumIntelligentAgent and register as mesh agent."""
    print("\n🤖 Activating QuantumIntelligentAgent...")

    try:
        from simp.organs.quantum_intelligence.production_agent import create_production_agent
        from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
        from simp.mesh.packet import create_event_packet

        agent = create_production_agent(
            agent_id="quantum_intelligence_prime",
            initial_level="quantum_aware",
        )

        bus = get_enhanced_mesh_bus()
        bus.register_agent("quantum_intelligence_prime")
        bus.subscribe("quantum_intelligence_prime", "quantum_problems")
        bus.subscribe("quantum_intelligence_prime", "quantum_circuits")

        print("  ✅ QuantumIntelligentAgent LIVE")
        print(f"     Agent ID: quantum_intelligence_prime")
        print(f"     Level: quantum_aware")
        print(f"     Deployment stage: {agent.deployment_manager.config.stage.value}")
        print(f"     Listening on: quantum_problems, quantum_circuits")
        print(f"     Features: QUANTUM_SKILL_EVOLUTION={agent.deployment_manager.config.feature_flags.get('quantum_skill_evolution', False)}")

        # Run a quick local test problem
        print("\n     🧪 Running test quantum problem...")
        try:
            result = agent.solve_quantum_problem_with_rollout(
                problem_description="Find optimal portfolio allocation across 3 assets",
                problem_type="optimization",
                qubits=3,
                request_id="activation_test_001",
            )
            status = result.get("status", "unknown")
            print(f"     Test result status: {status}")
            if "quantum_advantage" in result:
                print(f"     Quantum advantage: {result['quantum_advantage']:.3f}")
        except Exception as test_err:
            print(f"     Test skipped: {test_err}")

        return agent

    except Exception as e:
        print(f"  ⚠️  QuantumIntelligentAgent activation: {e}")
        print("     (Non-fatal — agent will activate when quantum deps are installed)")
        return None


class QuantumIntelligenceBrokerAdapter:
    """Thin HTTP adapter so the broker can monitor and route to the quantum intelligence agent."""

    def __init__(self, agent):
        self.agent_id = agent.agent_id
        self.intent_handlers = {
            "health_check": self.handle_health_check,
            "status_check": self.handle_get_deployment_status,
            "get_deployment_status": self.handle_get_deployment_status,
            "market_analysis": self.handle_solve_quantum_problem,
            "solve_quantum_problem": self.handle_solve_quantum_problem,
            "optimize_portfolio": self.handle_optimize_portfolio,
            "evolve_quantum_skills": self.handle_evolve_quantum_skills,
        }
        self._agent = agent

    def handle_health_check(self, _params):
        return self._agent.get_deployment_status()

    def handle_get_deployment_status(self, _params):
        return self._agent.get_deployment_status()

    def handle_solve_quantum_problem(self, params):
        return self._agent.solve_quantum_problem_with_rollout(
            problem_description=params.get("problem_description", "Solve a generic optimization problem"),
            problem_type=params.get("problem_type", "optimization"),
            qubits=int(params.get("qubits", 3)),
            request_id=params.get("request_id"),
            metadata=params.get("metadata"),
        )

    def handle_optimize_portfolio(self, params):
        return self._agent.optimize_portfolio_with_quantum(
            opportunities=params.get("opportunities", []),
            capital=float(params.get("capital", 0.0)),
            risk_tolerance=float(params.get("risk_tolerance", 0.3)),
            request_id=params.get("request_id"),
        )

    def handle_evolve_quantum_skills(self, params):
        return self._agent.evolve_quantum_skills(
            focus_area=params.get("focus_area"),
            request_id=params.get("request_id"),
        )


class QuantumArbBrokerAdapter:
    """Thin HTTP adapter so the broker can monitor and query QuantumArb mesh state."""

    def __init__(self, integration):
        self.agent_id = integration.agent_id
        self.intent_handlers = {
            "health_check": self.handle_health_check,
            "status_check": self.handle_get_status,
            "get_status": self.handle_get_status,
            "get_statistics": self.handle_get_statistics,
        }
        self._integration = integration

    def handle_health_check(self, _params):
        return self._integration.get_status()

    def handle_get_status(self, _params):
        return self._integration.get_status()

    def handle_get_statistics(self, _params):
        return self._integration.get_statistics()


def start_embedded_agent_server(agent, port: int):
    """Start a lightweight HTTP wrapper for a live in-process agent."""
    from simp.server.agent_server import SimpAgentServer

    server = SimpAgentServer(agent=agent, host="127.0.0.1", port=port)
    thread = threading.Thread(
        target=server.run,
        kwargs={"threaded": True},
        daemon=True,
        name=f"{agent.agent_id}-http-server",
    )
    thread.start()
    return server, thread


def find_available_port(preferred_port: int, max_tries: int = 25) -> int:
    """Return the preferred port if free, otherwise the next available port."""
    for offset in range(max_tries):
        port = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No available port found near {preferred_port}")


def wait_for_agent_health(endpoint: str, timeout_seconds: float = 5.0) -> bool:
    """Poll /health until the agent endpoint is live or timeout expires."""
    deadline = time.time() + timeout_seconds
    health_url = f"{endpoint.rstrip('/')}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2.0) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    return False


def wait_for_intent_result(client, intent_id: str, timeout_seconds: float = 10.0) -> Dict:
    """Poll broker intent status until the routed intent completes or times out."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = client.get_intent_status(intent_id) or {}
        intent = status.get("intent") or {}
        if intent.get("status") in {"completed", "failed"}:
            return intent
        time.sleep(0.25)
    return {}


def register_embedded_agent(
    agent_id: str,
    agent_type: str,
    endpoint: str,
    broker_url: str,
    capabilities,
    metadata=None,
) -> bool:
    """Register a live in-process agent with the broker."""
    from simp.server.agent_http_client import SimpHttpClient

    agents_url = f"{broker_url.rstrip('/')}/agents"
    try:
        with urllib.request.urlopen(agents_url, timeout=5.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
            existing = payload.get("agents", {}).get(agent_id)
    except Exception:
        existing = None

    if existing:
        existing_endpoint = existing.get("endpoint")
        if existing_endpoint == endpoint and wait_for_agent_health(endpoint):
            return True

        try:
            delete_request = urllib.request.Request(
                f"{broker_url.rstrip('/')}/agents/{agent_id}",
                method="DELETE",
            )
            with urllib.request.urlopen(delete_request, timeout=5.0) as response:
                if response.status not in (200, 204):
                    return False
        except Exception:
            return False

    client = SimpHttpClient(
        agent_id=agent_id,
        agent_type=agent_type,
        broker_url=broker_url,
        timeout=10.0,
    )
    result = client.register(
        endpoint=endpoint,
        capabilities=capabilities,
        metadata=metadata or {},
    )
    return bool(result and result.get("status") == "success")


def _find_existing_open_channel(settler, initiator_id: str, counterparty_id: str) -> Optional[Dict]:
    from simp.mesh.enhanced_bus import ChannelState

    for channel in settler.list_channels(state_filter=ChannelState.OPEN):
        if (
            channel.get("initiator_id") == initiator_id
            and channel.get("counterparty_id") == counterparty_id
        ):
            return channel
    return None


def automate_payment_lifecycle(
    agent_pairs: List[Tuple[str, str]],
    opening_balance: float = 5.0,
    payment_amount: float = 0.25,
    target_sequence: int = 1,
) -> List[Dict[str, object]]:
    """Open payment channels for active agents and advance them through real lifecycle APIs."""
    from simp.mesh.enhanced_bus import PaymentSettler, get_enhanced_mesh_bus

    bus = get_enhanced_mesh_bus()
    results: List[Dict[str, object]] = []

    for initiator_id, counterparty_id in agent_pairs:
        settler = PaymentSettler(
            agent_id=initiator_id,
            db_path=str(bus.log_dir / "mesh_payments.db"),
            shared_secret=bus._secret,
        )
        channel = _find_existing_open_channel(settler, initiator_id, counterparty_id)
        created = False
        if channel is None:
            opened = bus.open_payment_channel(
                initiator_id=initiator_id,
                counterparty_id=counterparty_id,
                my_balance=opening_balance,
                their_balance=0.0,
            )
            if opened is None:
                results.append({
                    "initiator_id": initiator_id,
                    "counterparty_id": counterparty_id,
                    "status": "failed",
                    "reason": "open_channel_failed",
                })
                continue
            channel_id = opened.channel_id
            sequence = opened.sequence
            created = True
        else:
            channel_id = channel["channel_id"]
            sequence = int(channel.get("sequence", 0))

        desired_sequence = max(target_sequence, sequence + 1)

        while sequence < desired_sequence:
            if not settler.pay(
                channel_id=channel_id,
                amount=payment_amount,
                description=f"phase3 lifecycle payment {sequence + 1}",
            ):
                results.append({
                    "initiator_id": initiator_id,
                    "counterparty_id": counterparty_id,
                    "channel_id": channel_id,
                    "status": "failed",
                    "reason": "payment_failed",
                    "sequence": sequence,
                })
                break
            sequence += 1
        else:
            refreshed = settler.get_channel(channel_id)
            results.append({
                "initiator_id": initiator_id,
                "counterparty_id": counterparty_id,
                "channel_id": channel_id,
                "status": "ok",
                "created": created,
                "sequence": refreshed.sequence if refreshed else sequence,
                "initiator_balance": refreshed.initiator_balance if refreshed else None,
                "counterparty_balance": refreshed.counterparty_balance if refreshed else None,
            })

    return results


def verify_broker_routed_intents(broker_url: str) -> List[Tuple[str, bool, Dict]]:
    """Send real intents through the broker to the live quantum endpoints."""
    from simp.server.agent_http_client import SimpHttpClient

    client = SimpHttpClient(
        agent_id="phase3_verifier",
        agent_type="ops",
        broker_url=broker_url,
        timeout=20.0,
    )

    checks: List[Tuple[str, bool, Dict]] = []

    quantumarb_route = client.send_intent(
        target_agent="quantumarb_primary",
        intent_type="status_check",
        params={},
    ) or {}
    quantumarb_status = wait_for_intent_result(
        client,
        quantumarb_route.get("intent_id", ""),
    ) if quantumarb_route.get("intent_id") else {}
    checks.append((
        "quantumarb_primary.status_check",
        quantumarb_status.get("status") == "completed"
        and isinstance(quantumarb_status.get("response"), dict)
        and (
            quantumarb_status["response"].get("status") is not None
            or quantumarb_status["response"].get("statistics") is not None
            or quantumarb_status["response"].get("mesh_integration") is not None
        ),
        {
            "route": quantumarb_route,
            "intent": quantumarb_status,
        },
    ))

    quantum_problem_route = client.send_intent(
        target_agent="quantum_intelligence_prime",
        intent_type="market_analysis",
        params={
            "problem_description": "Broker-routed quantum intent verification for portfolio optimization",
            "problem_type": "optimization",
            "qubits": 3,
            "request_id": "phase3_broker_route_verify",
            "metadata": {"source": "activate_phase3"},
        },
    ) or {}
    quantum_problem = wait_for_intent_result(
        client,
        quantum_problem_route.get("intent_id", ""),
        timeout_seconds=20.0,
    ) if quantum_problem_route.get("intent_id") else {}
    success = (
        quantum_problem.get("status") == "completed"
        and isinstance(quantum_problem.get("response"), dict)
        and quantum_problem["response"].get("quantum_advantage") is not None
    )
    checks.append((
        "quantum_intelligence_prime.market_analysis",
        success,
        {
            "route": quantum_problem_route,
            "intent": quantum_problem,
        },
    ))

    return checks


def verify_live_consensus(trust_graph) -> Optional[Dict]:
    """Run a small trust-weighted L5 consensus round and return the result."""
    from simp.mesh.consensus import MeshConsensusNode, VoteChoice

    participant_ids = ["simp_broker", "quantumarb", "kashclaw"]
    nodes = [MeshConsensusNode(agent_id=agent_id, trust_graph=trust_graph) for agent_id in participant_ids]

    try:
        for node in nodes:
            node.start()

        proposal = nodes[0].propose(
            topic="phase3_live_consensus_verification",
            payload={"verified_at": time.time()},
            required_quorum=0.67,
            ttl=30.0,
            metadata={"source": "activate_phase3"},
        )

        time.sleep(0.5)
        for node in nodes[1:]:
            node._handle_incoming_proposal(proposal.to_dict())
        votes = []
        for node in nodes:
            vote = node.vote(proposal.proposal_id, VoteChoice.APPROVE, rationale="phase3 verification")
            if vote is not None:
                votes.append(vote)
        for node in nodes:
            for vote in votes:
                node._handle_incoming_vote(vote.to_dict())

        time.sleep(1.0)
        result = nodes[0].aggregate_now(proposal.proposal_id)
        if not result:
            return None
        return result.to_dict()
    finally:
        for node in nodes:
            try:
                node.stop()
            except Exception:
                pass


def check_broker(broker_url: str) -> bool:
    """Verify broker is live before activation."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{broker_url}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def print_system_status():
    """Print final system status summary."""
    print("\n" + "="*60)
    print("  SIMP SYSTEM STATUS")
    print("="*60)

    try:
        from simp.mesh.trust_graph import get_trust_graph
        tg = get_trust_graph(autostart=False)
        snap = tg.snapshot()
        count = snap.get("agent_count", len(snap.get("agents", {})))
        print(f"  L4 TrustGraph:      {count} agents scored")
    except Exception:
        print("  L4 TrustGraph:      not initialized")

    try:
        from simp.mesh.brp_mesh_gateway import get_brp_mesh_gateway
        gw = get_brp_mesh_gateway()
        s = gw.get_status()
        stats = s.get("stats", {})
        print(f"  BRP Gateway:        screened={stats.get('packets_screened',0)} denied={stats.get('packets_denied',0)} blocks={s.get('blocklist_count',0)}")
    except Exception:
        print("  BRP Gateway:        not initialized")

    try:
        from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
        bus = get_enhanced_mesh_bus()
        print(f"  Mesh Bus:           live")
    except Exception:
        print("  Mesh Bus:           not initialized")

    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="SIMP Phase 3 Activation")
    parser.add_argument("--broker", default="http://127.0.0.1:5555", help="Broker URL")
    parser.add_argument("--quantum", action="store_true", help="Activate PennyLane quantum simulation")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--no-quantumarb", action="store_true", help="Skip QuantumArb activation")
    parser.add_argument("--quantumarb-port", type=int, default=8770, help="HTTP port for QuantumArb broker-visible endpoint")
    parser.add_argument("--quantum-intelligence-port", type=int, default=8771, help="HTTP port for QuantumIntelligence broker-visible endpoint")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("╔══════════════════════════════════════════════════╗")
    print("║  SIMP PHASE 3 ACTIVATION — KLOUTBOT              ║")
    print("║  Wiring all dormant modules to the live mesh     ║")
    print("╚══════════════════════════════════════════════════╝")

    # Check broker
    print(f"\n🔍 Checking broker at {args.broker}...")
    if check_broker(args.broker):
        print(f"  ✅ Broker live at {args.broker}")
    else:
        print(f"  ⚠️  Broker not reachable at {args.broker}")
        print("     Some activations will run in offline mode")

    # Always activate these — they work offline
    tg = activate_trust_graph()
    gw = activate_brp_gateway()

    # QuantumArb Phase 3 — needs broker
    integration = None
    quantumarb_registered = False
    if not args.no_quantumarb:
        integration = activate_quantumarb_mesh(args.broker)
        if integration:
            print("\n🌐 Exposing QuantumArb HTTP endpoint...")
            quantumarb_adapter = QuantumArbBrokerAdapter(integration)
            quantumarb_port = find_available_port(args.quantumarb_port)
            quantumarb_endpoint = f"http://127.0.0.1:{quantumarb_port}"
            start_embedded_agent_server(quantumarb_adapter, quantumarb_port)
            if wait_for_agent_health(quantumarb_endpoint):
                registered = register_embedded_agent(
                    agent_id="quantumarb_primary",
                    agent_type="quantumarb",
                    endpoint=quantumarb_endpoint,
                    broker_url=args.broker,
                    capabilities=["health_check", "get_status", "get_statistics"],
                    metadata={
                        "service": "QuantumArb Embedded Endpoint",
                        "mesh_enabled": True,
                    },
                )
            else:
                registered = False
            if registered:
                quantumarb_registered = True
                print(f"  ✅ QuantumArb registered with broker at {quantumarb_endpoint}")
            else:
                print(f"  ⚠️  QuantumArb HTTP endpoint started but broker registration failed at {quantumarb_endpoint}")

    # Optional quantum backends
    pennylane_adapter = None
    if args.quantum:
        pennylane_adapter = activate_pennylane()
        if pennylane_adapter:
            quantum_agent = activate_quantum_intelligence(pennylane_adapter)
            if quantum_agent:
                print("\n🌐 Exposing QuantumIntelligence HTTP endpoint...")
                qi_adapter = QuantumIntelligenceBrokerAdapter(quantum_agent)
                qi_port = find_available_port(args.quantum_intelligence_port)
                qi_endpoint = f"http://127.0.0.1:{qi_port}"
                start_embedded_agent_server(qi_adapter, qi_port)
                if wait_for_agent_health(qi_endpoint):
                    registered = register_embedded_agent(
                        agent_id="quantum_intelligence_prime",
                        agent_type="quantum_intelligence",
                        endpoint=qi_endpoint,
                        broker_url=args.broker,
                        capabilities=[
                            "health_check",
                            "get_deployment_status",
                            "solve_quantum_problem",
                            "optimize_portfolio",
                            "evolve_quantum_skills",
                        ],
                        metadata={
                            "service": "Quantum Intelligence Embedded Endpoint",
                            "quantum_backend": "pennylane" if pennylane_adapter else "unknown",
                        },
                    )
                else:
                    registered = False
                if registered:
                    print("\n💸 Activating payment channel lifecycle...")
                    payment_results = automate_payment_lifecycle(
                        [
                            ("quantumarb_primary", "ktc_agent"),
                            ("quantumarb_primary", "quantum_intelligence_prime"),
                            ("quantum_intelligence_prime", "ktc_agent"),
                        ],
                        target_sequence=1,
                    )
                    for item in payment_results:
                        if item.get("status") == "ok":
                            print(
                                f"  ✅ Payment channel {item['channel_id']} "
                                f"{item['initiator_id']} -> {item['counterparty_id']} "
                                f"seq={item['sequence']}"
                            )
                        else:
                            print(
                                f"  ⚠️  Payment lifecycle issue for "
                                f"{item['initiator_id']} -> {item['counterparty_id']}: {item.get('reason')}"
                            )

                    print("\n🗳️  Verifying L5 MeshConsensusNode...")
                    consensus_result = verify_live_consensus(tg)
                    if consensus_result:
                        print(
                            f"  ✅ Consensus verified — state={consensus_result['state']} "
                            f"approval={consensus_result['approval_ratio']:.2f} "
                            f"votes={consensus_result['vote_count']}"
                        )
                    else:
                        print("  ⚠️  Consensus verification did not return a result")

                    print("\n🔁 Verifying broker-routed quantum intents...")
                    route_checks = verify_broker_routed_intents(args.broker)
                    for label, ok, payload in route_checks:
                        if ok:
                            print(f"  ✅ Routed intent succeeded: {label}")
                        else:
                            print(f"  ⚠️  Routed intent failed: {label} -> {payload}")

                    print(f"  ✅ QuantumIntelligence registered with broker at {qi_endpoint}")
                else:
                    print(f"  ⚠️  QuantumIntelligence HTTP endpoint started but broker registration failed at {qi_endpoint}")
    else:
        print("\n⚛️  Quantum simulation: pass --quantum flag to activate PennyLane")

    # Summary
    print_system_status()

    if integration:
        print("\n⏳ Mesh integration running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(5)
                stats = integration.get_statistics()
                trade_events_sent = stats.get("trade_events_sent", 0)
                safety_commands_received = stats.get("safety_commands_received", 0)
                if trade_events_sent > 0 or safety_commands_received > 0:
                    print(f"  📊 QuantumArb mesh stats: "
                          f"events_sent={trade_events_sent} "
                          f"safety_cmds={safety_commands_received}")
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping mesh integration...")
            integration.stop()
            print("✅ Shutdown complete.")


if __name__ == "__main__":
    main()
