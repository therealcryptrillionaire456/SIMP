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
import urllib.error
import urllib.request
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
    if __name__ == "__main__":
        print(
            "[fatal] coinbase-advanced-py is not installed in this venv.\n"
            "        Install it with:\n"
            "        ./venv_gate4/bin/pip install coinbase-advanced-py\n",
            file=sys.stderr,
        )
        sys.exit(2)
    RESTClient = None  # type: ignore

from simp.exchange import CoinbaseOperationError, ResilientCoinbaseClient
from simp.memory import Episode, SystemMemoryStore, load_active_system_policies
from simp.policies.trading_policy import check_trade_allowed, PolicyViolation

# --- paths ------------------------------------------------------------------
REPO = Path(__file__).resolve().parent
INBOX = REPO / "data" / "inboxes" / "gate4_real"
PROCESSED = INBOX / "_processed"
FAILED = INBOX / "_failed"
STATE_FILE = REPO / "data" / "gate4_consumer_state.json"
LOG_DIR = REPO / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_LOG = LOG_DIR / "gate4_trades.jsonl"
PNL_LEDGER = REPO / "data" / "phase4_pnl_ledger.jsonl"
CONFIG_PATH = REPO / "config" / "live_production_config.json"
BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:5555").rstrip("/")
TRADE_RESULT_CHANNEL = "trade_updates"
TRADE_RESULT_RECIPIENTS = ("projectx_quantum_advisor", "projectx_native")
SYSTEM_MEMORY_STORE = SystemMemoryStore()

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
        "transient_errors": 0,
        "last_error_classification": None,
        "last_transient_error_at": None,
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


def reset_cooldown_if_expired(state: dict) -> bool:
    cooldown_until = state.get("cooldown_until")
    if not cooldown_until:
        return False
    try:
        cooldown_dt = datetime.fromisoformat(cooldown_until)
    except ValueError:
        state["cooldown_until"] = None
        return True
    if datetime.now(timezone.utc) < cooldown_dt:
        return False
    state["cooldown_until"] = None
    if state.get("consecutive_losses", 0):
        log.info(
            "cooldown expired at %s; resetting consecutive_losses from %s to 0",
            cooldown_dt.isoformat(),
            state.get("consecutive_losses", 0),
        )
    state["consecutive_losses"] = 0
    state["last_error_classification"] = None
    return True


def circuit_breakers_open(state: dict, cfg: dict) -> tuple[bool, str]:
    """Return (tripped, reason)."""
    cb = cfg["risk_management"]["circuit_breakers"]
    prune_timestamps(state)

    if state.get("cooldown_until"):
        cd = datetime.fromisoformat(state["cooldown_until"])
        if datetime.now(timezone.utc) < cd:
            return True, f"cooldown active until {cd.isoformat()}"
        reset_cooldown_if_expired(state)

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


def build_client(cfg: dict) -> ResilientCoinbaseClient:
    ex = cfg["exchange_config"]
    # Check for CDP key file first (preferred path for coinbase-advanced-py)
    cdp_key_file = os.path.expandvars(ex.get("key_file", ""))
    if cdp_key_file and os.path.exists(cdp_key_file):
        raw_client = RESTClient(
            key_file=cdp_key_file,
            timeout=ex.get("timeout_seconds", 30),
        )
    else:
        # Fallback: legacy api_key/api_secret path
        api_key_name = os.path.expandvars(ex["api_key_name"])
        api_secret = os.path.expandvars(ex["api_secret"]).strip()
        if api_secret.startswith(("'", '"')) and api_secret.endswith(("'", '"')):
            api_secret = api_secret[1:-1]
        if "\\n" in api_secret:
            api_secret = api_secret.replace("\\n", "\n")
        raw_client = RESTClient(
            api_key=api_key_name,
            api_secret=api_secret,
            timeout=ex.get("timeout_seconds", 30),
        )
    return ResilientCoinbaseClient(raw_client, logger=log)


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


