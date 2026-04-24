#!/usr/bin/env python3.10
"""
fix_qip_mesh_registration.py

Fixes the "0 mesh agents" problem.

The issue: QIP registers with /agents/register (broker's agent table)
but the mesh ROUTING table is separate. The routing layer only knows
about agents that have explicitly announced capabilities via the
mesh routing discovery endpoint.

This script force-registers QIP into the mesh routing table.

Run once, then restart quantum_mesh_consumer.py.
"""

import json
import requests
import sys

BROKER_URL = "http://127.0.0.1:5555"
QIP_ID     = "quantum_intelligence_prime"

CAPABILITIES = [
    "solve_quantum_problem",
    "optimize_portfolio",
    "evolve_quantum_skills",
    "health_check",
    "get_deployment_status",
]

print("Fixing QIP mesh routing registration...")
print()

# ── Try every known registration path ────────────────────────
endpoints_to_try = [
    # Standard mesh routing agent announcement
    ("/mesh/routing/register", {
        "agent_id":     QIP_ID,
        "capabilities": CAPABILITIES,
        "channels":     ["quantum", "intent_requests"],
    }),
    # Some SIMP versions use /mesh/routing/agents for POST
    ("/mesh/routing/agents", {
        "agent_id":     QIP_ID,
        "capabilities": CAPABILITIES,
    }),
    # Discovery announcement
    ("/mesh/routing/discover", {
        "agent_id":     QIP_ID,
        "capabilities": CAPABILITIES,
        "mode":         "announce",
    }),
    # Capability announcement
    ("/mesh/routing/announce", {
        "agent_id":     QIP_ID,
        "capabilities": CAPABILITIES,
        "channels":     ["quantum", "intent_requests"],
    }),
    # Generic agent update
    (f"/mesh/routing/agent/{QIP_ID}", {
        "capabilities": CAPABILITIES,
        "status":       "online",
    }),
]

success = False
for path, payload in endpoints_to_try:
    try:
        r = requests.post(f"{BROKER_URL}{path}", json=payload, timeout=5)
        if r.status_code < 400:
            print(f"✅ {path} → {r.status_code}: {r.text[:200]}")
            success = True
        else:
            print(f"⚠️  {path} → {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"⚠️  {path} → error: {e}")

print()

# ── Also set mesh mode to PREFERRED (not FALLBACK) ────────────
print("Setting mesh routing mode to PREFERRED...")
r = requests.post(f"{BROKER_URL}/mesh/routing/config",
                  json={"mode": "preferred"}, timeout=5)
print(f"  → {r.status_code}: {r.text[:200]}")
print()

# ── Verify routing table now ──────────────────────────────────
print("Verifying mesh routing agents:")
r = requests.get(f"{BROKER_URL}/mesh/routing/agents", timeout=5)
print(json.dumps(r.json(), indent=2)[:800])
print()

# ── Verify routing status ─────────────────────────────────────
print("Mesh routing status:")
r = requests.get(f"{BROKER_URL}/mesh/routing/status", timeout=5)
print(json.dumps(r.json(), indent=2)[:400])

print()
if success:
    print("✅ Registration attempted. Restart quantum_mesh_consumer.py to re-subscribe.")
    print("   kill $(pgrep -f quantum_mesh_consumer) && nohup python3.10 quantum_mesh_consumer.py > data/logs/goose/qip.log 2>&1 &")
else:
    print("⚠️  No registration endpoint worked.")
    print("   The mesh routing table may be populated automatically on subscribe.")
    print("   Check: curl -s http://127.0.0.1:5555/mesh/routing/agents | python3 -m json.tool")
