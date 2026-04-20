#!/usr/bin/env python3.10
"""
quantumarb_mesh_consumer.py  — Phase 6
Quantum signal path for quantumarb_real.

Bridges QIP → quantumarb_real inbox, parallel to the
gate4_real signal bridge. Asks QIP for arb opportunities
(not portfolio allocation) and delivers actionable signals.

Deploy: python3.10 quantumarb_mesh_consumer.py
Logs:   data/logs/goose/quantumarb_consumer.log
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
BROKER_URL    = "http://127.0.0.1:5555"
AGENT_ID      = "quantumarb_mesh_consumer"
AGENT_NAME    = "QuantumArb Mesh Consumer"
QIP_ID        = "quantum_intelligence_prime"
ARB_INBOX     = Path("data/inboxes/quantumarb_real")
LOG_DIR       = Path("data/logs/goose")
POLL_EVERY    = 45   # seconds — arb windows are shorter than portfolio
HEARTBEAT_EVERY = 30

ARB_PAIRS = [
    ("BTC-USD", "ETH-USD"),
    ("ETH-USD", "SOL-USD"),
    ("BTC-USD", "SOL-USD"),
]

ARB_INBOX.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [QARB] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "quantumarb_consumer.log"),
    ],
)
log = logging.getLogger("quantumarb_consumer")


# ── Broker helpers ────────────────────────────────────────────────────────────

def _post(path, payload):
    try:
        r = requests.post(f"{BROKER_URL}{path}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"POST {path}: {e}")
        return None


def _setup():
    _post("/agents/register", {
        "agent_id":     AGENT_ID,
        "name":         AGENT_NAME,
        "version":      "1.0.0",
        "capabilities": ["receive_arb_signal", "forward_to_quantumarb"],
    })
    _post("/mesh/subscribe", {"agent_id": AGENT_ID, "channel": "quantum"})
    _post("/mesh/subscribe", {"agent_id": AGENT_ID, "channel": "arb_signals"})
    log.info("Registered and subscribed.")


def _heartbeat():
    _post("/agents/heartbeat", {"agent_id": AGENT_ID, "status": "online"})


# ── QIP arb query ─────────────────────────────────────────────────────────────

ARB_PROMPT_TEMPLATE = """
Use Grover's search algorithm to identify arbitrage opportunities across these pairs:
{pairs}

For each pair, determine:
1. Current spread direction (which leg is over/underpriced)
2. Estimated profit window (seconds)
3. Confidence level (0-1)
4. Recommended action: buy_A_sell_B or buy_B_sell_A or skip