def _balance_snapshot(client: ResilientCoinbaseClient, currency: str) -> dict[str, float]:
    try:
        records = _response_records(client.get_accounts())
    except CoinbaseOperationError:
        raise
    except Exception as exc:
        raise CoinbaseOperationError(
            message=f"balance lookup failed for {currency}: {exc}",
            classification="fatal",
            attempts=1,
            exception_type=type(exc).__name__,
            last_error=str(exc),
        ) from exc

    for record in records:
        asset = str(record.get("currency") or record.get("asset") or "").upper()
        if asset != currency.upper():
            continue
        total_raw = record.get("balance") or record.get("available_balance") or {}
        balance = record.get("available_balance") or record.get("available") or {}
        hold = record.get("hold") or record.get("held_balance") or {}
        if isinstance(balance, dict):
            raw = balance.get("value") or balance.get("amount") or 0
        else:
            raw = balance or 0
        if isinstance(total_raw, dict):
            total_value = total_raw.get("value") or total_raw.get("amount") or raw
        else:
            total_value = total_raw or raw
        if isinstance(hold, dict):
            hold_value = hold.get("value") or hold.get("amount") or 0
        else:
            hold_value = hold or 0
        try:
            available = float(raw)
            total = float(total_value)
            held = float(hold_value)
            return {
                "available": available,
                "total": total if total > 0 else available,
                "held": held,
            }
        except (TypeError, ValueError):
            return {"available": 0.0, "total": 0.0, "held": 0.0}
    return {"available": 0.0, "total": 0.0, "held": 0.0}


def _market_price(client: ResilientCoinbaseClient, product_id: str) -> float:
    try:
        resp = client.get_product(product_id=product_id)
    except Exception:
        resp = None

    if resp is None:
        raise CoinbaseOperationError(
            message=f"could not resolve market price for {product_id}",
            classification="fatal",
            attempts=1,
            exception_type="MarketPriceUnavailable",
            last_error=product_id,
        )

    # GetProductResponse has .price attribute (string)
    if hasattr(resp, "price") and resp.price:
        return float(resp.price)

    # Fallback: to_dict
    payload = resp.to_dict() if hasattr(resp, "to_dict") else {}
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
    raise CoinbaseOperationError(
        message=f"could not resolve market price for {product_id}",
        classification="fatal",
        attempts=1,
        exception_type="MarketPriceUnavailable",
        last_error=product_id,
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload)) + "\n")


def _record_trade_episode(payload: dict[str, Any]) -> None:
    try:
        SYSTEM_MEMORY_STORE.add_episode(
            Episode(
                episode_type="gate4_trade_result",
                source="gate4_inbox_consumer",
                entity=str(payload.get("client_order_id") or payload.get("signal_id") or "unknown"),
                summary=(
                    f"{payload.get('symbol', 'unknown')} "
                    f"{payload.get('side', 'unknown')} "
                    f"result={payload.get('result', 'unknown')}"
                ),
                occurred_at=str(payload.get("ts") or ""),
                payload=payload,
                tags=[
                    "trade",
                    str(payload.get("symbol") or "unknown"),
                    str(payload.get("side") or "unknown").lower(),
                    str(payload.get("result") or "unknown"),
                ],
            )
        )
    except Exception:
        log.debug("failed to record structured trade episode", exc_info=True)


def _extract_order_id(payload: dict[str, Any]) -> str | None:
    response = payload.get("response") or {}
    if not isinstance(response, dict):
        return None
    return response.get("order_id") or (response.get("success_response") or {}).get("order_id")


def _extract_fee_usd(payload: dict[str, Any]) -> float | None:
    response = payload.get("response") or {}
    if not isinstance(response, dict):
        return None
    candidates = [
        response.get("total_fees"),
        response.get("commission"),
        (response.get("success_response") or {}).get("total_fees"),
        (response.get("success_response") or {}).get("commission"),
    ]
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _estimate_entry_px(payload: dict[str, Any]) -> float | None:
    market_price = payload.get("market_price")
    if market_price:
        try:
            return float(market_price)
        except (TypeError, ValueError):
            return None

    base_size = payload.get("base_size")
    executed_usd = payload.get("executed_usd")
    try:
        if base_size and executed_usd:
            return round(float(executed_usd) / float(base_size), 8)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def append_pnl_entry(payload: dict[str, Any]) -> None:
    order_id = _extract_order_id(payload)
    entry = {
        "ts": payload.get("ts"),
        "exec_ts": payload.get("ts"),
        "signal_id": payload.get("signal_id"),
        "symbol": payload.get("symbol"),
        "side": payload.get("side"),
        "notional_usd": payload.get("executed_usd"),
        "exec_usd": payload.get("executed_usd"),
        "entry_px": _estimate_entry_px(payload),
        "fees_usd": _extract_fee_usd(payload),
        "client_order_id": payload.get("client_order_id"),
        "order_id": order_id,
        "source": "gate4_inbox_consumer",
    }
    _append_jsonl(PNL_LEDGER, entry)


