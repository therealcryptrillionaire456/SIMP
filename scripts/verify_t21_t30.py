"""
Verify T21-T30 modules are importable and functional.
"""
import os, sys, time, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── T21 ──
from simp.organs.quantumarb.liquidity_scorer import LiquidityScorer, LIQUIDITY_SCORER
scorer = LiquidityScorer(data_dir=tempfile.mkdtemp())
scorer.record_slippage('coinbase', 'BTC-USD', 1.5)
score = scorer.score_venue('BTC-USD', 'coinbase', bid_depth=5000000, ask_depth=5000000, spread_bps=1.0)
assert score.composite > 0, f"Expected positive composite, got {score.composite}"
print(f"T21 ✅  LiquidityScorer score={score.composite:.4f}")

# ── T22 ──
from simp.organs.quantumarb.partial_fill_rollback import PartialFillRollbackHandler, PartialFillConfig, PartialFillAction
handler = PartialFillRollbackHandler(log_dir=tempfile.mkdtemp())
event = handler.handle_partial_fill('tx_test', 0, 'coinbase', 'BTC-USD', 'buy', 1.0, 0.5)
assert event.action in ('accepted', 'retrying', 'unwinding', 'timeout')
print(f"T22 ✅  PartialFillRollbackHandler action={event.action}")

# ── T23 ──
from simp.organs.quantumarb.fee_tier_negotiation import FeeTierNegotiator, FeeTier
negotiator = FeeTierNegotiator(data_dir=tempfile.mkdtemp())
negotiator.record_volume('kraken', 500000)
profile = negotiator.get_profile('kraken')
assert profile is not None and profile.current_tier is not None
print(f"T23 ✅  FeeTierNegotiator kraken tier={profile.current_tier.tier_name}")

# ── T24 ──
from simp.organs.quantumarb.time_weighted_sizing import TimeWeightedPositionSizer, TimeWeightConfig
sizer = TimeWeightedPositionSizer()
ts_fresh = time.time()
assert sizer.compute_multiplier(ts_fresh) == 1.0
assert sizer.is_fresh(ts_fresh)
assert sizer.is_stale(time.time() - 360)
print(f"T24 ✅  TimeWeightedPositionSizer fresh_mult=1.0")

# ── T25 ──
from simp.organs.quantumarb.var_alert_manager import VaRAlertManager, VaRAlertConfig, get_var_alert_manager
from simp.organs.quantumarb.risk_reporter import RiskReporter
reporter = RiskReporter()
mgr = VaRAlertManager(risk_reporter=reporter, alert_dir=tempfile.mkdtemp())
stats = mgr.get_alert_summary()
assert "total_alerts" in stats
print(f"T25 ✅  VaRAlertManager summary={stats['total_alerts']} alerts")

# ── T26 ──
from simp.organs.quantumarb.triangular_path_optimizer import TriangularPathOptimizer
optimizer = TriangularPathOptimizer(data_dir=tempfile.mkdtemp())
optimizer.register_pairs('coinbase', ['BTC-USD', 'ETH-USD', 'SOL-USD'])
optimizer.update_prices('coinbase', {'BTC-USD': 65000.0, 'ETH-USD': 3500.0, 'SOL-USD': 150.0})
paths = optimizer.find_paths('coinbase')
print(f"T26 ✅  TriangularPathOptimizer found {len(paths)} paths")

# ── T27 ──
from simp.organs.quantumarb.strategy_switcher import StrategySwitcher, StrategyConfig, StrategyMode, DEFAULT_STRATEGIES
from simp.organs.quantumarb.regime_detector import RegimeDetector
detector = RegimeDetector()
switcher = StrategySwitcher(regime_detector=detector, log_dir=tempfile.mkdtemp())
for i in range(200):
    detector.update_prices({'BTC-USD': 50000.0 + i * 0.5})
mode, config = switcher.evaluate_and_switch('BTC-USD')
assert config.max_position_usd > 0
print(f"T27 ✅  StrategySwitcher mode={mode}")

# ── T28 ──
from simp.organs.quantumarb.audit_trail import AuditTrail, AuditEntry, get_audit_trail
trail = AuditTrail(log_dir=tempfile.mkdtemp())
entry = trail.record_execution({
    'execution_id': 'exec_001', 'asset': 'BTC', 'quantity': 0.001,
    'price_usd': 65000.0, 'side': 'buy', 'venue': 'coinbase',
    'fees_usd': 0.65, 'pnl_usd': 1.50,
})
assert trail.verify_integrity(), "Hash chain integrity check failed"
print(f"T28 ✅  AuditTrail entry_id={entry.entry_id[:16]} integrity=True")

# ── T29 ──
from simp.organs.quantumarb.latency_sla import LatencySLAEnforcer, PathSLARegistration, CircuitBreakerState
from simp.organs.quantumarb.latency_profiler import LatencyProfiler
profiler = LatencyProfiler(profiles_dir=tempfile.mkdtemp())
sla = LatencySLAEnforcer(profiler=profiler, data_dir=tempfile.mkdtemp())
sla.register_path('price_fetch', sla_target_ms=500)
for i in range(5):
    with profiler.start_span('price_fetch', target_ms=500) as span:
        time.sleep(0.01)
violations = sla.check_all_paths()
assert sla.is_path_allowed('price_fetch')
print(f"T29 ✅  LatencySLAEnforcer violations={len(violations)}")

# ── T30 ──
from simp.organs.quantumarb.drift_detector import DriftDetector, BacktestBaseline, DriftConfig, get_drift_detector
baseline = BacktestBaseline(
    strategy_name='quantumarb', regime='all', sharpe_ratio=1.5,
    sortino_ratio=2.0, win_rate=0.65, profit_factor=2.5,
    max_drawdown=0.10, avg_trade_return_pct=0.5, sample_size=500,
)
detector = DriftDetector(backtest_baselines={'quantumarb': baseline}, data_dir=tempfile.mkdtemp())
for i in range(25):
    detector.record_live_metrics('quantumarb', sharpe_ratio=0.8, win_rate=0.40, num_trades=20 + i)
result = detector.check_drift('quantumarb')
assert result is not None
print(f"T30 ✅  DriftDetector drifting={result.is_drifting} score={result.drift_score:.4f} throttle={result.throttle_multiplier:.4f}")

print()
print("=" * 60)
print("ALL T21-T30 MODULES VERIFIED SUCCESSFULLY")
print("=" * 60)
