import json
from pathlib import Path

from simp.agents import quantumarb_agent_phase4 as phase4_module
from simp.agents.quantumarb_agent_phase4 import (
    ArbDecision,
    ArbitrageSignal,
    QuantumArbAgentPhase4,
    QuantumArbEnginePhase4,
)
from simp.memory import SystemMemoryStore
from simp.organs.quantumarb.exchange_connector import OrderSide, StubExchangeConnector
from simp.organs.quantumarb.executor import TradeExecutor


class _DummyMemoryStore:
    def __init__(self, *args, **kwargs):
        self.episodes = []

    def add_episode(self, episode):
        self.episodes.append(episode)


def test_executor_blocks_live_trading_without_explicit_enable():
    live_connector = StubExchangeConnector(sandbox=False, simulated_latency_ms=0)
    executor = TradeExecutor(
        exchange_connector=live_connector,
        max_position_size_usd=1000.0,
    )

    result = executor.execute_investment(
        exchange_name="default",
        symbol="BTC-USD",
        side=OrderSide.BUY,
        quantity=0.001,
    )

    assert result.success is False
    assert "Live trading disabled" in result.error_message


def test_executor_executes_cross_venue_arbitrage():
    buy_exchange = StubExchangeConnector(sandbox=True, simulated_latency_ms=0)
    sell_exchange = StubExchangeConnector(sandbox=True, simulated_latency_ms=0)
    buy_exchange.market_data["BTC-USD"] = {
        "bid": 100.0,
        "ask": 100.0,
        "last": 100.0,
        "volume": 100000.0,
    }
    sell_exchange.market_data["BTC-USD"] = {
        "bid": 103.0,
        "ask": 103.0,
        "last": 103.0,
        "volume": 100000.0,
    }

    executor = TradeExecutor(
        exchange_connectors={"cheap": buy_exchange, "rich": sell_exchange},
        max_position_size_usd=50.0,
        max_slippage_bps=50.0,
    )

    opportunity = type(
        "Opportunity",
        (),
        {
            "opportunity_id": "arb-1",
            "position_size_usd": 10.0,
            "execution_plan": {
                "steps": [
                    {
                        "symbol": "BTC-USD",
                        "venue": "cheap",
                        "amount_usd": 10.0,
                    },
                    {
                        "symbol": "BTC-USD",
                        "venue": "rich",
                        "amount_usd": 10.0,
                    },
                ]
            },
        },
    )()

    result = executor.execute_arbitrage(opportunity, opportunity.execution_plan)

    assert result.success is True
    assert len(result.trades) == 2
    assert result.total_pnl_usd > 0


def test_phase4_engine_evaluates_and_executes_with_stub_config(tmp_path, monkeypatch):
    monkeypatch.setattr(phase4_module, "load_active_system_policies", lambda: {})
    config_path = tmp_path / "phase4.json"
    config_path.write_text(
        json.dumps(
            {
                "exchanges": {
                    "venue_a": {"driver": "stub", "sandbox": True, "enabled": True},
                    "venue_b": {"driver": "stub", "sandbox": True, "enabled": True},
                },
                "risk": {
                    "max_position_size_usd": 10.0,
                    "max_daily_loss_usd": 100.0,
                    "min_spread_pct": 0.01,
                    "max_slippage_pct": 0.50,
                    "risk_score_threshold": 0.1,
                },
                "executor": {
                    "max_position_size_usd": 10.0,
                    "max_slippage_bps": 50.0,
                },
                "pnl_ledger_path": str(tmp_path / "pnl.jsonl"),
            }
        )
    )

    engine = QuantumArbEnginePhase4(str(config_path))
    venue_a = engine.exchange_connectors["venue_a"]
    venue_b = engine.exchange_connectors["venue_b"]
    assert isinstance(venue_a, StubExchangeConnector)
    assert isinstance(venue_b, StubExchangeConnector)
    venue_a.simulated_latency_ms = 0
    venue_b.simulated_latency_ms = 0
    venue_a.market_data["BTC-USD"] = {
        "bid": 100.0,
        "ask": 100.0,
        "last": 100.0,
        "volume": 100000.0,
    }
    venue_b.market_data["BTC-USD"] = {
        "bid": 103.0,
        "ask": 103.0,
        "last": 103.0,
        "volume": 100000.0,
    }

    signal = ArbitrageSignal(
        signal_id="sig-1",
        arb_type="cross_venue",
        symbol_a="BTC-USD",
        symbol_b="BTC-USD",
        venue_a="venue_a",
        venue_b="venue_b",
        spread_pct=1.5,
        expected_return_pct=1.5,
        timestamp="2026-04-20T00:00:00",
        confidence=0.9,
    )

    opportunity = engine.evaluate(signal)
    fake_result = type(
        "FakeExecutionResult",
        (),
        {
            "success": True,
            "trades": [
                {
                    "exchange": "venue_a",
                    "filled_quantity": 0.1,
                    "average_price": 100.0,
                    "fees": 0.01,
                    "timestamp": "2026-04-20T00:00:00+00:00",
                    "order_id": "buy-1",
                },
                {
                    "exchange": "venue_b",
                    "filled_quantity": 0.1,
                    "average_price": 103.0,
                    "fees": 0.01,
                    "timestamp": "2026-04-20T00:00:00+00:00",
                    "order_id": "sell-1",
                },
            ],
            "total_pnl_usd": 0.28,
        },
    )()
    monkeypatch.setattr(engine.trade_executor, "execute_arbitrage", lambda *args, **kwargs: fake_result)
    result = __import__("asyncio").run(engine.execute_opportunity(opportunity))

    assert opportunity.decision.value == "execute"
    assert result.success is True
    assert engine.pnl_ledger.get_trade_count() == 1


