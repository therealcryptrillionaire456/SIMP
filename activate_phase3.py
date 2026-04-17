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
    if not args.no_quantumarb:
        integration = activate_quantumarb_mesh(args.broker)

    # Optional quantum backends
    pennylane_adapter = None
    if args.quantum:
        pennylane_adapter = activate_pennylane()
        if pennylane_adapter:
            activate_quantum_intelligence(pennylane_adapter)
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