def backfill_pnl_ledger() -> None:
    if not TRADE_LOG.exists():
        return
    known_ids: set[str] = set()
    if PNL_LEDGER.exists():
        for line in PNL_LEDGER.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("client_order_id"):
                known_ids.add(str(record["client_order_id"]))

    backfilled = 0
    for line in TRADE_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        client_order_id = str(record.get("client_order_id") or "")
        if not client_order_id or client_order_id in known_ids or record.get("result") != "ok":
            continue
        append_pnl_entry(record)
        known_ids.add(client_order_id)
        backfilled += 1
    if backfilled:
        log.info("backfilled %d Gate4 fills into %s", backfilled, PNL_LEDGER)


def _emit_trade_ack(payload: dict[str, Any]) -> None:
    if not BROKER_URL:
        return
    ack_payload = {
        "event": "gate4_trade_result",
        "signal_id": payload.get("signal_id"),
        "symbol": payload.get("symbol"),
        "side": payload.get("side"),
        "result": payload.get("result"),
        "order_id": _extract_order_id(payload),
        "client_order_id": payload.get("client_order_id"),
        "executed_usd": payload.get("executed_usd"),
        "error": payload.get("error"),
        "error_classification": payload.get("error_classification"),
        "timestamp": payload.get("ts"),
        "policy_decision": payload.get("policy_decision"),
        "policy_state_version": payload.get("policy_state_version"),
        "lineage": payload.get("lineage"),
    }
    body = {
        "sender_id": "gate4_real",
        "channel": TRADE_RESULT_CHANNEL,
        "payload": ack_payload,
        "ttl_seconds": 120,
    }
    for recipient in TRADE_RESULT_RECIPIENTS:
        body["recipient_id"] = recipient
        request = urllib.request.Request(
            f"{BROKER_URL}/mesh/send",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3):  # noqa: S310
                pass
        except (urllib.error.URLError, TimeoutError, OSError):
            continue


def record_trade(payload: dict) -> None:
    safe_payload = _json_safe(payload)
    _append_jsonl(TRADE_LOG, safe_payload)
    if safe_payload.get("result") == "ok":
        append_pnl_entry(safe_payload)
    _record_trade_episode(safe_payload)
    _emit_trade_ack(safe_payload)


# --- signal processing ------------------------------------------------------
def clamp_notional(usd: float, cfg: dict) -> float:
    p = cfg["position_sizing"]
    return max(p["min_notional"], min(p["max_notional"], round(usd, 2)))


def _extract_lineage(signal: dict[str, Any], policy_state: dict[str, Any]) -> dict[str, Any]:
    metadata = signal.get("metadata") or {}
    lineage = dict(metadata.get("lineage") or {})
    lineage.setdefault("source", signal.get("source"))
    lineage.setdefault("signal_id", signal.get("signal_id"))
    if metadata.get("qip_trace_id"):
        lineage.setdefault("qip_trace_id", metadata.get("qip_trace_id"))
    if metadata.get("bridge_cycle_id"):
        lineage.setdefault("bridge_cycle_id", metadata.get("bridge_cycle_id"))
    if metadata.get("plan_id"):
        lineage.setdefault("plan_id", metadata.get("plan_id"))
    if policy_state.get("generated_at"):
        lineage.setdefault("policy_state_version", policy_state.get("generated_at"))
    return lineage


def _quote_balance_usd(client: ResilientCoinbaseClient) -> float:
    balances = [_balance_snapshot(client, "USD"), _balance_snapshot(client, "USDC")]
    return round(sum(balance["available"] for balance in balances), 2)


