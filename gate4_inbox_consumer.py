#!/usr/bin/env python3.10
"""
gate4_inbox_consumer.py
-----------------------
Reads quantum_signal_*.json files from data/inboxes/gate4_real/
and places real Coinbase Advanced Trade market orders.

Respects config/gate4_scaled_microscopic_live.json for:
  - API credentials
  - position sizing (min/max notional)
  - circuit breakers (max hourly/daily trades, max consecutive losses)
  - trading hours

Files are moved to _processed/ on success, _failed/ on error,
so nothing is ever double-traded.

Usage:
    python3.10 gate4_inbox_consumer.py              # live
    python3.10 gate4_inbox_consumer.py --dry-run    # log only, no orders
    python3.10 gate4_inbox_consumer.py --once       # drain inbox once and exit
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- Coinbase SDK -----------------------------------------------------------
# We prefer the official coinbase-advanced-py SDK. It's pure-python and
# handles CDP JWT auth for us.
try:
    from coinbase.rest import RESTClient  # type: ignore
except ImportError:
    print(
        "[fatal] coinbase-advanced-py is not installed in this venv.\n"
        "        Install it with:\n"
        "        ./venv_gate4/bin/pip install coinbase-advanced-py\n",
        file=sys.stderr,
    )
    sys.exit(2)

# --- paths ------------------------------------------------------------------
REPO = Path(__file__).resolve().parent
INBOX = REPO / "data" / "inboxes" / "gate4_real"
PROCESSED = INBOX / "_processed"
FAILED = INBOX / "_failed"
STATE_FILE = REPO / "data" / "gate4_consumer_state.json"
LOG_DIR = REPO / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_LOG = LOG_DIR / "gate4_trades.jsonl"
CONFIG_PATH = REPO / "config" / "live_production_config.json"

# --- logging ----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [gate4] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "gate4_consumer.log"),
    ],
)
log = logging.getLogger("gate4")

# --- helpers ----------------------------------------------------------------
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        log.error("config not found: %s", CONFIG_PATH)
        sys.exit(2)
    with CONFIG_PATH.open() as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            log.warning("state file corrupt, starting fresh")
    return {
        "trades_today": [],            # list of ISO timestamps (UTC)
        "trades_this_hour": [],        # list of ISO timestamps (UTC)
        "consecutive_losses": 0,
        "last_trade_at": None,
        "cooldown_until": None,
    }


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def prune_timestamps(state: dict) -> None:
    """Drop trade timestamps older than 1h / 1d."""
    now = datetime.now(timezone.utc)
    state["trades_this_hour"] = [
        t for t in state["trades_this_hour"]
        if (now - datetime.fromisoformat(t)).total_seconds() < 3600
    ]
    state["trades_today"] = [
        t for t in state["trades_today"]
        if (now - datetime.fromisoformat(t)).total_seconds() < 86400
    ]


def circuit_breakers_open(state: dict, cfg: dict) -> tuple[bool, str]:
    """Return (tripped, reason)."""
    cb = cfg["risk_management"]["circuit_breakers"]
    prune_timestamps(state)

    if state.get("cooldown_until"):
        cd = datetime.fromisoformat(state["cooldown_until"])
        if datetime.now(timezone.utc) < cd:
            return True, f"cooldown active until {cd.isoformat()}"
        state["cooldown_until"] = None

    if len(state["trades_this_hour"]) >= cb["max_hourly_trades"]:
        return True, f"hourly trade cap hit ({cb['max_hourly_trades']})"
    if len(state["trades_today"]) >= cb["max_daily_trades"]:
        return True, f"daily trade cap hit ({cb['max_daily_trades']})"
    if state["consecutive_losses"] >= cb["max_consecutive_losses"]:
        # trigger cooldown
        cd = datetime.now(timezone.utc).timestamp() + cb["cool_down_minutes"] * 60
        state["cooldown_until"] = datetime.fromtimestamp(cd, timezone.utc).isoformat()
        return True, f"{cb['max_consecutive_losses']} consecutive losses — cooldown {cb['cool_down_minutes']}m"
    return False, ""


def is_trading_hours(cfg: dict) -> bool:
    th = cfg.get("trading_hours", {})
    days = {d.lower() for d in th.get("days_active", [])}
    now = datetime.now(timezone.utc)
    if days and now.strftime("%A").lower() not in days:
        return False
    start = th.get("start_time_utc", "00:00")
    end = th.get("end_time_utc", "23:59")
    cur = now.strftime("%H:%M")
    return start <= cur <= end


def build_client(cfg: dict) -> RESTClient:
    ex = cfg["exchange_config"]
    # coinbase-advanced-py accepts CDP keys directly.
    # Use environment variable substitution for security
    api_key_name = os.path.expandvars(ex["api_key_name"])
    api_secret = os.path.expandvars(ex["api_secret"]).strip()
    if api_secret.startswith(("'", '"')) and api_secret.endswith(("'", '"')):
        api_secret = api_secret[1:-1]
    if "\\n" in api_secret:
        api_secret = api_secret.replace("\\n", "\n")

    return RESTClient(
        api_key=api_key_name,  # the organizations/.../apiKeys/... name
        api_secret=api_secret,  # the PEM private key
        timeout=ex.get("timeout_seconds", 30),
    )


def _response_records(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, dict):
        records = resp.get("accounts") or resp.get("data") or []
    else:
        records = getattr(resp, "accounts", None) or getattr(resp, "data", None) or []
    normalized: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append(vars(item))
    return normalized


def _available_balance(client: RESTClient, currency: str) -> float:
    try:
        records = _response_records(client.get_accounts())
    except Exception as exc:
        log.warning("balance lookup failed for %s: %s", currency, exc)
        return 0.0

    for record in records:
        asset = str(record.get("currency") or record.get("asset") or "").upper()
        if asset != currency.upper():
            continue
        balance = record.get("available_balance") or record.get("available") or {}
        if isinstance(balance, dict):
            raw = balance.get("value") or balance.get("amount") or 0
        else:
            raw = balance or 0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _market_price(client: RESTClient, product_id: str) -> float:
    try:
        resp = client.get_product(product_id=product_id)
    except Exception:
        resp = client.get_product_ticker(product_id=product_id)

    payload = resp if isinstance(resp, dict) else vars(resp)
    for key in ("price", "last_price"):
        value = payload.get(key)
        if value:
            return float(value)
    pricebook = payload.get("pricebook") or {}
    if isinstance(pricebook, dict):
        bids = pricebook.get("bids") or []
        if bids:
            first = bids[0]
            if isinstance(first, dict) and first.get("price"):
                return float(first["price"])
    raise ValueError(f"could not resolve market price for {product_id}")


def record_trade(payload: dict) -> None:
    with TRADE_LOG.open("a") as f:
        f.write(json.dumps(_json_safe(payload)) + "\n")


# --- signal processing ------------------------------------------------------
def clamp_notional(usd: float, cfg: dict) -> float:
    p = cfg["position_sizing"]
    return max(p["min_notional"], min(p["max_notional"], round(usd, 2)))


def process_signal(
    path: Path,
    client: RESTClient,
    cfg: dict,
    state: dict,
    dry_run: bool,
) -> bool:
    """Process one signal file. Returns True on success."""
    try:
        sig = json.loads(path.read_text())
    except Exception as e:
        log.error("bad JSON in %s: %s", path.name, e)
        return False

    sig_id = sig.get("signal_id", path.stem)
    stype = sig.get("signal_type")
    if stype != "portfolio_allocation":
        log.warning("signal %s: unsupported type %r, skipping", sig_id, stype)
        return False

    allowed_symbols = set(cfg["symbols"])
    assets = sig.get("assets", {})
    if not assets:
        log.warning("signal %s: no assets, skipping", sig_id)
        return False

    any_success = False
    for symbol, leg in assets.items():
        if symbol not in allowed_symbols:
            log.info("signal %s: %s not in allowed symbols, skipping leg", sig_id, symbol)
            continue

        action = (leg.get("action") or "").lower()
        if action not in ("buy", "sell"):
            log.warning("signal %s: %s unknown action %r", sig_id, symbol, action)
            continue

        notional_req = float(leg.get("position_usd", 0) or 0)
        if notional_req <= 0:
            log.info("signal %s: %s zero notional, skipping", sig_id, symbol)
            continue

        notional = clamp_notional(notional_req, cfg)

        # circuit breakers
        tripped, reason = circuit_breakers_open(state, cfg)
        if tripped:
            log.warning("circuit breaker: %s — aborting remaining legs of %s", reason, sig_id)
            save_state(state)
            return any_success

        client_order_id = f"qsig-{sig_id[:8]}-{symbol}-{uuid.uuid4().hex[:6]}"

        trade_record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "signal_id": sig_id,
            "signal_file": path.name,
            "symbol": symbol,
            "side": action.upper(),
            "requested_usd": notional_req,
            "executed_usd": notional,
            "client_order_id": client_order_id,
            "dry_run": dry_run,
        }

        if dry_run:
            log.info(
                "[DRY-RUN] would %s %s $%.2f  (cid=%s)",
                action.upper(), symbol, notional, client_order_id,
            )
            trade_record["result"] = "dry_run_ok"
            record_trade(trade_record)
            any_success = True
            continue

        # --- LIVE ORDER -----------------------------------------------------
        try:
            if action == "buy":
                resp = client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=symbol,
                    quote_size=str(notional),  # USD amount
                )
            else:
                base_currency = symbol.split("-", 1)[0]
                available_base = _available_balance(client, base_currency)
                if available_base <= 0:
                    log.warning("signal %s: no %s balance available for SELL %s", sig_id, base_currency, symbol)
                    trade_record["result"] = "rejected_operational"
                    trade_record["error"] = f"no_balance:{base_currency}"
                    record_trade(trade_record)
                    continue

                price = _market_price(client, symbol)
                base_size = min(available_base, round(notional / price, 8))
                if base_size <= 0:
                    log.warning("signal %s: computed zero sell size for %s at %.8f", sig_id, symbol, price)
                    trade_record["result"] = "rejected_operational"
                    trade_record["error"] = f"zero_base_size:{symbol}"
                    record_trade(trade_record)
                    continue

                trade_record["base_size"] = base_size
                resp = client.market_order_sell(
                    client_order_id=client_order_id,
                    product_id=symbol,
                    base_size=f"{base_size:.8f}",
                )

            resp_raw = resp if isinstance(resp, dict) else getattr(resp, "__dict__", {"raw": str(resp)})
            resp_dict = _json_safe(resp_raw)
            trade_record["response"] = _redact(resp_dict)

            success = bool(resp_dict.get("success", False)) or bool(resp_dict.get("order_id"))
            if success:
                log.info("LIVE %s %s $%.2f OK  order=%s",
                         action.upper(), symbol, notional,
                         resp_dict.get("order_id") or resp_dict.get("success_response", {}).get("order_id"))
                now = datetime.now(timezone.utc).isoformat()
                state["trades_this_hour"].append(now)
                state["trades_today"].append(now)
                state["last_trade_at"] = now
                state["consecutive_losses"] = 0
                save_state(state)
                trade_record["result"] = "ok"
                any_success = True
            else:
                log.error("LIVE %s %s $%.2f FAILED  resp=%s",
                          action.upper(), symbol, notional, resp_dict)
                if _counts_as_loss(resp_dict):
                    state["consecutive_losses"] += 1
                    save_state(state)
                    trade_record["result"] = "rejected"
                else:
                    trade_record["result"] = "rejected_operational"
        except Exception as e:
            log.exception("exchange error on %s %s: %s", symbol, action, e)
            state["consecutive_losses"] += 1
            save_state(state)
            trade_record["result"] = f"exception:{type(e).__name__}"
            trade_record["error"] = str(e)

        record_trade(trade_record)

    return any_success


def _redact(d: Any) -> Any:
    """Shallow redact of anything that looks like a secret in responses."""
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            if re.search(r"(secret|private|key|token|signature)", str(k), re.I):
                out[k] = "<redacted>"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(d, list):
        return [_redact(x) for x in d]
    return d


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return str(value)


def _response_error_details(resp_dict: dict[str, Any]) -> tuple[str, str]:
    err = resp_dict.get("error_response") or {}
    code = str(err.get("error") or "")
    reason = str(err.get("preview_failure_reason") or err.get("message") or "")
    return code.upper(), reason.upper()


def _counts_as_loss(resp_dict: dict[str, Any]) -> bool:
    code, reason = _response_error_details(resp_dict)
    operational_markers = {
        "INSUFFICIENT_FUND",
        "PREVIEW_INSUFFICIENT_FUND",
        "INSUFFICIENT_BALANCE",
    }
    if code in operational_markers or reason in operational_markers:
        return False
    if "INSUFFICIENT" in code or "INSUFFICIENT" in reason:
        return False
    return True


# --- main loop --------------------------------------------------------------
def drain_once(client: RESTClient, cfg: dict, state: dict, dry_run: bool) -> int:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FAILED.mkdir(parents=True, exist_ok=True)

    if not is_trading_hours(cfg):
        log.info("outside trading hours; sleeping")
        return 0

    files = sorted(INBOX.glob("quantum_signal_*.json"))
    if not files:
        return 0

    processed = 0
    for f in files:
        tripped, reason = circuit_breakers_open(state, cfg)
        if tripped:
            log.warning("circuit breaker: %s — stopping drain", reason)
            save_state(state)
            break

        log.info("processing %s", f.name)
        ok = process_signal(f, client, cfg, state, dry_run)
        dest = PROCESSED if ok else FAILED
        try:
            shutil.move(str(f), str(dest / f.name))
        except Exception as e:
            log.error("could not move %s: %s", f.name, e)
        processed += 1
    return processed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="log trades but do NOT place orders")
    ap.add_argument("--once", action="store_true",
                    help="drain inbox once and exit")
    ap.add_argument("--interval", type=int, default=5,
                    help="seconds between inbox polls (default 5)")
    args = ap.parse_args()

    cfg = load_config()
    state = load_state()

    # honor config's own dry_run flag if set
    if cfg["execution"].get("dry_run") and not args.dry_run:
        log.warning("config has execution.dry_run=true; forcing --dry-run")
        args.dry_run = True

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    log.info("=== gate4 inbox consumer starting (%s) ===", mode)
    log.info("inbox:       %s", INBOX)
    log.info("processed:   %s", PROCESSED)
    log.info("failed:      %s", FAILED)
    log.info("trade log:   %s", TRADE_LOG)
    log.info("symbols:     %s", cfg["symbols"])
    log.info("notional:    $%.2f - $%.2f",
             cfg["position_sizing"]["min_notional"],
             cfg["position_sizing"]["max_notional"])
    cb = cfg["risk_management"]["circuit_breakers"]
    log.info("breakers:    %d/hr, %d/day, %d consec losses -> %dm cooldown",
             cb["max_hourly_trades"], cb["max_daily_trades"],
             cb["max_consecutive_losses"], cb["cool_down_minutes"])

    client = build_client(cfg)

    # graceful shutdown
    stop = {"flag": False}
    def _stop(signum, frame):
        log.info("signal %s received, draining current work then exiting", signum)
        stop["flag"] = True
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if args.once:
        n = drain_once(client, cfg, state, args.dry_run)
        log.info("drained %d file(s), exiting", n)
        return 0

    while not stop["flag"]:
        try:
            n = drain_once(client, cfg, state, args.dry_run)
            if n:
                log.info("processed %d signal(s) this pass", n)
        except Exception:
            log.exception("drain loop error")
        # short interval, but break fast on stop
        for _ in range(args.interval):
            if stop["flag"]:
                break
            time.sleep(1)

    log.info("=== gate4 inbox consumer stopped ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
