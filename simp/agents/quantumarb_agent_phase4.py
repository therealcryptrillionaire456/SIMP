#!/usr/bin/env python3.10
"""
QuantumArb Agent - Phase 4

Operational Phase 4 agent that consumes file-based inbox intents for:
- two-leg arbitrage execution
- KTC spot accumulation requests

The agent keeps live execution behind explicit config/env gates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from monitoring_alerting_system import AlertSeverity, MonitoringSystem

from simp.organs.quantumarb.exchange_connector import (
    ExchangeConnector,
    OrderSide,
    StubExchangeConnector,
    create_exchange_connector,
)
from simp.organs.quantumarb.executor import ExecutionResult, TradeExecutor
from simp.organs.quantumarb.pnl_ledger import PNLLedger
from simp.security.brp_bridge import BRPBridge
from simp.security.brp_models import BRPMode, BRPObservation

logger = logging.getLogger("quantumarb_phase4")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_update(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _resolve_env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"\$\{([A-Z0-9_]+)\}", value)
    if match:
        return os.getenv(match.group(1), "")
    return value


def _resolve_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_tree(v) for v in value]
    return _resolve_env(value)


def _asset_to_symbol(asset: str) -> str:
    normalized = (asset or "SOL").strip().lower()
    mapping = {
        "bitcoin": "BTC-USD",
        "btc": "BTC-USD",
        "ethereum": "ETH-USD",
        "eth": "ETH-USD",
        "solana": "SOL-USD",
        "sol": "SOL-USD",
        "litecoin": "LTC-USD",
        "ltc": "LTC-USD",
    }
    if "-" in asset:
        return asset.upper()
    return mapping.get(normalized, f"{asset.upper()}-USD")


class ArbType(str, Enum):
    CROSS_VENUE = "cross_venue"


class ArbDecision(str, Enum):
    EXECUTE = "execute"
    REJECT_RISK = "reject_risk"
    REJECT_SLIPPAGE = "reject_slippage"


@dataclass
class ArbitrageSignal:
    signal_id: str
    arb_type: ArbType
    symbol_a: str
    symbol_b: str
    venue_a: str
    venue_b: str
    spread_pct: float
    expected_return_pct: float
    timestamp: str
    confidence: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        return cls(
            signal_id=intent.get("signal_id", str(uuid.uuid4())),
            arb_type=ArbType(intent.get("arb_type", ArbType.CROSS_VENUE.value)),
            symbol_a=intent["symbol_a"],
            symbol_b=intent["symbol_b"],
            venue_a=intent["venue_a"],
            venue_b=intent["venue_b"],
            spread_pct=float(intent["spread_pct"]),
            expected_return_pct=float(intent.get("expected_return_pct", 0.0)),
            timestamp=intent.get("timestamp", _utcnow()),
            confidence=float(intent.get("confidence", 0.0)),
            metadata=intent.get("metadata", {}),
        )


@dataclass
class ArbitrageOpportunity:
    opportunity_id: str
    signal: ArbitrageSignal
    decision: ArbDecision
    decision_reason: str
    position_size_usd: float
    expected_pnl_usd: float
    max_slippage_pct: float
    risk_score: float
    timestamp: str
    execution_plan: Optional[Dict[str, Any]] = None
    monitoring_id: Optional[str] = None


@dataclass
class InvestmentRequest:
    intent_id: str
    user_id: str
    amount_usd: float
    asset: str
    symbol: str
    review_required: bool
    auto_approve: bool
    timestamp: str
    source_agent: str = "ktc_api"
    exchange: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "InvestmentRequest":
        params = intent.get("params", {})
        payload = intent.get("payload", {})
        asset = params.get("asset") or payload.get("asset") or "SOL"
        return cls(
            intent_id=intent.get("intent_id", str(uuid.uuid4())),
            user_id=params.get("user_id") or payload.get("user_id") or "anonymous",
            amount_usd=float(params.get("amount_usd") or payload.get("amount_usd") or 0.0),
            asset=asset,
            symbol=_asset_to_symbol(asset),
            review_required=bool(params.get("review_required", payload.get("review_required", False))),
            auto_approve=bool(params.get("auto_approve", True)),
            timestamp=intent.get("timestamp", _utcnow()),
            source_agent=intent.get("source_agent", "ktc_api"),
            exchange=params.get("exchange") or payload.get("exchange"),
            metadata=intent.get("metadata", {}),
        )


class QuantumArbEnginePhase4:
    """Operational Phase 4 engine backed by the shared TradeExecutor."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.monitoring_system = MonitoringSystem()
        self.exchange_connectors: Dict[str, ExchangeConnector] = {}
        self.default_exchange_name = "coinbase_sandbox"
        self._init_exchange_connectors()
        executor_config = dict(self.config["executor"])
        executor_config.setdefault(
            "max_position_size_usd",
            float(self.config["risk"]["max_position_size_usd"]),
        )
        executor_config.setdefault(
            "max_slippage_bps",
            float(self.config["risk"]["max_slippage_pct"]) * 100.0,
        )
        self.trade_executor = TradeExecutor(
            exchange_connectors=self.exchange_connectors,
            monitoring_system=self.monitoring_system,
            default_exchange_name=self.default_exchange_name,
            allow_live_trading=bool(self.config["executor"]["allow_live_trading"]),
            config=executor_config,
        )
        self.pnl_ledger = PNLLedger(self.config["pnl_ledger_path"])

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        default_config: Dict[str, Any] = {
            "exchanges": {
                "coinbase_sandbox": {
                    "driver": "coinbase",
                    "sandbox": True,
                    "enabled": True,
                    "api_key": "",
                    "api_secret": "",
                    "passphrase": "",
                }
            },
            "risk": {
                "max_position_size_usd": 0.10,
                "max_daily_loss_usd": 1.00,
                "min_spread_pct": 0.01,
                "max_slippage_pct": 0.05,
                "risk_score_threshold": 0.7,
            },
            "executor": {
                "max_position_size_usd": 0.10,
                "max_slippage_bps": 20.0,
                "max_retries": 1,
                "retry_delay_seconds": 1.0,
                "allow_live_trading": False,
            },
            "monitoring": {"enabled": True},
            "pnl_ledger_path": "data/phase4_pnl_ledger.jsonl",
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as handle:
                raw = _resolve_tree(json.load(handle))
            normalized = self._normalize_config(raw)
            _deep_update(default_config, normalized)

        env_live = os.getenv("QUANTUMARB_ALLOW_LIVE_TRADING")
        if env_live is not None:
            default_config["executor"]["allow_live_trading"] = env_live.lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        return default_config

    def _normalize_config(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}

        for passthrough in ("risk", "executor", "monitoring", "pnl_ledger_path"):
            if passthrough in raw:
                normalized[passthrough] = raw[passthrough]

        if "risk_parameters" in raw:
            rp = raw["risk_parameters"]
            normalized["risk"] = {
                "max_position_size_usd": rp.get("microscopic_trading", {}).get("max_position_size_usd", 0.10),
                "max_daily_loss_usd": rp.get("microscopic_trading", {}).get("max_daily_loss_usd", 1.00),
                "min_spread_pct": rp.get("spread_thresholds", {}).get("min_spread_pct", 0.01),
                "max_slippage_pct": rp.get("slippage_limits", {}).get("max_slippage_pct", 0.05),
                "risk_score_threshold": rp.get("risk_scoring", {}).get("min_risk_score", 0.7),
            }
            normalized["executor"] = {
                "max_position_size_usd": normalized["risk"]["max_position_size_usd"],
                "max_slippage_bps": normalized["risk"]["max_slippage_pct"] * 10000,
                "max_retries": raw.get("execution_parameters", {}).get("retry_logic", {}).get("max_retries", 1),
                "retry_delay_seconds": raw.get("execution_parameters", {}).get("retry_logic", {}).get("retry_delay_seconds", 1.0),
                "allow_live_trading": bool(os.getenv("QUANTUMARB_ALLOW_LIVE_TRADING", "false").lower() in {"1", "true", "yes", "on"}),
            }
            normalized["pnl_ledger_path"] = raw.get("pnl_tracking", {}).get("ledger_path", "data/phase4_pnl_ledger.jsonl")

        exchanges = raw.get("exchanges", {})
        if exchanges:
            normalized["exchanges"] = {}
            for alias, config in exchanges.items():
                if "environments" in config:
                    for env_name, env_cfg in config["environments"].items():
                        env_alias = f"{alias}_{env_name}"
                        normalized["exchanges"][env_alias] = {
                            "driver": alias,
                            "sandbox": env_name != "production",
                            "enabled": bool(env_cfg.get("enabled", False)),
                            "api_key": env_cfg.get("api_key", ""),
                            "api_secret": env_cfg.get("api_secret", ""),
                            "passphrase": env_cfg.get("passphrase", ""),
                        }
                else:
                    driver = config.get("driver", alias.split("_")[0])
                    normalized["exchanges"][alias] = {
                        "driver": driver,
                        "sandbox": config.get("type", "sandbox") != "live",
                        "enabled": bool(config.get("enabled", True)),
                        "api_key": config.get("api_key", ""),
                        "api_secret": config.get("api_secret", ""),
                        "passphrase": config.get("passphrase", ""),
                    }

        return normalized

    def _init_exchange_connectors(self) -> None:
        self.exchange_connectors.clear()
        for alias, config in self.config["exchanges"].items():
            if not config.get("enabled", True):
                continue
            driver = config.get("driver", alias.split("_")[0])
            sandbox = bool(config.get("sandbox", True))
            api_key = config.get("api_key", "")
            api_secret = config.get("api_secret", "")
            passphrase = config.get("passphrase", "")
            if driver == "stub":
                connector = StubExchangeConnector(sandbox=True, simulated_latency_ms=0)
            elif sandbox and not (api_key and api_secret and passphrase):
                connector = StubExchangeConnector(sandbox=True, simulated_latency_ms=0)
            else:
                connector = create_exchange_connector(
                    exchange_name=driver,
                    api_key=api_key,
                    api_secret=api_secret,
                    passphrase=passphrase,
                    sandbox=sandbox,
                )
            self.exchange_connectors[alias] = connector
        if not self.exchange_connectors:
            raise RuntimeError("No enabled exchange connectors configured")
        self.default_exchange_name = next(iter(self.exchange_connectors.keys()))

    def _estimate_slippage_pct(self, symbol: str, exchange_name: str, side: OrderSide, amount_usd: float) -> float:
        connector = self.exchange_connectors[exchange_name]
        ticker = connector.get_ticker(symbol)
        quantity = amount_usd / max(ticker.last, 1e-9)
        return connector.estimate_slippage(symbol, side, quantity) / 100.0

    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        min_spread = float(self.config["risk"]["min_spread_pct"])
        if signal.spread_pct < min_spread:
            return ArbitrageOpportunity(
                opportunity_id=str(uuid.uuid4()),
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                decision_reason=f"Spread {signal.spread_pct:.4f}% below minimum {min_spread:.4f}%",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                max_slippage_pct=0.0,
                risk_score=0.0,
                timestamp=_utcnow(),
            )

        liquidity_score = float(signal.metadata.get("liquidity_score", 1.0))
        max_trade_size = float(
            signal.metadata.get(
                "max_trade_size_usd",
                self.config["risk"]["max_position_size_usd"],
            )
        )

        position_size = min(float(self.config["risk"]["max_position_size_usd"]), float(max_trade_size))
        slippage_pct = self._estimate_slippage_pct(signal.symbol_a, signal.venue_a, OrderSide.BUY, position_size)
        slippage_pct += self._estimate_slippage_pct(signal.symbol_b, signal.venue_b, OrderSide.SELL, position_size)
        max_slippage_pct = float(self.config["risk"]["max_slippage_pct"])
        if slippage_pct > max_slippage_pct:
            return ArbitrageOpportunity(
                opportunity_id=str(uuid.uuid4()),
                signal=signal,
                decision=ArbDecision.REJECT_SLIPPAGE,
                decision_reason=f"Estimated slippage {slippage_pct:.4f}% exceeds maximum {max_slippage_pct:.4f}%",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                max_slippage_pct=slippage_pct,
                risk_score=0.0,
                timestamp=_utcnow(),
            )

        daily_pnl = self.pnl_ledger.get_statistics(days=1)["total_net_pnl"]
        if daily_pnl < -float(self.config["risk"]["max_daily_loss_usd"]):
            return ArbitrageOpportunity(
                opportunity_id=str(uuid.uuid4()),
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                decision_reason="Daily loss limit reached",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                max_slippage_pct=slippage_pct,
                risk_score=0.0,
                timestamp=_utcnow(),
            )

        risk_score = min(
            1.0,
            (min(signal.spread_pct / max(min_spread, 1e-9), 1.0) * 0.4)
            + (signal.confidence * 0.2)
            + (min(liquidity_score, 1.0) * 0.2)
            + (max(0.0, 1.0 - (slippage_pct / max(max_slippage_pct, 1e-9))) * 0.2),
        )
        threshold = float(self.config["risk"]["risk_score_threshold"])
        if risk_score < threshold:
            return ArbitrageOpportunity(
                opportunity_id=str(uuid.uuid4()),
                signal=signal,
                decision=ArbDecision.REJECT_RISK,
                decision_reason=f"Risk score {risk_score:.2f} below threshold {threshold:.2f}",
                position_size_usd=0.0,
                expected_pnl_usd=0.0,
                max_slippage_pct=slippage_pct,
                risk_score=risk_score,
                timestamp=_utcnow(),
            )

        expected_return = signal.expected_return_pct - slippage_pct
        execution_plan = {
            "steps": [
                {
                    "step": 1,
                    "action": "buy",
                    "symbol": signal.symbol_a,
                    "venue": signal.venue_a,
                    "amount_usd": position_size,
                },
                {
                    "step": 2,
                    "action": "sell",
                    "symbol": signal.symbol_b,
                    "venue": signal.venue_b,
                    "amount_usd": position_size,
                },
            ],
            "total_position_usd": position_size,
            "total_slippage_pct": slippage_pct,
        }
        monitoring_id = None
        if self.config["monitoring"]["enabled"]:
            monitoring_id = self.monitoring_system.record_intent(
                signal.signal_id,
                {
                    "timestamp": signal.timestamp,
                    "payload": {
                        "symbol": signal.symbol_a,
                        "price_a": signal.spread_pct,
                        "volume": position_size,
                    },
                },
            )

        return ArbitrageOpportunity(
            opportunity_id=str(uuid.uuid4()),
            signal=signal,
            decision=ArbDecision.EXECUTE,
            decision_reason=f"Approved: spread={signal.spread_pct:.4f}%, risk={risk_score:.2f}",
            position_size_usd=position_size,
            expected_pnl_usd=position_size * expected_return / 100.0,
            max_slippage_pct=slippage_pct,
            risk_score=risk_score,
            timestamp=_utcnow(),
            execution_plan=execution_plan,
            monitoring_id=monitoring_id,
        )

    async def execute_opportunity(self, opportunity: ArbitrageOpportunity) -> ExecutionResult:
        if opportunity.decision != ArbDecision.EXECUTE:
            return ExecutionResult(
                success=False,
                error_message=opportunity.decision_reason,
                timestamp=_utcnow(),
            )

        result = self.trade_executor.execute_arbitrage(
            opportunity=opportunity,
            execution_plan=opportunity.execution_plan,
        )
        if result.success and len(result.trades) >= 2:
            leg_a, leg_b = result.trades[0], result.trades[1]
            self.pnl_ledger.record_arbitrage_trade(
                trade_id=opportunity.opportunity_id,
                symbol=opportunity.signal.symbol_a,
                exchange_a=leg_a["exchange"],
                exchange_b=leg_b["exchange"],
                leg_a_result=leg_a,
                leg_b_result=leg_b,
                expected_spread_bps=opportunity.signal.spread_pct * 100,
                brp_decision=opportunity.decision.value,
                risk_allowed=True,
                position_size_usd=opportunity.position_size_usd,
                risk_percentage=0.0,
                monitoring_trade_id=opportunity.monitoring_id,
            )
            if opportunity.monitoring_id:
                self.monitoring_system.record_pnl(
                    opportunity.monitoring_id,
                    {"pnl": result.total_pnl_usd},
                )
        return result

    async def execute_investment_request(self, request: InvestmentRequest) -> ExecutionResult:
        exchange_name = request.exchange or self.default_exchange_name
        connector = self.exchange_connectors[exchange_name]
        ticker = connector.get_ticker(request.symbol)
        quantity = request.amount_usd / max(ticker.ask, 1e-9)
        return self.trade_executor.execute_investment(
            exchange_name=exchange_name,
            symbol=request.symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            trade_id=request.intent_id,
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        stats = self.pnl_ledger.get_statistics()
        return {
            "trades_executed": stats["total_trades"],
            "total_pnl_usd": stats["total_net_pnl"],
            "win_rate": stats["win_rate"],
            "daily_pnl_usd": self.pnl_ledger.get_statistics(days=1)["total_net_pnl"],
            "exchange_status": {
                name: ("sandbox" if connector.sandbox else "live")
                for name, connector in self.exchange_connectors.items()
            },
            "executor": self.trade_executor.get_execution_stats(),
        }


class QuantumArbAgentPhase4:
    def __init__(self, poll_interval: float = 2.0, config_path: Optional[str] = None):
        self.poll_interval = poll_interval
        self.engine = QuantumArbEnginePhase4(config_path)
        self.base_dir = Path("data/quantumarb_phase4")
        self.inbox_dir = self.base_dir / "inbox"
        self.outbox_dir = self.base_dir / "outbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.brp_bridge = BRPBridge()

    async def run(self) -> None:
        logger.info("Starting QuantumArbAgentPhase4")
        while True:
            self._process_inbox()
            self._check_alerts()
            await asyncio.sleep(self.poll_interval)

    def _process_inbox(self) -> None:
        processed_dir = self.inbox_dir / "processed"
        error_dir = self.inbox_dir / "error"
        processed_dir.mkdir(exist_ok=True)
        error_dir.mkdir(exist_ok=True)

        for intent_file in sorted(self.inbox_dir.glob("*.json")):
            try:
                with open(intent_file, "r", encoding="utf-8") as handle:
                    intent = json.load(handle)
                intent_type = intent.get("intent_type")
                if intent_type == "arbitrage_signal":
                    self._process_arbitrage_signal(intent)
                elif intent_type == "ktc_investment_request":
                    self._process_investment_request(intent)
                elif intent_type == "status_query":
                    self._process_status_query(intent)
                elif intent_type == "configuration_update":
                    self._process_configuration_update(intent)
                else:
                    logger.warning("Unknown intent type: %s", intent_type)
                intent_file.rename(processed_dir / intent_file.name)
            except Exception as exc:
                logger.error("Error processing %s: %s", intent_file, exc)
                intent_file.rename(error_dir / intent_file.name)

    def _process_arbitrage_signal(self, intent: Dict[str, Any]) -> None:
        signal = ArbitrageSignal.from_intent(intent.get("payload", {}))
        opportunity = self.engine.evaluate(signal)
        self._log_decision_summary(signal.signal_id, opportunity.decision.value, opportunity.decision_reason)
        self._emit_brp_shadow("arbitrage_signal", signal.signal_id, "success", {"decision": opportunity.decision.value})
        if opportunity.decision == ArbDecision.EXECUTE:
            asyncio.create_task(self._execute_approved_opportunity(opportunity))
        self._write_json(self.outbox_dir / f"result_{signal.signal_id}.json", {
            "signal_id": signal.signal_id,
            "processing_time": _utcnow(),
            "opportunity": asdict(opportunity),
            "engine_state": self.engine.get_performance_metrics(),
        })

    def _process_investment_request(self, intent: Dict[str, Any]) -> None:
        request = InvestmentRequest.from_intent(intent)
        if request.review_required:
            self._write_json(self.outbox_dir / f"investment_{request.intent_id}.json", {
                "intent_id": request.intent_id,
                "status": "pending_review",
                "reason": "KTC routing marked request for human review",
                "request": asdict(request),
                "timestamp": _utcnow(),
            })
            return
        asyncio.create_task(self._execute_investment_request(request))

    async def _execute_approved_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        result = await self.engine.execute_opportunity(opportunity)
        self._emit_brp_shadow("arbitrage_execution", opportunity.opportunity_id, "success" if result.success else "failure", result.to_dict())
        self._write_json(self.outbox_dir / f"execution_{opportunity.opportunity_id}.json", {
            "opportunity_id": opportunity.opportunity_id,
            "execution_time": _utcnow(),
            "result": result.to_dict(),
            "performance_impact": self.engine.get_performance_metrics(),
        })

    async def _execute_investment_request(self, request: InvestmentRequest) -> None:
        result = await self.engine.execute_investment_request(request)
        status = "executed" if result.success else "failed"
        self._emit_brp_shadow("ktc_investment_request", request.intent_id, status, result.to_dict())
        self._write_json(self.outbox_dir / f"investment_{request.intent_id}.json", {
            "intent_id": request.intent_id,
            "status": status,
            "request": asdict(request),
            "result": result.to_dict(),
            "timestamp": _utcnow(),
        })

    def _process_status_query(self, intent: Dict[str, Any]) -> None:
        query_id = intent.get("query_id", str(uuid.uuid4()))
        query_type = intent.get("payload", {}).get("query_type", "metrics")
        if query_type == "configuration":
            response = self.engine.config
        else:
            response = self.engine.get_performance_metrics()
        self._write_json(self.outbox_dir / f"status_response_{query_id}.json", response)

    def _process_configuration_update(self, intent: Dict[str, Any]) -> None:
        updates = intent.get("payload", {})
        _deep_update(self.engine.config, updates)
        if "exchanges" in updates:
            self.engine._init_exchange_connectors()
        self._write_json(
            self.outbox_dir / f"config_update_{intent.get('update_id', 'unknown')}.json",
            {"status": "updated", "timestamp": _utcnow(), "updates_applied": list(updates.keys())},
        )

    def _log_decision_summary(self, signal_id: str, decision: str, reason: str) -> None:
        self._append_jsonl(
            self.base_dir / "decisions.jsonl",
            {"signal_id": signal_id, "decision": decision, "reason": reason, "timestamp": _utcnow()},
        )

    def _emit_brp_shadow(self, action: str, event_id: str, outcome: str, result_data: Dict[str, Any]) -> None:
        try:
            self.brp_bridge.ingest_observation(
                BRPObservation(
                    source_agent="quantumarb_phase4",
                    event_id=event_id,
                    action=action,
                    outcome=outcome,
                    result_data=result_data,
                    mode=BRPMode.SHADOW.value,
                    tags=["quantumarb", "phase4"],
                )
            )
        except Exception as exc:
            logger.debug("BRP shadow emission failed: %s", exc)

    def _check_alerts(self) -> None:
        try:
            for alert in self.engine.monitoring_system.get_active_alerts():
                if alert.severity == AlertSeverity.CRITICAL:
                    logger.warning("CRITICAL alert: %s", alert.message)
                elif alert.severity == AlertSeverity.WARNING:
                    logger.info("Warning alert: %s", alert.message)
        except Exception as exc:
            logger.debug("Alert check failed: %s", exc)

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _append_jsonl(self, path: Path, payload: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")


def register_with_simp(agent_id: str = "quantumarb_phase4") -> bool:
    logger.info("Registering %s with SIMP (file-based runtime)", agent_id)
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="QuantumArb Agent Phase 4")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    if args.register:
        register_with_simp()
    asyncio.run(QuantumArbAgentPhase4(args.poll_interval, args.config).run())


if __name__ == "__main__":
    main()