def _apply_pre_fanout_budget(
    assets: dict[str, Any],
    cfg: dict,
    client: ResilientCoinbaseClient,
    policy_state: dict[str, Any],
) -> dict[str, Any]:
    capital_policy = policy_state.get("capital_budgeting") or {}
    if not capital_policy.get("enabled", False):
        return {
            "decision": "capital_budget_disabled",
            "allowed": {},
            "blocked": {},
            "available_quote_usd": None,
        }

    buy_legs: list[tuple[str, float, float]] = []
    for symbol, leg in assets.items():
        action = str(leg.get("action") or "").lower()
        if action != "buy":
            continue
        requested = float(leg.get("position_usd", 0.0) or 0.0)
        if requested <= 0:
            continue
        weight = float(leg.get("weight", requested) or requested)
        buy_legs.append((symbol, clamp_notional(requested, cfg), weight))

    if len(buy_legs) <= 1:
        return {
            "decision": "capital_budget_not_required",
            "allowed": {symbol: requested for symbol, requested, _ in buy_legs},
            "blocked": {},
            "available_quote_usd": None,
        }

    try:
        available_quote = max(
            0.0,
            round(
                _quote_balance_usd(client) - float(capital_policy.get("min_quote_reserve_usd", 0.0) or 0.0),
                2,
            ),
        )
    except CoinbaseOperationError as exc:
        return {
            "decision": "capital_budget_lookup_failed",
            "allowed": {symbol: requested for symbol, requested, _ in buy_legs},
            "blocked": {},
            "available_quote_usd": None,
            "error": exc.last_error,
            "error_classification": exc.classification,
        }

    remaining = available_quote
    min_notional = float(cfg["position_sizing"]["min_notional"])
    allowed: dict[str, float] = {}
    blocked: dict[str, str] = {}

    for symbol, requested, weight in sorted(buy_legs, key=lambda item: (-item[2], -item[1], item[0])):
        if remaining < min_notional:
            blocked[symbol] = "insufficient_quote_budget"
            continue
        allocation = min(requested, remaining)
        if allocation < min_notional:
            blocked[symbol] = "insufficient_quote_budget"
            continue
        allowed[symbol] = round(allocation, 2)
        remaining = round(remaining - allocation, 2)

    total_requested = round(sum(requested for _, requested, _ in buy_legs), 2)
    total_allocated = round(sum(allowed.values()), 2)
    decision = "capital_budget_clear"
    if blocked or total_allocated < total_requested:
        decision = "capital_budget_applied"

    return {
        "decision": decision,
        "allowed": allowed,
        "blocked": blocked,
        "available_quote_usd": available_quote,
        "remaining_quote_usd": remaining,
    }


