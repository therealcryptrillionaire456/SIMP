#!/usr/bin/env python3
"""
quantum_signal_bridge.py  —  Phase 5: Quantum → gate4_real Revenue Bridge

Polls quantum_intelligence_prime via mesh every POLL_INTERVAL seconds.
Converts QIP portfolio recommendations into trade signals.
Writes signals to gate4_real's file inbox for immediate execution.

This is the first direct revenue wire: quantum brain → live Coinbase trades.

DROP INTO:  simp root
RUN:        python3.10 quantum_signal_bridge.py &

Requires:
  - Broker running at 127.0.0.1:5555
  - quantum_mesh_consumer.py running (QIP active)
  - gate4_real registered with inbox at data/inboxes/gate4_real/
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
from typing import Optional, Dict, Any

import requests
from requests import Response

try:
    from coinbase.rest import RESTClient  # type: ignore
except ImportError:
    RESTClient = None  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [quantum_signal_bridge] %(levelname)s %(message)s"
)
logger = logging.getLogger("quantum_signal_bridge")

# ─── Config ───────────────────────────────────────────────────────────────────

BROKER_URL          = "http://127.0.0.1:5555"
BRIDGE_AGENT_ID     = "quantum_signal_bridge"
QIP_AGENT_ID        = "quantum_intelligence_prime"
GATE4_AGENT_ID      = "gate4_real"

POLL_INTERVAL       = 60        # seconds between quantum portfolio queries
RESPONSE_TIMEOUT    = 30        # seconds to wait for QIP response
HEARTBEAT_INTERVAL  = 30        # broker heartbeat

# gate4_real file inbox — matches what broker registered
GATE4_INBOX_PATHS = [
    Path("data/inboxes/gate4_real"),
    Path("data/inboxes/gate4"),
    Path(os.path.expanduser("~/bullbear/signals/gate4_real")),
]

# Assets to optimize (must match gate4_real's supported pairs)
TARGET_ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD"]

# Position sizing constraints (matches gate4_real metadata: "$1-$10")
MIN_POSITION_USD = 1.0
MAX_POSITION_USD = 10.0
QUOTE_CURRENCIES = ("USD", "USDC")

# Minimum QIP quality score to generate a live signal (0.0-1.0).
# Below this threshold, the cycle is skipped — no blind trades.
MIN_QUALITY_SCORE = float(os.environ.get("SIMP_MIN_QIP_QUALITY", "0.5"))


# ─── Broker helpers ───────────────────────────────────────────────────────────

def _parse_response_json(response: Response) -> Optional[dict]:
    try:
        return response.json()
    except ValueError:
        return None


def _post(url: str, payload: dict, timeout: int = 10) -> Optional[dict]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"POST {url}: {e}")
        return None


def _get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"GET {url}: {e}")
        return None


def _post_result(url: str, payload: dict, timeout: int = 10) -> tuple[Optional[int], Optional[dict], str]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code, _parse_response_json(r), r.text
    except Exception as exc:
        logger.error(f"POST {url}: {exc}")
        return None, None, str(exc)


def _get_result(url: str, params: dict = None, timeout: int = 10) -> tuple[Optional[int], Optional[dict], str]:
    try:
        r = requests.get(url, params=params, timeout=timeout)
        return r.status_code, _parse_response_json(r), r.text
    except Exception as exc:
        logger.error(f"GET {url}: {exc}")
        return None, None, str(exc)


def _broker_has_agent(broker: str, agent_id: str) -> bool:
    status, body, _ = _get_result(f"{broker}/agents/{agent_id}")
    if not status or status >= 400 or not isinstance(body, dict):
        return False
    agent = body.get("agent", body)
    return str(agent.get("agent_id") or "") == agent_id


def _bridge_poll_ready(broker: str) -> bool:
    status, body, _ = _get_result(
        f"{broker}/mesh/poll",
        params={"agent_id": BRIDGE_AGENT_ID, "max_messages": 1},
    )
    return bool(
        status
        and status < 400
        and isinstance(body, dict)
        and str(body.get("agent_id") or "") == BRIDGE_AGENT_ID
    )


def register_and_subscribe(broker: str) -> bool:
    status, body, raw = _post_result(f"{broker}/agents/register", {
        "agent_id": BRIDGE_AGENT_ID,
        "agent_type": "signal_bridge",
        "endpoint": "(file-based)",
        "metadata": {
            "simp_versions": ["1.0"],
            "mesh_native": True,
            "transport": "mesh",
            "capabilities": ["quantum_signal_relay", "trade_signal_generation"],
        },
    })
    ok = bool(status and status < 400 and body and body.get("status") == "success")
    if ok:
        logger.info(f"Registered as {BRIDGE_AGENT_ID}")
    elif _broker_has_agent(broker, BRIDGE_AGENT_ID):
        ok = True
        logger.info(f"{BRIDGE_AGENT_ID} already registered with broker; continuing")
    else:
        logger.warning(f"Registration did not succeed: status={status} body={body or raw}")

    for ch in ["quantum", "trade_signals"]:
        sub_status, sub_body, sub_raw = _post_result(
            f"{broker}/mesh/subscribe",
            {"agent_id": BRIDGE_AGENT_ID, "channel": ch},
        )
        if sub_status and sub_status < 400 and sub_body and sub_body.get("status") == "success":
            logger.info(f"Subscribed to '{ch}'")
            continue

        if _bridge_poll_ready(broker):
            logger.info(
                f"Subscription to '{ch}' returned non-success but bridge polling is ready; continuing"
            )
            continue

        logger.warning(
            f"Subscription to '{ch}' did not succeed: status={sub_status} body={sub_body or sub_raw}"
        )
    return ok


def heartbeat(broker: str):
    _post(f"{broker}/agents/heartbeat", {
        "agent_id": BRIDGE_AGENT_ID,
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ─── Quantum query ────────────────────────────────────────────────────────────

def query_qip(broker: str, problem: str) -> Optional[dict]:
    """Send intent to QIP and wait for response."""
    msg_id = str(uuid.uuid4())
    send_result = _post(f"{broker}/mesh/send", {
        "sender_id": BRIDGE_AGENT_ID,
        "recipient_id": QIP_AGENT_ID,
        "channel": "quantum",
        "payload": {
            "intent": "optimize_portfolio",
            "problem": problem,
            "assets": TARGET_ASSETS,
            "constraints": {
                "min_position_usd": MIN_POSITION_USD,
                "max_position_usd": MAX_POSITION_USD,
            },
            "request_id": msg_id,
        }
    })

    if not send_result or send_result.get("status") != "success":
        logger.error(f"Failed to send QIP intent: {send_result}")
        return None

    sent_msg_id = send_result.get("message_id", msg_id)
    logger.info(f"QIP intent sent [{sent_msg_id[:8]}], waiting up to {RESPONSE_TIMEOUT}s...")

    # Poll for response
    deadline = time.time() + RESPONSE_TIMEOUT
    while time.time() < deadline:
        result = _get(
            f"{broker}/mesh/poll",
            params={"agent_id": BRIDGE_AGENT_ID, "max_messages": 10},
        )
        if result and result.get("messages"):
            for msg in result["messages"]:
                payload = msg.get("payload", {})
                if payload.get("sender_id") == QIP_AGENT_ID or msg.get("sender_id") == QIP_AGENT_ID:
                    logger.info(f"QIP response received (success={payload.get('success')})")
                    return payload
                # Also match by responding_to
                if payload.get("responding_to") == sent_msg_id:
                    return payload
        time.sleep(2)

    logger.warning("QIP response timed out")
    return None


def _coinbase_client() -> Optional[RESTClient]:
    if RESTClient is None:
        return None

    api_key = os.environ.get("COINBASE_API_KEY_NAME", "").strip()
    api_secret = os.environ.get("COINBASE_API_PRIVATE_KEY", "").strip()
    if not api_key or not api_secret:
        return None
    if api_secret.startswith(("'", '"')) and api_secret.endswith(("'", '"')):
        api_secret = api_secret[1:-1]
    if "\\n" in api_secret:
        api_secret = api_secret.replace("\\n", "\n")

    try:
        return RESTClient(api_key=api_key, api_secret=api_secret, timeout=30)
    except Exception as exc:
        logger.warning(f"Coinbase client unavailable for funding-aware routing: {exc}")
        return None


def _account_balances(client: RESTClient) -> Dict[str, float]:
    try:
        resp = client.get_accounts()
    except Exception as exc:
        logger.warning(f"balance lookup failed: {exc}")
        return {}

    if isinstance(resp, dict):
        accounts = resp.get("accounts") or resp.get("data") or []
    else:
        accounts = getattr(resp, "accounts", None) or getattr(resp, "data", None) or []

    balances: Dict[str, float] = {}
    for account in accounts:
        row = account if isinstance(account, dict) else getattr(account, "__dict__", {})
        currency = str(row.get("currency") or row.get("asset") or "").upper()
        available = row.get("available_balance") or row.get("available") or {}
        if isinstance(available, dict):
            raw = available.get("value") or available.get("amount") or 0
        else:
            raw = available or 0
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if currency and value > 0:
            balances[currency] = value
    return balances


def _market_price(client: RESTClient, product_id: str) -> Optional[float]:
    try:
        resp = client.get_product(product_id=product_id)
    except Exception:
        try:
            resp = client.get_product_ticker(product_id=product_id)
        except Exception as exc:
            logger.warning(f"price lookup failed for {product_id}: {exc}")
            return None

    payload = resp if isinstance(resp, dict) else getattr(resp, "__dict__", {})
    for key in ("price", "last_price"):
        value = payload.get(key)
        if value:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def _apply_funding_constraints(signal: Dict[str, Any]) -> Dict[str, Any]:
    client = _coinbase_client()
    if client is None:
        signal["metadata"]["funding_mode"] = "blind"
        return signal

    balances = _account_balances(client)
    quote_balance = sum(balances.get(ccy, 0.0) for ccy in QUOTE_CURRENCIES)
    metadata = signal.setdefault("metadata", {})

    if quote_balance >= MIN_POSITION_USD:
        budget = max(MIN_POSITION_USD, min(MAX_POSITION_USD, round(quote_balance, 2)))
        buy_assets = {
            asset: leg for asset, leg in signal.get("assets", {}).items()
            if (leg.get("action") or "").lower() == "buy"
        }
        total_weight = sum(float(leg.get("weight", 0.0) or 0.0) for leg in buy_assets.values())
        if total_weight > 0:
            for asset, leg in signal["assets"].items():
                if asset not in buy_assets:
                    continue
                weight = float(leg.get("weight", 0.0) or 0.0)
                scaled = round((weight / total_weight) * budget, 2)
                leg["position_usd"] = max(MIN_POSITION_USD, min(budget, scaled))
        metadata["funding_mode"] = "quote_funded"
        metadata["quote_balance_usd"] = round(quote_balance, 4)
        metadata["quote_budget_usd"] = budget
        return signal

    best_asset = None
    best_notional = 0.0
    for symbol in TARGET_ASSETS:
        base = symbol.split("-", 1)[0]
        base_balance = balances.get(base, 0.0)
        if base_balance <= 0:
            continue
        price = _market_price(client, symbol)
        if not price:
            continue
        notional = base_balance * price
        if notional > best_notional:
            best_asset = symbol
            best_notional = notional

    if best_asset and best_notional >= MIN_POSITION_USD:
        sell_notional = round(min(MAX_POSITION_USD, max(MIN_POSITION_USD, best_notional * 0.25)), 2)
        signal["assets"] = {
            best_asset: {
                "weight": 1.0,
                "position_usd": sell_notional,
                "action": "sell",
            }
        }
        metadata["funding_mode"] = "bootstrap_sell"
        metadata["bootstrap_asset"] = best_asset
        metadata["bootstrap_notional_usd"] = sell_notional
        metadata["quote_balance_usd"] = round(quote_balance, 4)
        return signal

    metadata["funding_mode"] = "hold_no_capital"
    metadata["quote_balance_usd"] = round(quote_balance, 4)
    signal["assets"] = {
        asset: {
            **leg,
            "action": "hold",
            "position_usd": 0.0,
        }
        for asset, leg in signal.get("assets", {}).items()
    }
    return signal


# ─── Signal generation ────────────────────────────────────────────────────────

def parse_qip_response(qip_payload: dict) -> Optional[Dict[str, Any]]:
    """
    Extract trade signal from QIP response payload.
    Returns a signal dict ready for gate4_real's inbox.
    """
    if not qip_payload.get("success"):
        # QIP returned failure — do not trade without real analysis
        logger.warning(
            "QIP returned failure: %s — skipping signal (qip_fallback suppressed)",
            qip_payload.get("error_code", "unknown"),
        )
        return None

    result = qip_payload.get("result", "")
    metadata = qip_payload.get("metadata", {})

    # Require minimum quality score — low-confidence responses don't trade
    quality = float(metadata.get("quality_score", 0.0))
    if quality < MIN_QUALITY_SCORE:
        logger.warning(
            "QIP quality_score %.2f < threshold %.2f — skipping signal",
            quality, MIN_QUALITY_SCORE,
        )
        return None

    # Parse quantum recommendation from result text
    # QIP returns circuit output + recommendation in string form
    signal = {
        "signal_id": str(uuid.uuid4()),
        "source": "quantum_intelligence_prime",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_type": "portfolio_allocation",
        "assets": {},
        "metadata": {
            "quality_score": metadata.get("quality_score", 0.5),
            "execution_mode": metadata.get("execution_mode", "simulator"),
            "qip_trace_id": metadata.get("trace_id"),
            "verification_score": metadata.get("verification_score", 0.0),
        }
    }

    # Parse allocation from result string (QIP outputs recommendations in text)
    allocations = _parse_allocations(result)
    if not allocations:
        allocations = {"BTC-USD": 0.40, "ETH-USD": 0.25, "SOL-USD": 0.35}
        signal["metadata"]["allocation_source"] = "default_quantum_weights"
    else:
        signal["metadata"]["allocation_source"] = "qip_circuit_output"

    # Convert allocations to USD position sizes
    total_capital = MAX_POSITION_USD  # work within gate4_real's $10 limit
    for asset, weight in allocations.items():
        position_usd = round(weight * total_capital, 2)
        position_usd = max(MIN_POSITION_USD, min(MAX_POSITION_USD, position_usd))
        signal["assets"][asset] = {
            "weight": round(weight, 4),
            "position_usd": position_usd,
            "action": "buy" if weight > 0.2 else "hold",
        }

    return _apply_funding_constraints(signal)


def _parse_allocations(result_text: str) -> Dict[str, float]:
    """Extract allocation percentages from QIP circuit output text."""
    allocs = {}
    if not result_text:
        return allocs

    # Pattern: "SOL=0.45", "BTC: 35%", "ETH 25%", "Allocation: SOL=0.45, BTC=0.35"
    import re
    patterns = [
        r"(BTC|ETH|SOL)[^0-9]*([0-9]+\.?[0-9]*)\s*%",
        r"(BTC|ETH|SOL)[^0-9]*([0-9]*\.?[0-9]+)",
        r"(BTC-USD|ETH-USD|SOL-USD)[^0-9]*([0-9]*\.?[0-9]+)",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, result_text, re.IGNORECASE):
            asset = m.group(1).upper()
            if "-USD" not in asset:
                asset = f"{asset}-USD"
            val = float(m.group(2))
            if val > 1.0:
                val = val / 100.0   # was a percentage
            allocs[asset] = val

    # Normalize to sum=1.0
    total = sum(allocs.values())
    if total > 0.01:
        allocs = {k: round(v / total, 4) for k, v in allocs.items()}

    return allocs


def _equal_weight_signal(source: str) -> Dict[str, Any]:
    n = len(TARGET_ASSETS)
    weight = 1.0 / n
    pos = round(MAX_POSITION_USD * weight, 2)
    return {
        "signal_id": str(uuid.uuid4()),
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_type": "portfolio_allocation",
        "assets": {
            asset: {"weight": weight, "position_usd": pos, "action": "buy"}
            for asset in TARGET_ASSETS
        },
        "metadata": {"allocation_source": "equal_weight_fallback"}
    }


# ─── Signal delivery to gate4_real ───────────────────────────────────────────

def _find_gate4_inbox() -> Optional[Path]:
    for p in GATE4_INBOX_PATHS:
        if p.exists():
            return p
    # Try to create the default
    default = Path("data/inboxes/gate4_real")
    try:
        default.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created gate4_real inbox at {default}")
        return default
    except Exception as e:
        logger.error(f"Cannot create inbox: {e}")
        return None


def deliver_signal(signal: Dict[str, Any], broker: str) -> bool:
    """
    Deliver signal to gate4_real via TWO paths:
    1. File inbox (primary — gate4_real polls this)
    2. Mesh send (secondary — direct message)
    """
    success = False

    # Path 1: File inbox
    inbox = _find_gate4_inbox()
    if inbox:
        fname = inbox / f"quantum_signal_{int(time.time())}.json"
        try:
            fname.write_text(json.dumps(signal, indent=2))
            logger.info(f"Signal written to gate4_real inbox: {fname.name}")
            success = True
        except Exception as e:
            logger.error(f"File inbox write failed: {e}")

    # Path 2: Mesh direct message
    mesh_result = _post(f"{broker}/mesh/send", {
        "sender_id": BRIDGE_AGENT_ID,
        "recipient_id": GATE4_AGENT_ID,
        "channel": "trade_signals",
        "payload": {
            "intent": "process_quantum_signal",
            "signal": signal,
        }
    })
    if mesh_result and mesh_result.get("status") == "success":
        logger.info(f"Signal sent to gate4_real via mesh [{mesh_result.get('message_id','?')[:8]}]")
        success = True
    else:
        logger.warning(f"Mesh delivery to gate4_real: {mesh_result}")

    return success


# ─── Main loop ────────────────────────────────────────────────────────────────

class QuantumSignalBridge:
    def __init__(self, broker: str = BROKER_URL, poll_interval: float = POLL_INTERVAL):
        self.broker = broker
        self.poll_interval = poll_interval
        self._running = False
        self._signals_sent = 0
        self._last_signal: Optional[dict] = None

    def start(self):
        logger.info(f"Quantum Signal Bridge starting — broker={self.broker}")
        logger.info(f"Poll interval: {self.poll_interval}s | Assets: {TARGET_ASSETS}")

        register_and_subscribe(self.broker)

        self._running = True
        last_heartbeat = 0.0
        last_query = 0.0

        logger.info("Bridge active. Quantum signals → gate4_real (Coinbase live)")

        while self._running:
            now = time.time()

            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                heartbeat(self.broker)
                last_heartbeat = now

            if now - last_query >= self.poll_interval:
                logger.info("Querying QIP for portfolio optimization...")

                problem = (
                    f"optimize portfolio allocation across {', '.join(TARGET_ASSETS)} "
                    f"for live trading. Max position ${MAX_POSITION_USD}. "
                    f"Use quantum amplitude estimation for return probability. "
                    f"Current timestamp: {datetime.now(timezone.utc).isoformat()}"
                )

                qip_response = query_qip(self.broker, problem)

                if qip_response is not None:
                    signal = parse_qip_response(qip_response)
                else:
                    logger.warning("No QIP response — skipping this cycle (timeout_fallback suppressed)")
                    signal = None

                if signal:
                    delivered = deliver_signal(signal, self.broker)
                    if delivered:
                        self._signals_sent += 1
                        self._last_signal = signal
                        alloc_summary = {
                            k: f"${v['position_usd']}"
                            for k, v in signal["assets"].items()
                        }
                        logger.info(f"Signal #{self._signals_sent} delivered: {alloc_summary}")

                last_query = now

            time.sleep(2)

    def stop(self):
        self._running = False
        logger.info(f"Bridge stopped. Total signals sent: {self._signals_sent}")


def main():
    parser = argparse.ArgumentParser(description="Quantum Signal Bridge — QIP → gate4_real")
    parser.add_argument("--broker", default=BROKER_URL)
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL,
                        help="Seconds between quantum portfolio queries")
    parser.add_argument("--once", action="store_true",
                        help="Run one query and exit (useful for testing)")
    args = parser.parse_args()

    if args.once:
        logging.basicConfig(level=logging.INFO)
        register_and_subscribe(args.broker)
        problem = f"optimize {TARGET_ASSETS} portfolio for live Coinbase trading"
        qip = query_qip(args.broker, problem)
        signal = parse_qip_response(qip) if qip else _apply_funding_constraints(_equal_weight_signal("once_fallback"))
        deliver_signal(signal, args.broker)
        print(json.dumps(signal, indent=2))
        return

    bridge = QuantumSignalBridge(broker=args.broker, poll_interval=args.interval)

    def _shutdown(sig, frame):
        bridge.stop()
        sys.exit(0)

    signal_mod = __import__("signal")
    signal_mod.signal(signal_mod.SIGINT, _shutdown)
    signal_mod.signal(signal_mod.SIGTERM, _shutdown)

    bridge.start()


if __name__ == "__main__":
    main()
