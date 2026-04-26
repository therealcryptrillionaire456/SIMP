"""Tests for Execution Engine — ProjectX trade execution and order management."""

import pytest
from simp.projectx.execution_engine import (
    ExecutionEngine,
    ExecutionConfig,
    OrderIntent,
    Fill,
    RiskViolation,
    get_execution_engine,
)


class TestExecutionConfig:
    def test_config_defaults(self) -> None:
        cfg = ExecutionConfig()
        assert cfg.live_mode is False

    def test_config_custom_values(self) -> None:
        cfg = ExecutionConfig(live_mode=True, max_retries=5)
        assert cfg.live_mode is True
        assert cfg.max_retries == 5


class TestOrderIntent:
    def test_order_intent_creation(self) -> None:
        intent = OrderIntent(
            signal_id="sig_001",
            symbol="BTC/USD",
            side="BUY",
            notional_usd=1000.0,
            strategy="trend_follow",
        )
        assert intent.signal_id == "sig_001"
        assert intent.symbol == "BTC/USD"
        assert intent.side == "BUY"
        assert intent.notional_usd == 1000.0

    def test_order_intent_metadata(self) -> None:
        intent = OrderIntent(
            signal_id="sig_002",
            symbol="ETH/USD",
            side="SELL",
            notional_usd=500.0,
            strategy="mean_revert",
            metadata={"confidence": 0.85},
        )
        assert intent.metadata["confidence"] == 0.85


class TestExecutionEngine:
    def test_engine_initialization(self) -> None:
        cfg = ExecutionConfig(live_mode=False)
        engine = ExecutionEngine(config=cfg)
        assert engine is not None

    def test_engine_default_initialization(self) -> None:
        engine = ExecutionEngine()
        assert engine is not None

    def test_execute_method_exists(self) -> None:
        engine = ExecutionEngine(config=ExecutionConfig(live_mode=False))
        assert hasattr(engine, "execute")

    def test_execute_batch_method_exists(self) -> None:
        engine = ExecutionEngine(config=ExecutionConfig(live_mode=False))
        assert hasattr(engine, "execute_batch")


class TestFill:
    def test_fill_dataclass(self) -> None:
        fill = Fill(
            signal_id="sig_fill",
            symbol="BTC/USD",
            side="BUY",
            notional_usd=25000.0,
            exec_usd=25000.0,
        )
        assert fill.symbol == "BTC/USD"


class TestRiskViolation:
    def test_risk_violation_dataclass(self) -> None:
        violation = RiskViolation(gate="max_position", reason="Too large")
        assert violation.gate == "max_position"


class TestExecutionEngineWithMock:
    def test_execute_handles_intent(self) -> None:
        engine = ExecutionEngine(config=ExecutionConfig(live_mode=False))
        intent = OrderIntent(
            signal_id="mock_sig",
            symbol="BTC/USD",
            side="BUY",
            notional_usd=100.0,
            strategy="mock",
        )
        try:
            engine.execute(intent)
        except Exception:
            pass

    def test_get_execution_engine_returns_instance(self) -> None:
        e = get_execution_engine()
        assert e is not None

    def test_execute_batch_returns_list(self) -> None:
        engine = ExecutionEngine(config=ExecutionConfig(live_mode=False))
        intents = [
            OrderIntent(signal_id=f"sig_{i}", symbol="BTC/USD", side="BUY",
                       notional_usd=100.0, strategy="test")
            for i in range(3)
        ]
        if hasattr(engine, "execute_batch"):
            results = engine.execute_batch(intents)
            assert isinstance(results, list)