def process_signal(
    path: Path,
    client: ResilientCoinbaseClient,
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
    policy_state = load_active_system_policies()
    lineage = _extract_lineage(sig, policy_state)
    budget_plan = {
        "decision": "capital_budget_unchecked",
        "allowed": {},
        "blocked": {},
        "available_quote_usd": None,
    }
    if not dry_run:
        budget_plan = _apply_pre_fanout_budget(assets, cfg, client, policy_state)

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
            "policy_state_version": policy_state.get("generated_at"),
            "policy_decision": budget_plan.get("decision"),
            "lineage": lineage,
        }

        if budget_plan.get("available_quote_usd") is not None:
            trade_record["available_quote_usd"] = budget_plan.get("available_quote_usd")

        if action == "buy" and symbol in (budget_plan.get("blocked") or {}):
            trade_record["result"] = "policy_blocked:capital_budget"
            trade_record["error"] = budget_plan["blocked"][symbol]
            record_trade(trade_record)
            continue

        if action == "buy" and symbol in (budget_plan.get("allowed") or {}):
            notional = float(budget_plan["allowed"][symbol])
            trade_record["executed_usd"] = notional

        if dry_run:
            log.info(
                "[DRY-RUN] would %s %s $%.2f  (cid=%s)",
                action.upper(), symbol, notional, client_order_id,
            )
            trade_record["result"] = "dry_run_ok"
            record_trade(trade_record)
            any_success = True
            continue

        # --- POLICY GATE (kill switch + risk limits) -----------------------
        try:
            # Use paper exchange name when live trading is disabled
            _exchange_name = "coinbase_paper" if os.environ.get("SIMP_LIVE_TRADING_ENABLED", "").lower() != "true" else "coinbase"
            check_trade_allowed(exchange=_exchange_name, size_usd=notional)
        except PolicyViolation as pv:
            log.error("POLICY BLOCKED %s %s $%.2f: %s", action.upper(), symbol, notional, pv.reason)
            trade_record["result"] = f"policy_blocked: {pv.reason}"
            trade_record["policy_decision"] = "policy_guard_blocked"
            record_trade(trade_record)
            continue

        # --- LIVE ORDER -----------------------------------------------------
        try:
            price_hint: float | None = None
            if action == "buy":
                try:
                    price_hint = _market_price(client, symbol)
                except CoinbaseOperationError:
                    price_hint = None
                if price_hint:
                    trade_record["market_price"] = price_hint
                resp = client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=symbol,
                    quote_size=str(notional),  # USD amount
                )
            else:
                base_currency = symbol.split("-", 1)[0]
                balance = _balance_snapshot(client, base_currency)
                available_base = balance["available"]
                held_balance = max(balance["available"], balance["total"])
                if available_base <= 0 or held_balance <= 0:
                    log.warning(
                        "signal %s: insufficient %s balance for SELL %s (available=%.8f total=%.8f)",
                        sig_id,
                        base_currency,
                        symbol,
                        available_base,
                        held_balance,
                    )
                    trade_record["result"] = "insufficient_balance"
                    trade_record["error"] = f"insufficient_balance:{base_currency}"
                    record_trade(trade_record)
                    continue

                price = _market_price(client, symbol)
                trade_record["market_price"] = price
                requested_base = round(notional / price, 8)
                safe_sellable = round(min(available_base, held_balance) * 0.99, 8)
                base_size = min(requested_base, safe_sellable)
                if base_size <= 0:
                    log.warning(
                        "signal %s: computed insufficient sell size for %s at %.8f (available=%.8f total=%.8f)",
                        sig_id,
                        symbol,
                        price,
                        available_base,
                        held_balance,
                    )
                    trade_record["result"] = "insufficient_balance"
                    trade_record["error"] = f"insufficient_balance:{symbol}"
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
                trade_record["error_classification"] = None
                any_success = True
            else:
                classification = _classify_response(resp_dict)
                log.error("LIVE %s %s $%.2f FAILED  resp=%s",
                          action.upper(), symbol, notional, resp_dict)
                trade_record["result"] = classification["result"]
                trade_record["error_classification"] = classification["classification"]
                state["last_error_classification"] = classification["classification"]
                if classification["classification"] == "transient":
                    state["transient_errors"] = state.get("transient_errors", 0) + 1
                    state["last_transient_error_at"] = datetime.now(timezone.utc).isoformat()
                    save_state(state)
                elif classification["counts_as_loss"]:
                    state["consecutive_losses"] += 1
                    save_state(state)
        except CoinbaseOperationError as e:
            log.exception("exchange error on %s %s classified=%s: %s", symbol, action, e.classification, e)
            trade_record["result"] = f"exception:{e.exception_type}"
            trade_record["error"] = e.last_error
            trade_record["error_classification"] = e.classification
            trade_record["attempts"] = e.attempts
            state["last_error_classification"] = e.classification
            if e.classification == "transient":
                state["transient_errors"] = state.get("transient_errors", 0) + 1
                state["last_transient_error_at"] = datetime.now(timezone.utc).isoformat()
            else:
                state["consecutive_losses"] += 1
            save_state(state)
        except Exception as e:
            log.exception("exchange error on %s %s: %s", symbol, action, e)
            state["consecutive_losses"] += 1
            state["last_error_classification"] = "fatal"
            save_state(state)
            trade_record["result"] = f"exception:{type(e).__name__}"
            trade_record["error"] = str(e)
            trade_record["error_classification"] = "fatal"

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


def _classify_response(resp_dict: dict[str, Any]) -> dict[str, Any]:
    code, reason = _response_error_details(resp_dict)
    merged = f"{code} {reason}"
    if not merged.strip():
        return {
            "classification": "fatal",
            "counts_as_loss": True,
            "result": "rejected",
        }
    if "INSUFFICIENT" in merged:
        return {
            "classification": "operational",
            "counts_as_loss": False,
            "result": "insufficient_balance",
        }
    transient_markers = ("RATE_LIMIT", "TOO_MANY_REQUESTS", "TEMPORARY", "SERVICE_UNAVAILABLE", "TIMEOUT", "429", "503", "504", "502")
    if any(marker in merged for marker in transient_markers):
        return {
            "classification": "transient",
            "counts_as_loss": False,
            "result": "rejected_transient",
        }
    return {
        "classification": "fatal",
        "counts_as_loss": True,
        "result": "rejected",
    }


# --- main loop --------------------------------------------------------------
def drain_once(client: ResilientCoinbaseClient, cfg: dict, state: dict, dry_run: bool) -> int:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FAILED.mkdir(parents=True, exist_ok=True)
    if reset_cooldown_if_expired(state):
        save_state(state)

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
    backfill_pnl_ledger()

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
