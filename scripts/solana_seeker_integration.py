#!/usr/bin/env python3.10
"""
Solana Seeker integration with explicit dry-run/live modes.

This runtime consumes `data/signals/solana_*.json`, applies active system
policies, records structured trade artifacts, and can run once or as a daemon.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import shutil
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from simp.memory import Episode, SystemMemoryStore, load_active_system_policies


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "solana_seeker_config.json"
SIGNALS_DIR = ROOT / "data" / "signals"
STATE_FILE = ROOT / "data" / "solana_seeker_state.json"
TRADE_LOG = ROOT / "logs" / "solana_seeker_trades.jsonl"
LEDGER = ROOT / "data" / "solana_seeker_ledger.jsonl"
LOG_PATH = ROOT / "logs" / "solana_seeker.log"
PROCESSED_DIR = SIGNALS_DIR / "processed"
FAILED_DIR = SIGNALS_DIR / "failed"
SYSTEM_MEMORY_STORE = SystemMemoryStore()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [solana_seeker] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH),
    ],
)
log = logging.getLogger("solana_seeker")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return str(value)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload)) + "\n")


def _load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            log.warning("solana state file corrupt, starting fresh")
    return {
        "trades_today": [],
        "trades_this_hour": [],
        "consecutive_losses": 0,
        "last_trade_at": None,
        "cooldown_until": None,
        "wallet_balance": {},
        "performance_metrics": {},
        "last_reflection_policy": None,
    }


def _save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def _load_config(config_arg: str) -> Dict[str, Any]:
    config_path = Path(config_arg)
    if not config_path.is_absolute():
        config_path = ROOT / "config" / config_arg
    if not config_path.exists():
        raise FileNotFoundError(f"configuration file not found: {config_path}")
    raw = json.loads(config_path.read_text())
    return raw.get("solana_seeker", raw)


def _extract_lineage(signal: Dict[str, Any], policy_state: Dict[str, Any]) -> Dict[str, Any]:
    metadata = signal.get("metadata") or {}
    lineage = dict(metadata.get("lineage") or {})
    lineage.setdefault("signal_id", signal.get("signal_id"))
    lineage.setdefault("source", signal.get("source"))
    if metadata.get("plan_id"):
        lineage.setdefault("plan_id", metadata.get("plan_id"))
    if metadata.get("qip_trace_id"):
        lineage.setdefault("qip_trace_id", metadata.get("qip_trace_id"))
    lineage.setdefault("policy_state_version", policy_state.get("generated_at"))
    return lineage


def _record_episode(
    episode_type: str,
    entity: str,
    summary: str,
    payload: Dict[str, Any],
    *,
    tags: Optional[List[str]] = None,
) -> None:
    try:
        SYSTEM_MEMORY_STORE.add_episode(
            Episode(
                episode_type=episode_type,
                source="solana_seeker",
                entity=entity,
                summary=summary,
                occurred_at=_utcnow(),
                payload=payload,
                tags=tags or ["solana", episode_type],
            )
        )
    except Exception:
        log.debug("failed to persist Solana episode", exc_info=True)


class SolanaSeekerAPI:
    """HTTP client for the Seeker API surface."""

    def __init__(self, config: Dict[str, Any]):
        phone = config.get("phone_integration", {})
        self.api_key = os.getenv("SOLANA_SEEKER_API_KEY", "")
        self.api_secret = os.getenv("SOLANA_SEEKER_SECRET", "")
        self.wallet_address = os.getenv("SOLANA_WALLET_ADDRESS", "")
        self.base_url = phone.get("api_endpoint", "https://api.solana-seeker.com/v1").rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "SolanaSeekerAPI":
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session:
            await self.session.close()

    def _signature(self) -> str:
        timestamp = str(int(time.time()))
        seed = f"{self.api_key}{self.api_secret}{timestamp}"
        return hashlib.sha256(seed.encode()).hexdigest()

    async def authenticate(self) -> bool:
        if not self.session:
            raise RuntimeError("session not initialized")
        if not self.api_key or not self.wallet_address:
            log.error("missing Solana Seeker credentials")
            return False

        payload = {
            "api_key": self.api_key,
            "timestamp": int(time.time()),
            "signature": self._signature(),
        }
        try:
            async with self.session.post(f"{self.base_url}/auth", json=payload) as response:
                return response.status == 200
        except Exception as exc:
            log.error("authentication error: %s", exc)
            return False

    async def place_order(self, order_data: Dict[str, Any], *, live_mode: bool) -> Dict[str, Any]:
        order = dict(order_data)
        order.setdefault("client_order_id", f"solana-{uuid.uuid4().hex[:8]}")
        order["timestamp"] = int(time.time())
        if not live_mode:
            return {
                "success": True,
                "order_id": f"dry_run_{uuid.uuid4().hex[:8]}",
                "dry_run": True,
            }
        if not self.session:
            raise RuntimeError("session not initialized")
        try:
            async with self.session.post(
                f"{self.base_url}/orders",
                json=order,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as response:
                payload = await response.json(content_type=None)
                if response.status == 200:
                    payload.setdefault("success", True)
                    return payload
                payload.setdefault("success", False)
                payload.setdefault("error", str(response.status))
                return payload
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def get_wallet_balance(self) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("session not initialized")
        try:
            async with self.session.get(
                f"{self.base_url}/wallet/balance",
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as response:
                if response.status == 200:
                    return await response.json(content_type=None)
        except Exception as exc:
            log.error("wallet balance fetch failed: %s", exc)
        return {}


class SolanaSeekerTrader:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api = SolanaSeekerAPI(config)
        self.state = _load_state()

    def _clamp_notional(self, notional: float) -> float:
        sizing = self.config.get("position_sizing", {})
        microscopic = sizing.get("microscopic", {})
        min_usd = float(microscopic.get("min_usd", 0.01))
        max_usd = float(microscopic.get("max_usd", 10.0))
        return max(min_usd, min(max_usd, round(notional, 2)))

    def _quality_allowed(self, signal: Dict[str, Any], policy_state: Dict[str, Any]) -> tuple[bool, float]:
        quality = float((signal.get("metadata") or {}).get("quality_score", 1.0) or 0.0)
        execution_quality = policy_state.get("execution_quality") or {}
        threshold = float(execution_quality.get("min_quality_score", 0.5) or 0.5)
        return quality >= threshold, threshold

    def _record_trade(
        self,
        record: Dict[str, Any],
        *,
        live_mode: bool,
    ) -> None:
        _append_jsonl(TRADE_LOG, record)
        if record.get("result") == "ok" and live_mode:
            _append_jsonl(
                LEDGER,
                {
                    "ts": record.get("ts"),
                    "signal_id": record.get("signal_id"),
                    "symbol": record.get("symbol"),
                    "side": record.get("side"),
                    "exec_usd": record.get("executed_usd"),
                    "client_order_id": record.get("client_order_id"),
                    "order_id": (record.get("response") or {}).get("order_id"),
                    "source": "solana_seeker",
                },
            )
        _record_episode(
            "solana_trade_result",
            str(record.get("client_order_id") or record.get("signal_id") or "unknown"),
            f"{record.get('symbol', 'unknown')} {record.get('side', 'unknown')} result={record.get('result', 'unknown')}",
            record,
            tags=["solana", "trade", str(record.get("result") or "unknown")],
        )

    async def process_signal(self, signal: Dict[str, Any], *, live_mode: bool) -> Dict[str, Any]:
        policy_state = load_active_system_policies()
        lineage = _extract_lineage(signal, policy_state)
        quality_ok, quality_threshold = self._quality_allowed(signal, policy_state)
        result = {
            "signal_id": signal.get("signal_id", str(uuid.uuid4())),
            "timestamp": _utcnow(),
            "positions": [],
            "total_notional": 0.0,
            "success": True,
            "errors": [],
            "lineage": lineage,
            "policy_state_version": policy_state.get("generated_at"),
        }

        if not quality_ok:
            result["success"] = False
            result["errors"].append(f"quality_below_threshold:{quality_threshold}")
            _record_episode(
                "solana_signal_blocked",
                result["signal_id"],
                "Solana signal blocked by execution quality policy",
                result,
                tags=["solana", "policy_blocked"],
            )
            return result

        for asset, position_data in (signal.get("assets") or {}).items():
            position = await self._process_asset(
                result["signal_id"],
                asset,
                position_data,
                live_mode=live_mode,
                lineage=lineage,
                policy_state_version=policy_state.get("generated_at"),
            )
            result["positions"].append(position)
            result["total_notional"] += float(position.get("executed_notional") or 0.0)
            if position.get("status") not in {"executed", "skipped"}:
                result["success"] = False
                result["errors"].append(f"{asset}:{position.get('status')}")

        if live_mode and result["success"]:
            now = _utcnow()
            self.state["trades_today"].append(now)
            self.state["trades_this_hour"].append(now)
            self.state["last_trade_at"] = now
            self.state["consecutive_losses"] = 0
            self.state["last_reflection_policy"] = policy_state.get("generated_at")
            _save_state(self.state)

        _record_episode(
            "solana_signal_processed",
            result["signal_id"],
            f"Solana signal processed success={result['success']}",
            result,
            tags=["solana", "signal", "success" if result["success"] else "failure"],
        )
        return result

    async def _process_asset(
        self,
        signal_id: str,
        asset: str,
        position_data: Dict[str, Any],
        *,
        live_mode: bool,
        lineage: Dict[str, Any],
        policy_state_version: Optional[str],
    ) -> Dict[str, Any]:
        action = str(position_data.get("action", "")).lower()
        requested = float(position_data.get("position_usd", 0.0) or 0.0)

        if action == "hold" or requested <= 0 or action not in {"buy", "sell"}:
            return {
                "asset": asset,
                "status": "skipped",
                "reason": "invalid_or_hold_action",
                "requested_notional": requested,
                "executed_notional": 0.0,
            }

        notional = self._clamp_notional(requested)
        order_payload = {
            "symbol": asset,
            "action": action.upper(),
            "notional": notional,
        }
        response = await self.api.place_order(order_payload, live_mode=live_mode)
        client_order_id = response.get("client_order_id") or order_payload.get("client_order_id") or f"solana-{uuid.uuid4().hex[:8]}"
        trade_record = {
            "ts": _utcnow(),
            "signal_id": signal_id,
            "symbol": asset,
            "side": action.upper(),
            "requested_usd": requested,
            "executed_usd": notional,
            "client_order_id": client_order_id,
            "response": _json_safe(response),
            "dry_run": not live_mode,
            "lineage": lineage,
            "policy_state_version": policy_state_version,
        }
        if response.get("success"):
            trade_record["result"] = "ok"
            status = "executed"
        else:
            trade_record["result"] = "failed"
            trade_record["error"] = response.get("error", "unknown_error")
            status = "failed"

        self._record_trade(trade_record, live_mode=live_mode)
        return {
            "asset": asset,
            "action": action.upper(),
            "requested_notional": requested,
            "executed_notional": notional,
            "status": status,
            "order_id": response.get("order_id"),
            "client_order_id": client_order_id,
        }

    async def sync_wallet_data(self) -> None:
        balance = await self.api.get_wallet_balance()
        if balance:
            self.state["wallet_balance"] = balance
            _save_state(self.state)


async def _process_signal_file(
    trader: SolanaSeekerTrader,
    signal_file: Path,
    *,
    live_mode: bool,
) -> bool:
    try:
        signal = json.loads(signal_file.read_text())
        result = await trader.process_signal(signal, live_mode=live_mode)
        target_dir = PROCESSED_DIR if result["success"] else FAILED_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(signal_file), str(target_dir / signal_file.name))
        return result["success"]
    except Exception as exc:
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        log.exception("signal processing failed for %s: %s", signal_file.name, exc)
        shutil.move(str(signal_file), str(FAILED_DIR / signal_file.name))
        return False


async def _run_once(trader: SolanaSeekerTrader, *, live_mode: bool) -> int:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    signal_files = sorted(SIGNALS_DIR.glob("solana_*.json"))
    processed = 0
    for signal_file in signal_files:
        await _process_signal_file(trader, signal_file, live_mode=live_mode)
        processed += 1
    return processed


async def main() -> int:
    parser = argparse.ArgumentParser(description="Solana Seeker integration")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode")
    parser.add_argument("--live", action="store_true", help="Enable live order placement")
    parser.add_argument("--once", action="store_true", help="Process signals once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=15, help="Seconds between daemon polling passes")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG.name), help="Configuration file path")
    args = parser.parse_args()

    if args.dry_run and args.live:
        raise SystemExit("choose either --dry-run or --live, not both")

    config = _load_config(args.config)
    live_mode = bool(args.live)
    if not live_mode:
        log.info("Solana Seeker running in DRY-RUN mode")
    else:
        log.info("Solana Seeker running in LIVE mode")

    trader = SolanaSeekerTrader(config)
    stop = {"flag": False}

    def _stop(signum, frame):
        log.info("received signal %s, stopping", signum)
        stop["flag"] = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    async with trader.api:
        if live_mode and not await trader.api.authenticate():
            raise SystemExit("Solana Seeker authentication failed")
        if live_mode:
            await trader.sync_wallet_data()

        if args.once or not args.daemon:
            await _run_once(trader, live_mode=live_mode)
            return 0

        while not stop["flag"]:
            await _run_once(trader, live_mode=live_mode)
            for _ in range(args.interval):
                if stop["flag"]:
                    break
                await asyncio.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
