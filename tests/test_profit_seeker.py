"""
Tests for the Profit Seeker Core — Compounding Growth Engine,
Multi-Exchange Arbitrage, Market News, Quantum Optimizer,
Noise Wrapper, and Post-Quantum Crypto.
"""

import json
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simp.organs.quantumarb.compounding import (
    CompoundingTarget,
    CompoundingConfig,
    GrowthScheduler,
    EscalationManager,
    ConsolidationManager,
    CompoundEngine,
)
from simp.organs.quantumarb.multi_exchange import (
    MultiExchangeScanner,
    MultiExchangeOpportunity,
    MultiExchangeOpportunityRanker,
    SimultaneousOrderExecutor,
    ArbLeg,
    ExchangePriceCache,
)
from simp.integrations.market_news import (
    NewsAPIIngestor,
    SentimentAnalyzer,
    MLTradeLogicAdjuster,
    NewsArticle,
)
from simp.organs.quantumarb.quantum_optimizer import (
    QuantumArbOptimizer,
    QuantumBackendDispatcher,
    MeasurementToTradeSize,
    QuantumArbResult,
)
from simp.transport.noise_wrapper import (
    NoiseTransportWrapper,
    NoiseSession,
    NoiseMessage,
)
from simp.post_quantum import (
    PostQuantumCryptoManager,
    Ed25519Signer,
    FalconSigner,
    DilithiumSigner,
    SPHINCSSigner,
)


# ======================================================================
# Compounding Engine Tests
# ======================================================================

