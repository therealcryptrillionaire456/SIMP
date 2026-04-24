#!/usr/bin/env python3.10
"""
debug_qip.py
Diagnoses exactly why QIP polls but doesn't process requests.
Run this FIRST to identify the specific failure point.

Usage: python3.10 debug_qip.py
"""

import sys
import json
import time
import traceback
import requests
from pathlib import Path

BROKER_URL = "http://127.0.0.1:5555"
QIP_ID     = "quantum_intelligence_prime"

print("=" * 60)
print("  QIP DIAGNOSTIC — finding the processing failure")
print("=" * 60)
print()

# ── 1. Broker alive? ──────────────────────────────────────────
print("── 1. Broker health ────────────────────────────────────")
try:
    r = requests.get(f"{BROKER_URL}/health", timeout=5)
    print(f"  ✅ Broker: {r.status_code} | {r.json()}")
except Exception as e:
    print(f"  ❌ Broker unreachable: {e}")
    sys.exit(1)
print()

# ── 2. QIP registered? ────────────────────────────────────────
print("── 2. QIP registration status ──────────────────────────")
try:
    r = requests.get(f"{BROKER_URL}/agents", timeout=5)
    agents = r.json()
    qip_found = False
    for agent in (agents.get("agents") or agents.get("results") or []):
        aid = agent.get("agent_id") or agent.get("id") or ""
        if QIP_ID in str(aid):
            qip_found = True
            print(f"  ✅ QIP found: {json.dumps(agent, indent=4)}")
    if not qip_found:
        print(f"  ❌ QIP NOT in agent list — quantum_mesh_consumer.py may not be running")
except Exception as e:
    print(f"  ⚠️  Could not list agents: {e}")
print()

# ── 3. QIP in mesh routing? ───────────────────────────────────
print("── 3. QIP in mesh routing table ────────────────────────")
try:
    r = requests.get(f"{BROKER_URL}/mesh/routing/agents", timeout=5)
    mesh_agents = r.json()
    print(f"  Raw response: {json.dumps(mesh_agents, indent=2)[:500]}")
    agents_list = (mesh_agents.get("agents") or
                   mesh_agents.get("mesh_agents") or
                   mesh_agents.get("results") or [])
    qip_mesh = any(QIP_ID in str(a) for a in agents_list)
    if qip_mesh:
        print(f"  ✅ QIP in mesh routing")
    else:
        print(f"  ⚠️  QIP NOT in mesh routing table")
        print(f"  → Fix: ensure quantum_mesh_consumer registers via /mesh/subscribe")
except Exception as e:
    print(f"  ⚠️  Mesh routing check failed: {e}")
print()

# ── 4. Can we send to QIP and get a response? ─────────────────
print("── 4. Direct QIP round-trip test ───────────────────────")
TEST_AGENT = "debug_probe"
# Register probe
requests.post(f"{BROKER_URL}/agents/register", json={
    "agent_id": TEST_AGENT, "name": "Debug Probe", "version": "1.0",
    "capabilities": ["debug"],
}, timeout=5)
requests.post(f"{BROKER_URL}/mesh/subscribe", json={
    "agent_id": TEST_AGENT, "channel": "quantum"
}, timeout=5)

# Send health_check intent
requests.post(f"{BROKER_URL}/mesh/send", json={
    "sender_id":    TEST_AGENT,
    "recipient_id": QIP_ID,
    "channel":      "quantum",
    "payload": {"intent": "health_check", "problem": "ping"},
}, timeout=5)

print(f"  Sent health_check to QIP. Polling for 15s...")
got_response = False
for i in range(5):
    time.sleep(3)
    poll = requests.post(f"{BROKER_URL}/mesh/poll", json={
        "agent_id": TEST_AGENT, "channel": "quantum"
    }, timeout=5).json()
    msgs = poll.get("messages", [])
    if msgs:
        print(f"  ✅ QIP responded after {(i+1)*3}s:")
        print(f"     {json.dumps(msgs[0], indent=4)[:400]}")
        got_response = True
        break
    print(f"  ... {(i+1)*3}s — no response yet")

if not got_response:
    print(f"  ❌ QIP DID NOT RESPOND in 15s")
    print(f"  → Check quantum_mesh_consumer.py logs: data/logs/goose/qip.log")
print()

# ── 5. Check quantum engine imports ──────────────────────────
print("── 5. Quantum engine import test ───────────────────────")
try:
    from pathlib import Path as P
    sys.path.insert(0, ".")
    from quantum_mode_engine import QuantumModeEngine
    print("  ✅ quantum_mode_engine imports OK")
    try:
        engine = QuantumModeEngine(config_path=P("quantum_mode_config.json"))
        print(f"  ✅ QuantumModeEngine instantiated OK")
    except Exception as e:
        print(f"  ❌ QuantumModeEngine init failed: {e}")
        traceback.print_exc()
except ImportError as e:
    print(f"  ❌ Cannot import quantum_mode_engine: {e}")
print()

# ── 6. Check integration imports ─────────────────────────────
print("── 6. StrayGooseQuantumIntegration import test ─────────")
try:
    from stray_goose_quantum_integration import StrayGooseQuantumIntegration
    print("  ✅ stray_goose_quantum_integration imports OK")
    try:
        integration = StrayGooseQuantumIntegration()
        print(f"  ✅ StrayGooseQuantumIntegration instantiated OK")
        result = integration.process_query("test health check", force_quantum=True)
        print(f"  ✅ process_query returned: {str(result)[:200]}")
    except Exception as e:
        print(f"  ❌ Integration failed: {e}")
        traceback.print_exc()
except ImportError as e:
    print(f"  ❌ Cannot import stray_goose_quantum_integration: {e}")
print()

# ── 7. Config files ───────────────────────────────────────────
print("── 7. Config file check ────────────────────────────────")
for cfg in ["quantum_mode_config.json", "goose_quantum_profile.json",
            "data/quantum_dataset/portfolio_optimization_examples.json"]:
    p = Path(cfg)
    if p.exists():
        print(f"  ✅ {cfg} ({p.stat().st_size} bytes)")
    else:
        print(f"  ❌ MISSING: {cfg}")
print()

# ── 8. QIP process alive? ─────────────────────────────────────
print("── 8. Process check ────────────────────────────────────")
import subprocess
result = subprocess.run(
    ["pgrep", "-af", "quantum_mesh_consumer"],
    capture_output=True, text=True
)
if result.stdout.strip():
    print(f"  ✅ quantum_mesh_consumer process:")
    for line in result.stdout.strip().split("\n"):
        print(f"     {line}")
else:
    print(f"  ❌ quantum_mesh_consumer NOT running — start it:")
    print(f"     nohup python3.10 quantum_mesh_consumer.py > data/logs/goose/qip.log 2>&1 &")

result2 = subprocess.run(
    ["pgrep", "-af", "quantum_signal_bridge"],
    capture_output=True, text=True
)
if result2.stdout.strip():
    print(f"  ✅ quantum_signal_bridge running")
else:
    print(f"  ❌ quantum_signal_bridge NOT running")
print()

print("── 9. Last 30 lines of QIP log ─────────────────────────")
log_path = Path("data/logs/goose/qip.log")
if log_path.exists():
    lines = log_path.read_text().strip().split("\n")
    for line in lines[-30:]:
        print(f"  {line}")
else:
    print(f"  ❌ Log not found: {log_path}")
print()

print("=" * 60)
print("  Diagnostic complete. Fix items marked ❌ above.")
print("=" * 60)