def test_phase4_engine_rejects_signal_below_policy_quality_floor(tmp_path, monkeypatch):
    config_path = tmp_path / "phase4.json"
    config_path.write_text(
        json.dumps(
            {
                "exchanges": {
                    "venue_a": {"driver": "stub", "sandbox": True, "enabled": True},
                    "venue_b": {"driver": "stub", "sandbox": True, "enabled": True},
                },
                "risk": {
                    "max_position_size_usd": 10.0,
                    "max_daily_loss_usd": 100.0,
                    "min_spread_pct": 0.01,
                    "max_slippage_pct": 0.50,
                    "risk_score_threshold": 0.1,
                },
                "pnl_ledger_path": str(tmp_path / "pnl.jsonl"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        phase4_module,
        "load_active_system_policies",
        lambda: {
            "generated_at": "2026-04-22T00:00:00+00:00",
            "execution_quality": {"enabled": True, "min_quality_score": 0.95},
        },
    )

    engine = QuantumArbEnginePhase4(str(config_path))
    signal = ArbitrageSignal(
        signal_id="sig-low-quality",
        arb_type="cross_venue",
        symbol_a="BTC-USD",
        symbol_b="BTC-USD",
        venue_a="venue_a",
        venue_b="venue_b",
        spread_pct=1.5,
        expected_return_pct=1.5,
        timestamp="2026-04-22T00:00:00",
        confidence=0.9,
    )

    opportunity = engine.evaluate(signal)

    assert opportunity.decision == ArbDecision.REJECT_RISK
    assert "below policy quality floor 0.95" in opportunity.decision_reason

    monkeypatch.setattr(phase4_module, "SystemMemoryStore", _DummyMemoryStore)
    agent = QuantumArbAgentPhase4(poll_interval=0.01, config_path=str(config_path))
    agent.base_dir = tmp_path / "quantumarb_phase4"
    agent.inbox_dir = agent.base_dir / "inbox"
    agent.outbox_dir = agent.base_dir / "outbox"
    agent.base_dir.mkdir(parents=True, exist_ok=True)
    agent.inbox_dir.mkdir(parents=True, exist_ok=True)
    agent.outbox_dir.mkdir(parents=True, exist_ok=True)
    agent.engine = engine
    agent._emit_brp_shadow = lambda *args, **kwargs: None

    agent._process_arbitrage_signal(
        {
            "intent_id": "intent-low-quality",
            "source_agent": "quantum_signal_bridge",
            "payload": {
                "signal_id": "sig-low-quality",
                "arb_type": "cross_venue",
                "symbol_a": "BTC-USD",
                "symbol_b": "BTC-USD",
                "venue_a": "venue_a",
                "venue_b": "venue_b",
                "spread_pct": 1.5,
                "expected_return_pct": 1.5,
                "timestamp": "2026-04-22T00:00:00+00:00",
                "confidence": 0.4,
            },
            "metadata": {
                "lineage": {
                    "bridge_cycle_id": "cycle-7",
                    "plan_id": "plan-9",
                    "qip_trace_id": "trace-1",
                }
            },
        }
    )

    result_path = agent.outbox_dir / "result_sig-low-quality.json"
    assert result_path.exists()
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_payload["policy_state_version"] == "2026-04-22T00:00:00+00:00"
    assert result_payload["lineage"]["bridge_cycle_id"] == "cycle-7"
    assert result_payload["lineage"]["plan_id"] == "plan-9"
    assert result_payload["lineage"]["qip_trace_id"] == "trace-1"
    assert result_payload["opportunity"]["decision"] == "reject_risk"

    decisions_path = agent.base_dir / "decisions.jsonl"
    decisions = [
        json.loads(line)
        for line in decisions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert decisions[-1]["policy_state_version"] == "2026-04-22T00:00:00+00:00"
    assert decisions[-1]["lineage"]["bridge_cycle_id"] == "cycle-7"
    assert decisions[-1]["lineage"]["plan_id"] == "plan-9"
    assert decisions[-1]["lineage"]["qip_trace_id"] == "trace-1"


def test_phase4_agent_records_lineage_and_policy_state_version(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "phase4_config.json"
    config_path.write_text(
        json.dumps(
            {
                "exchanges": {
                    "stub_exec": {
                        "driver": "stub",
                        "sandbox": True,
                        "enabled": True,
                    }
                },
                "monitoring": {"enabled": False},
                "executor": {
                    "allow_live_trading": False,
                    "max_position_size_usd": 10.0,
                    "max_slippage_bps": 50.0,
                },
                "risk": {
                    "max_position_size_usd": 10.0,
                    "min_spread_pct": 10.0,
                    "max_slippage_pct": 0.50,
                    "risk_score_threshold": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        phase4_module,
        "load_active_system_policies",
        lambda: {
            "generated_at": "2026-04-22T01:02:03+00:00",
            "execution_quality": {"enabled": True, "min_quality_score": 0.1},
        },
    )

    agent = QuantumArbAgentPhase4(poll_interval=0.01, config_path=str(config_path))
    agent.base_dir = tmp_path / "quantumarb_phase4"
    agent.inbox_dir = agent.base_dir / "inbox"
    agent.outbox_dir = agent.base_dir / "outbox"
    agent.inbox_dir.mkdir(parents=True, exist_ok=True)
    agent.outbox_dir.mkdir(parents=True, exist_ok=True)
    agent.system_memory_store = SystemMemoryStore(str(tmp_path / "memory.sqlite3"))

    intent = {
        "intent_id": "intent-123",
        "source_agent": "quantum_signal_bridge",
        "payload": {
            "signal_id": "sig-lineage",
            "arb_type": "cross_venue",
            "symbol_a": "BTC-USD",
            "symbol_b": "BTC-USD",
            "venue_a": "stub_exec",
            "venue_b": "stub_exec",
            "spread_pct": 1.0,
            "expected_return_pct": 1.0,
            "confidence": 0.8,
        },
        "metadata": {
            "plan_id": "plan-42",
            "qip_trace_id": "trace-7",
            "lineage": {"upstream": "qip"},
        },
    }

    agent._process_arbitrage_signal(intent)

    result_path = agent.outbox_dir / "result_sig-lineage.json"
    assert result_path.exists()
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_payload["policy_state_version"] == "2026-04-22T01:02:03+00:00"
    assert result_payload["lineage"]["plan_id"] == "plan-42"
    assert result_payload["lineage"]["qip_trace_id"] == "trace-7"
    assert result_payload["lineage"]["upstream"] == "qip"

    decisions_path = agent.base_dir / "decisions.jsonl"
    decisions = [json.loads(line) for line in decisions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert decisions[-1]["policy_state_version"] == "2026-04-22T01:02:03+00:00"
    assert decisions[-1]["lineage"]["plan_id"] == "plan-42"