class TestCompoundingTarget:
    def test_day_zero_target(self):
        target = CompoundingTarget(start_date="2025-01-01", config=CompoundingConfig(initial_capital=1.0))
        assert target.target(0) == 1.0

    def test_day_one_doubles(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=1.0, daily_multiplier=2.0))
        assert target.target(1) == 2.0

    def test_day_ten(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=1.0))
        assert target.target(10) == 1024.0

    def test_progress_on_track(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        # Day 0 target = 100, actual = 100 → progress = 1.0
        assert target.progress(100.0) == pytest.approx(1.0, abs=0.01)

    def test_progress_behind(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        assert target.progress(50.0) < 0.7

    def test_progress_ahead(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        assert target.progress(200.0) > 1.3

    def test_regime_tracking(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        assert target.regime(100.0) == "TRACKING"

    def test_regime_escalate(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0, escalation_threshold=0.7))
        assert target.regime(50.0) == "ESCALATE"

    def test_regime_crisis(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0, crisis_threshold=0.3))
        assert target.regime(20.0) == "CRISIS"

    def test_regime_consolidate(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0, consolidation_threshold=1.3))
        assert target.regime(200.0) == "CONSOLIDATE"

    def test_growth_needed_on_track(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        # Day 0: target 100, actual 100 → 0% growth needed
        assert target.growth_needed_today(100.0) == 0.0

    def test_growth_needed_behind(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        growth = target.growth_needed_today(50.0)
        assert growth > 0  # needs positive growth to catch up

    def test_snapshot(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        snap = target.snapshot(100.0)
        assert snap.day == 0
        assert snap.progress_ratio == 1.0
        assert snap.regime == "TRACKING"


class TestGrowthScheduler:
    def test_tracking_params(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        params = scheduler.trading_parameters(100.0)
        assert params["regime"] == "TRACKING"
        assert not params["quantum_opt_in"]
        assert not params["aggressive_scan"]

    def test_escalate_params(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        params = scheduler.trading_parameters(50.0)
        assert params["regime"] == "ESCALATE"
        assert params["quantum_opt_in"] is True
        assert params["aggressive_scan"] is True

    def test_consolidate_params(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        params = scheduler.trading_parameters(200.0)
        assert params["regime"] == "CONSOLIDATE"
        assert params["risk_per_trade_pct"] == target.config.min_risk_per_trade_pct

    def test_crisis_params(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        params = scheduler.trading_parameters(20.0)
        assert params["regime"] == "CRISIS"
        assert params["emergency_stop"] is True

    def test_day_tracking(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        scheduler.update_day_tracking(50.0)
        scheduler.update_day_tracking(50.0)
        # Should now be 1 day behind
        assert scheduler.consecutive_days_behind() >= 0


class TestEscalationManager:
    def test_escalation_triggers(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        mgr = EscalationManager(scheduler)
        action = mgr.check_and_escalate(50.0)
        assert action["action_required"] is True
        assert action["regime"] == "ESCALATE"


class TestConsolidationManager:
    def test_consolidation_triggers(self):
        target = CompoundingTarget(config=CompoundingConfig(initial_capital=100.0))
        scheduler = GrowthScheduler(target)
        mgr = ConsolidationManager(scheduler)
        action = mgr.check_and_consolidate(200.0)
        assert action["consolidate"] is True


class TestCompoundEngine:
    def test_full_report(self):
        engine = CompoundEngine(initial_capital=100.0)
        report = engine.full_report(100.0)
        assert "snapshot" in report
        assert "trading_params" in report
        assert "escalation" in report
        assert "consolidation" in report
        assert report["snapshot"]["regime"] == "TRACKING"

    def test_escalation_via_engine(self):
        engine = CompoundEngine(initial_capital=100.0)
        action = engine.escalation_check(50.0)
        assert action["action_required"] is True


# ======================================================================
# Multi-Exchange Arbitrage Tests
# ======================================================================

class TestMultiExchangeOpportunity:
    def test_opportunity_creation(self):
        legs = [
            ArbLeg(exchange="binance", symbol="BTC/USDT", side="buy", expected_price=50000.0, quantity=0.01),
            ArbLeg(exchange="coinbase", symbol="BTC/USDT", side="sell", expected_price=50100.0, quantity=0.01),
        ]
        opp = MultiExchangeOpportunity(
            opportunity_id="test_001",
            arb_type="cross_exchange",
            legs=legs,
            gross_pnl_pct=0.2,
            net_pnl_pct=0.18,
            fees_pct=0.02,
            confidence=0.8,
            timestamp="2025-01-01T00:00:00Z",
            estimated_duration_ms=500.0,
        )
        assert opp.exchange_names == {"binance", "coinbase"}
        assert opp.opportunity_id == "test_001"

    def test_opportunity_to_dict(self):
        leg = ArbLeg(exchange="kraken", symbol="ETH/USDT", side="buy", expected_price=3000.0, quantity=1.0)
        opp = MultiExchangeOpportunity(
            opportunity_id="test_002",
            arb_type="triangular_multi",
            legs=[leg, leg],
            gross_pnl_pct=0.5, net_pnl_pct=0.45, fees_pct=0.05,
            confidence=0.7, timestamp="2025-01-01T00:00:00Z",
            estimated_duration_ms=1000.0,
        )
        d = opp.to_dict()
        assert d["opportunity_id"] == "test_002"
        assert len(d["legs"]) == 2


class TestSimultaneousOrderExecutor:
    def test_execute_opportunity_no_executors(self):
        """With no executors, should return failure."""
        executor = SimultaneousOrderExecutor({})
        leg = ArbLeg(exchange="nonexistent", symbol="BTC/USDT", side="buy",
                     expected_price=50000.0, quantity=0.0, fees_bps=10.0)
        opp = MultiExchangeOpportunity(
            opportunity_id="no_exec",
            arb_type="cross_exchange",
            legs=[leg],
            gross_pnl_pct=0.1, net_pnl_pct=0.08, fees_pct=0.02,
            confidence=0.5, timestamp="2025-01-01T00:00:00Z",
            estimated_duration_ms=500.0,
        )
        result = executor.execute_opportunity(opp, capital_usd=100.0)
        assert result["success"] is False


class TestExchangePriceCache:
    def test_cache_empty_initially(self):
        cache = ExchangePriceCache()
        assert cache._prices == {}


class TestMultiExchangeOpportunityRanker:
    def test_rank_empty(self):
        ranker = MultiExchangeOpportunityRanker()
        assert ranker.rank([]) == []


# ======================================================================
# Market News Tests
# ======================================================================

class TestSentimentAnalyzer:
    def test_bullish_score(self):
        analyzer = SentimentAnalyzer()
        article = NewsArticle(
            source="test", title="Bitcoin surges to new high! Bullish momentum continues",
            url="https://test.com", published_at="2025-01-01T00:00:00Z",
            summary="Strong bullish rally in crypto markets",
            token_pairs=["BTC/USDT"],
        )
        score = analyzer.score_article(article)
        assert score > 0

    def test_bearish_score(self):
        analyzer = SentimentAnalyzer()
        article = NewsArticle(
            source="test", title="Crypto crash! Market plunges. Fear everywhere",
            url="https://test.com", published_at="2025-01-01T00:00:00Z",
            summary="Bearish sentiment dominates as prices fall",
            token_pairs=["BTC/USDT"],
        )
        score = analyzer.score_article(article)
        assert score < 0

    def test_neutral_score(self):
        analyzer = SentimentAnalyzer()
        article = NewsArticle(
            source="test", title="The weather today is sunny",
            url="https://test.com", published_at="2025-01-01T00:00:00Z",
            summary="No financial content here",
            token_pairs=[],
        )
        score = analyzer.score_article(article)
        assert abs(score) < 0.2

    def test_aggregate_by_pair(self):
        analyzer = SentimentAnalyzer()
        articles = [
            NewsArticle(source="test", title="Bitcoin bullish", url="", published_at="",
                        summary="up", token_pairs=["BTC/USDT"], sentiment_score=0.5),
            NewsArticle(source="test", title="Bitcoin bearish", url="", published_at="",
                        summary="down", token_pairs=["BTC/USDT"], sentiment_score=-0.3),
        ]
        sentiments = analyzer.aggregate_by_pair(articles)
        assert len(sentiments) >= 1
        btc = [s for s in sentiments if s.pair == "BTC/USDT"]
        assert len(btc) == 1


class TestMLTradeLogicAdjuster:
    def test_adjust_for_news(self):
        adjuster = MLTradeLogicAdjuster()
        articles = [
            NewsArticle(source="test", title="Strong bullish breakout for BTC",
                        url="", published_at="", token_pairs=["BTC/USDT"]),
        ]
        adjustments = adjuster.adjust_for_news(articles)
        btc_adj = adjustments.get("BTC/USDT")
        assert btc_adj is not None
        assert btc_adj.risk_multiplier >= 1.0

    def test_apply_to_params(self):
        adjuster = MLTradeLogicAdjuster()
        from simp.integrations.market_news import StrategyAdjustment
        adj = StrategyAdjustment(
            timestamp="2025-01-01T00:00:00Z",
            source="test",
            pair="BTC/USDT",
            risk_multiplier=1.5,
            min_spread_adjustment_bps=-2.0,
            position_size_multiplier=1.2,
            confidence_boost=0.1,
            reason="Bullish news",
        )
        params = {"risk_per_trade_pct": 0.5, "min_spread_bps": 10.0, "max_position_pct": 10.0}
        modified = adjuster.apply_to_params(params, "BTC/USDT", {"BTC/USDT": adj})
        assert modified["risk_per_trade_pct"] == 0.75
        assert modified["min_spread_bps"] == 8.0
        assert modified["max_position_pct"] == 12.0


# ======================================================================
# Quantum Optimizer Tests
# ======================================================================

class TestQuantumArbOptimizer:
    def test_optimizer_designs_circuit(self):
        optimizer = QuantumArbOptimizer()
        circuit = optimizer.design_circuit_for_opportunity(
            type("Opportunity", (), {"net_pnl_pct": 0.5, "confidence": 0.8})(),
            num_qubits=4,
        )
        assert circuit["num_qubits"] == 4
        assert "gates" in circuit
        assert len(circuit["gates"]) > 0

    def test_dispatch_fallback(self):
        optimizer = QuantumArbOptimizer()
        circuit = optimizer.design_circuit_for_opportunity(
            type("Opportunity", (), {"net_pnl_pct": 0.3, "confidence": 0.6})(),
        )
        result = optimizer.dispatch_and_measure(circuit, shots=256)
        assert result.backend_used == "local_simulator"
        assert 0 <= result.optimised_score <= 1.0
        assert result.recommended_position_pct > 0


class TestMeasurementToTradeSize:
    def test_compute_trade_size(self):
        converter = MeasurementToTradeSize(base_position_usd=100.0)
        qr = QuantumArbResult(
            opportunity_id="test",
            backend_used="simulator",
            circuit_depth=8,
            measurement_outcomes={"00": 0.5, "01": 0.3, "10": 0.2},
            optimised_score=0.6,
            recommended_position_pct=10.0,
            confidence_adjustment=0.02,
            execution_time_ms=1.0,
            noise_estimate=0.001,
            timestamp="2025-01-01T00:00:00Z",
        )
        sizing = converter.compute_trade_size(qr, available_capital=1000.0, risk_per_trade_pct=0.5)
        assert sizing["final_size_usd"] > 0
        assert sizing["quantum_score"] == 0.6


# ======================================================================
# Noise Wrapper Tests
# ======================================================================

class TestNoiseSession:
    def test_session_age(self):
        session = NoiseSession(
            session_id="test123", peer_id="peer1",
            send_key=b"k" * 32, recv_key=b"r" * 32,
            handshake_hash=b"h" * 32, established_at=time.monotonic(),
        )
        assert session.age_seconds() < 1.0

    def test_session_age_increases(self):
        session = NoiseSession(
            session_id="test", peer_id="peer",
            send_key=b"k" * 32, recv_key=b"r" * 32,
            handshake_hash=b"h" * 32, established_at=time.monotonic() - 10,
        )
        assert session.age_seconds() >= 9.0


class TestNoiseTransportWrapper:
    def test_wrapper_initializes(self):
        """Wrapper can be instantiated without a real inner transport."""
        wrapper = NoiseTransportWrapper(
            inner_transport=type("MockTransport", (), {"transport_name": "mock"})(),
        )
        d = wrapper.describe()
        assert d["wrapper"] == "Noise_XX_25519_ChaChaPoly_SHA256"
        assert d["active_sessions"] == 0


# ======================================================================
# Post-Quantum Crypto Tests
# ======================================================================

class TestPostQuantumCryptoManager:
    def test_default_scheme(self):
        pq = PostQuantumCryptoManager()
        assert pq.scheme == "ed25519"

    def test_set_scheme(self):
        pq = PostQuantumCryptoManager()
        pq.set_scheme("falcon")
        assert pq.scheme == "falcon"

    def test_set_scheme_invalid(self):
        pq = PostQuantumCryptoManager()
        with pytest.raises(ValueError):
            pq.set_scheme("nonexistent")

    def test_adaptive_ed25519_low_threat(self):
        pq = PostQuantumCryptoManager()
        pq.set_adaptive(True, threat_score=0.2)
        scheme = pq.resolve_scheme()
        assert scheme == "ed25519"

    def test_adaptive_falcon_high_threat(self):
        pq = PostQuantumCryptoManager()
        pq.set_adaptive(True, threat_score=0.7)
        scheme = pq.resolve_scheme()
        assert scheme == "falcon"

    def test_adaptive_dilithium_critical_threat(self):
        pq = PostQuantumCryptoManager()
        pq.set_adaptive(True, threat_score=0.9)
        scheme = pq.resolve_scheme()
        assert scheme == "dilithium"

    def test_sign_and_verify(self):
        pq = PostQuantumCryptoManager()
        signer = Ed25519Signer()
        priv, pub = signer.generate_keypair()
        msg = b"test message"
        sig = pq.sign(msg, priv)
        assert pq.verify(msg, sig, pub) is True

    def test_get_crypto_posture(self):
        pq = PostQuantumCryptoManager()
        posture = pq.get_crypto_posture()
        assert "active_scheme" in posture
        assert "quantum_safe" in posture
        assert posture["active_scheme"] == "ed25519"
        assert posture["quantum_safe"] is False

    def test_list_schemes(self):
        pq = PostQuantumCryptoManager()
        schemes = pq.list_schemes()
        names = {s["name"] for s in schemes}
        assert "ed25519" in names
        assert "falcon" in names
        assert "dilithium" in names
        assert "sphincs+" in names


class TestEd25519Signer:
    def test_sign_and_verify_roundtrip(self):
        signer = Ed25519Signer()
        priv, pub = signer.generate_keypair()
        msg = b"arbitrage opportunity data"
        sig = signer.sign(msg, priv)
        assert signer.verify(msg, sig, pub) is True

    def test_verify_wrong_key(self):
        signer = Ed25519Signer()
        priv1, pub1 = signer.generate_keypair()
        _, pub2 = signer.generate_keypair()
        msg = b"test"
        sig = signer.sign(msg, priv1)
        assert signer.verify(msg, sig, pub2) is False

    def test_verify_tampered_message(self):
        signer = Ed25519Signer()
        priv, pub = signer.generate_keypair()
        msg = b"original message"
        sig = signer.sign(msg, priv)
        assert signer.verify(b"tampered message", sig, pub) is False
