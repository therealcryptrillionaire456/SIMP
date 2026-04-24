#!/usr/bin/env python3.10
"""
diagnose_qip_pipeline.py
Deep diagnostic on why QIP has 0 intents_completed.
Traces the full intent request flow and identifies the break point.

Usage:
    cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"
    python3.10 diagnose_qip_pipeline.py
"""
import json, time, uuid, sys, os
from datetime import datetime, timezone
import requests

BROKER = "http://127.0.0.1:5555"

def h(label, val):
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    if isinstance(val, (dict, list)):
        print(json.dumps(val, indent=2, default=str))
    else:
        print(val)

def get(path, timeout=5):
    try:
        r = requests.get(f"{BROKER}{path}", timeout=timeout)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return 0, str(e)

def post(path, payload, timeout=10):
    try:
        r = requests.post(f"{BROKER}{path}", json=payload, timeout=timeout)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return 0, str(e)

print("═"*50)
print("  QIP PIPELINE DIAGNOSTIC")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("═"*50)

# ── 1. Broker health ──────────────────────────────────────
status, data = get("/health")
h("1. Broker health", data)

# ── 2. QIP agent state ────────────────────────────────────
status, agents = get("/agents")
qip = None
if isinstance(agents, dict):
    qip = agents.get("agents", {}).get("quantum_intelligence_prime") or \
          agents.get("quantum_intelligence_prime")
elif isinstance(agents, list):
    qip = next((a for a in agents if a.get("agent_id") == "quantum_intelligence_prime"), None)

h("2. QIP agent state", qip or "NOT FOUND IN ROSTER")
if qip:
    print(f"\n  intents_received:  {qip.get('intents_received', '?')}")
    print(f"  intents_completed: {qip.get('intents_completed', '?')}")
    print(f"  heartbeat_count:   {qip.get('heartbeat_count', '?')}")
    print(f"  status:            {qip.get('status', '?')}")

# ── 3. Check what channels exist ─────────────────────────
status, channels = get("/channels")
h("3. Available channels", channels)

# ── 4. Check what's queued in intent_requests channel ────
status, intent_q = get("/channels/intent_requests/messages")
h("4. intent_requests channel (pending messages)", intent_q)

# also try alternate paths
if status != 200:
    for path in ["/mesh/messages/intent_requests", "/mesh/channel/intent_requests"]:
        s2, d2 = get(path)
        if s2 == 200:
            h(f"4b. {path}", d2)
            break

# ── 5. Check quantum channel ──────────────────────────────
status, q_chan = get("/channels/quantum/messages")
h("5. quantum channel messages", q_chan)

# ── 6. Try a fresh intent directly to QIP ────────────────
test_id = f"diag_{uuid.uuid4().hex[:8]}"
intent_payload = {
    "message_id": test_id,
    "channel": "intent_requests",
    "sender": "kloutbot_diagnostic",
    "recipient": "quantum_intelligence_prime",
    "message_type": "intent_request",
    "payload": {
        "intent": "health_check",
        "query": "quantum health status check — respond with ok",
        "intent_id": test_id,
        "response_channel": "quantum_results",
        "timeout": 15,
    }
}
status, pub_resp = post("/mesh/publish", intent_payload)
h(f"6. Direct intent → QIP (id={test_id})", {"status": status, "response": pub_resp})

# ── 7. Wait and poll for response ────────────────────────
print(f"\n  Waiting 10s for QIP response...")
time.sleep(10)

# Check multiple possible response channels
for chan in ["quantum_results", "intent_responses", "kloutbot_results", "quantum"]:
    s, msgs = get(f"/channels/{chan}/messages")
    if s == 200 and msgs:
        h(f"7. Response in '{chan}' channel", msgs)
        break
    # also try subscribe endpoint
    s2, msgs2 = get(f"/mesh/subscribe/{chan}?agent_id=kloutbot_diagnostic")
    if s2 == 200 and msgs2:
        h(f"7. Response via subscribe '{chan}'", msgs2)
        break
else:
    print(f"\n  ⚠️  No response found in any channel after 10s")
    print(f"     Possible causes:")
    print(f"     a) QIP is receiving intents but response_channel is wrong")
    print(f"     b) QIP engine is in stub mode and returns nothing")
    print(f"     c) QIP polls a different endpoint than we're publishing to")

# ── 8. Check QIP's actual subscription / polling behavior ─
h("8. Checking QIP process details", "")
import subprocess
result = subprocess.run(
    "ps aux | grep quantum_intelligence | grep -v grep",
    shell=True, capture_output=True, text=True
)
print(result.stdout or "  (not found in ps)")

# Check the QIP log
for log_path in [
    "data/logs/goose/quantum_intelligence_prime.log",
    "data/logs/qip.log",
    "data/logs/goose/qip.log",
    "logs/qip.log",
]:
    if os.path.exists(log_path):
        result = subprocess.run(f"tail -30 {log_path}", shell=True, capture_output=True, text=True)
        h(f"8b. QIP log ({log_path})", result.stdout or "(empty)")
        break

# ── 9. What endpoint is QIP using to receive intents? ────
print(f"\n{'─'*50}")
print("  9. Checking QIP source for intent polling endpoint")
print(f"{'─'*50}")
for fname in ["quantum_intelligence_prime.py", "qip.py", "simp/agents/qip.py"]:
    if os.path.exists(fname):
        with open(fname) as f:
            content = f.read()
        # Find the subscribe/poll endpoint
        import re
        matches = re.findall(r'(subscribe|poll|intent|listen|channel)[^\n]*', content, re.IGNORECASE)
        for m in matches[:15]:
            print(f"  {m.strip()}")
        break

# ── 10. Summary ───────────────────────────────────────────
print(f"\n{'═'*50}")
print("  DIAGNOSIS SUMMARY")
print(f"{'═'*50}")
print("""
Check the output above for:
  • If 'intent_requests' channel has queued messages → QIP isn't consuming them
  • If QIP log shows timeout or error → engine issue
  • If test intent got no response → response_channel mismatch
  • If QIP process not in ps → it crashed

Run this after to see fresh agent stats:
  curl -s http://127.0.0.1:5555/agents | python3.10 -m json.tool | grep -A5 quantum_intelligence
""")