Return JSON array:
[{{"pair": "A-B", "action": "buy_A_sell_B", "spread_pct": 0.003, "confidence": 0.85, "window_seconds": 30}}]
"""


def query_qip_for_arb() -> dict | None:
    pairs_str = "\n".join(f"  - {a} vs {b}" for a, b in ARB_PAIRS)
    problem   = ARB_PROMPT_TEMPLATE.format(pairs=pairs_str)
    msg_id    = str(uuid.uuid4())

    _post("/mesh/send", {
        "sender_id":    AGENT_ID,
        "recipient_id": QIP_ID,
        "channel":      "quantum",
        "payload": {
            "intent":  "solve_quantum_problem",
            "problem": problem,
            "msg_id":  msg_id,
            "context": "arbitrage_detection",
        },
    })

    log.info(f"Sent arb query to QIP (msg_id={msg_id}). Waiting...")

    for _ in range(10):
        time.sleep(3)
        try:
            poll = requests.get(
                f"{BROKER_URL}/mesh/poll",
                params={"agent_id": AGENT_ID, "max_messages": 10},
                timeout=15,
            )
            poll.raise_for_status()
            payload = poll.json()
        except Exception as exc:
            log.warning(f"GET /mesh/poll: {exc}")
            continue

        if isinstance(payload.get("messages"), list):
            for msg in payload["messages"]:
                p = msg.get("payload", {})
                if "result" in p or "error" in p:
                    log.info("QIP arb response received.")
                    return p

    log.warning("QIP arb response timeout — using statistical fallback.")
    return None


# ── Signal parser ─────────────────────────────────────────────────────────────

DEFAULT_ARB_SIGNALS = [
    {"pair": "BTC-USD/ETH-USD", "action": "monitor", "spread_pct": 0.0, "confidence": 0.5, "window_seconds": 0},
]


def parse_arb_signals(qip_response: dict | None) -> list[dict]:
    if not qip_response:
        return DEFAULT_ARB_SIGNALS

    result_str = str(qip_response.get("result", ""))

    # Try JSON array extraction
    array_match = re.search(r'\[.*?\]', result_str, re.DOTALL)
    if array_match:
        try:
            signals = json.loads(array_match.group())
            if isinstance(signals, list) and signals:
                log.info(f"Parsed {len(signals)} quantum arb signals.")
                return signals
        except Exception:
            pass

    # Single object fallback
    obj_match = re.search(r'\{.*?\}', result_str, re.DOTALL)
    if obj_match:
        try:
            signal = json.loads(obj_match.group())
            return [signal]
        except Exception:
            pass

    # Regex key extraction
    signals = []
    for pair_a, pair_b in ARB_PAIRS:
        pair_key = f"{pair_a}/{pair_b}"
        spread_m = re.search(rf"{re.escape(pair_a)}.*?spread.*?([0-9.]+)", result_str, re.IGNORECASE)
        conf_m   = re.search(rf"{re.escape(pair_a)}.*?confidence.*?([0-9.]+)", result_str, re.IGNORECASE)
        if spread_m:
            signals.append({
                "pair":           pair_key,
                "action":         "buy_A_sell_B",
                "spread_pct":     float(spread_m.group(1)),
                "confidence":     float(conf_m.group(1)) if conf_m else 0.5,
                "window_seconds": 30,
            })

    return signals if signals else DEFAULT_ARB_SIGNALS


# ── Signal delivery ───────────────────────────────────────────────────────────

MIN_CONFIDENCE = 0.65  # only deliver high-confidence signals
MIN_SPREAD_PCT  = 0.001  # ignore sub-0.1% spreads


def deliver_arb_signals(signals: list[dict], qip_raw: dict | None):
    actionable = [
        s for s in signals
        if s.get("confidence", 0) >= MIN_CONFIDENCE
        and s.get("spread_pct", 0) >= MIN_SPREAD_PCT
        and s.get("action", "skip") not in ("skip", "monitor")
    ]

    if not actionable:
        log.info(f"No actionable arb signals above thresholds "
                 f"(confidence>={MIN_CONFIDENCE}, spread>={MIN_SPREAD_PCT}). "
                 f"Received {len(signals)} signals total.")
        return

    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"quantum_arb_{ts}.json"
    path     = ARB_INBOX / filename

    envelope = {
        "signal_id":     str(uuid.uuid4()),
        "source":        "quantum_intelligence_prime",
        "signal_type":   "arbitrage",
        "timestamp":     datetime.utcnow().isoformat() + "Z",
        "signals":       actionable,
        "total_signals": len(signals),
        "qip_response":  qip_raw,
    }

    path.write_text(json.dumps(envelope, indent=2))
    log.info(f"Delivered {len(actionable)} arb signals → {path}")

    # Mesh notification
    _post("/mesh/send", {
        "sender_id": AGENT_ID,
        "channel":   "arb_signals",
        "payload": {
            "event":        "new_arb_signal",
            "signal_id":    envelope["signal_id"],
            "signal_count": len(actionable),
            "timestamp":    envelope["timestamp"],
        },
    })

    # Cross-notify gate4 so both agents can coordinate
    _post("/mesh/send", {
        "sender_id":    AGENT_ID,
        "recipient_id": "gate4_real",
        "channel":      "quantum_signals",
        "payload": {
            "event":     "arb_opportunity",
            "signal_id": envelope["signal_id"],
            "signals":   actionable,
        },
    })

    return envelope


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_continuous():
    _setup()
    last_heartbeat = 0
    last_query     = 0
    signals_sent   = 0

    log.info(f"QuantumArb mesh consumer running. Querying QIP every {POLL_EVERY}s.")

    while True:
        try:
            now = time.time()

            if now - last_heartbeat >= HEARTBEAT_EVERY:
                _heartbeat()
                last_heartbeat = now

            if now - last_query >= POLL_EVERY:
                log.info(f"Querying QIP for arb opportunities (cycle #{signals_sent + 1})...")
                qip_raw  = query_qip_for_arb()
                signals  = parse_arb_signals(qip_raw)
                result   = deliver_arb_signals(signals, qip_raw)
                if result:
                    signals_sent += 1
                last_query = now

            time.sleep(5)

        except KeyboardInterrupt:
            log.info(f"QuantumArb consumer stopped. Total delivered: {signals_sent}")
            break
        except Exception as e:
            log.error(f"Consumer error: {e}")
            time.sleep(15)


def run_once():
    _setup()
    qip_raw = query_qip_for_arb()
    signals = parse_arb_signals(qip_raw)
    result  = deliver_arb_signals(signals, qip_raw)
    print(json.dumps(result or {"status": "no actionable signals", "signals": signals}, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        run_once()
    else:
        run_continuous()
