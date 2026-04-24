#!/usr/bin/env python3
"""
Market Cognition Training Data Preparation - Tranche 3 (Phase 13)

Transforms gate4_trades.jsonl and phase4_pnl_ledger.jsonl into preference pairs
for market cognition DPO training.

Extracts:
- Regime indicators (volatility, trend, liquidity)
- Strategy allocations
- Execution quality labels

Outputs HuggingFace dataset format with chosen/rejected preference pairs.
"""

import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from itertools import combinations

from datasets import Dataset


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MarketRegime:
    """Market regime classification."""
    regime_type: str  # 'trending', 'ranging', 'high_volatility', 'low_volatility'
    volatility_score: float  # 0.0 - 1.0
    trend_direction: str  # 'bullish', 'bearish', 'neutral'
    liquidity_state: str  # 'high', 'medium', 'low'
    confidence: float = 0.5


@dataclass
class ExecutionMetrics:
    """Execution quality metrics."""
    slippage_bps: float
    fill_rate: float  # 0.0 - 1.0
    timing_score: float  # 0.0 - 1.0
    execution_cost_bps: float


@dataclass
class PreferencePair:
    """DPO preference pair for market cognition."""
    prompt: str
    chosen: str
    rejected: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Data Loading
# ============================================================================

def load_jsonl(path: str) -> List[Dict]:
    """Load JSONL file into list of dicts."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_trades_and_pnl(
    trades_path: str = "logs/gate4_trades.jsonl",
    pnl_path: str = "data/phase4_pnl_ledger.jsonl"
) -> Tuple[List[Dict], List[Dict]]:
    """Load trade and PNL data from JSONL files."""
    trades = load_jsonl(trades_path)
    pnl = load_jsonl(pnl_path)
    return trades, pnl


def group_by_signal(records: List[Dict]) -> Dict[str, List[Dict]]:
    """Group records by signal_id for coherent analysis."""
    signals = defaultdict(list)
    for r in records:
        sig_id = r.get("signal_id", "unknown")
        signals[sig_id].append(r)
    return signals


# ============================================================================
# Regime Detection
# ============================================================================

def calculate_volatility_from_prices(prices: List[float]) -> float:
    """Calculate volatility score from price series. Returns 0.0-1.0."""
    if len(prices) < 3:
        return 0.5
    
    returns = []
    sorted_prices = sorted(prices)
    for i in range(1, len(sorted_prices)):
        if sorted_prices[i-1] > 0:
            ret = abs((sorted_prices[i] - sorted_prices[i-1]) / sorted_prices[i-1])
            returns.append(ret)
    
    if not returns:
        return 0.5
    
    # Normalize: typical crypto vol
    mean_ret = statistics.mean(returns)
    vol_score = min(1.0, mean_ret * 100 / 5.0)
    return vol_score


def detect_trend(prices: List[float]) -> str:
    """Detect trend direction from price series."""
    if len(prices) < 5:
        return "neutral"
    
    # Use last N prices
    recent = prices[-10:] if len(prices) > 10 else prices
    if len(recent) < 3:
        return "neutral"
    
    # Simple linear regression slope
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(recent)
    
    num = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    
    if den == 0:
        return "neutral"
    
    slope_pct = (num / den) / y_mean if y_mean > 0 else 0
    
    if slope_pct > 0.002:
        return "bullish"
    elif slope_pct < -0.002:
        return "bearish"
    return "neutral"


def estimate_liquidity(volume_usd: float, trade_count: int) -> str:
    """Estimate liquidity state based on trade sizes and frequency."""
    if trade_count == 0:
        return "medium"
    
    avg_volume = volume_usd / trade_count if trade_count > 0 else 0
    
    if avg_volume > 50:
        return "high"
    elif avg_volume < 5:
        return "low"
    return "medium"


def classify_regime(
    prices: List[float],
    volume_usd: float,
    trade_count: int
) -> MarketRegime:
    """Classify market regime from price and volume data."""
    vol_score = calculate_volatility_from_prices(prices)
    trend = detect_trend(prices)
    liquidity = estimate_liquidity(volume_usd, trade_count)
    
    # Determine regime type
    if vol_score > 0.6:
        regime_type = "high_volatility"
    elif vol_score > 0.35:
        if trend != "neutral":
            regime_type = "trending"
        else:
            regime_type = "ranging"
    else:
        regime_type = "low_volatility"
    
    confidence = min(1.0, trade_count / 10) if trade_count > 0 else 0.3
    confidence = max(0.3, confidence)
    
    return MarketRegime(
        regime_type=regime_type,
        volatility_score=vol_score,
        trend_direction=trend,
        liquidity_state=liquidity,
        confidence=confidence
    )


# ============================================================================
# Execution Quality Analysis
# ============================================================================

def calculate_execution_metrics(trade: Dict) -> ExecutionMetrics:
    """Calculate execution quality metrics for a trade."""
    requested = trade.get("requested_usd", 0) or 0
    executed = trade.get("executed_usd", 0) or 0
    notional = trade.get("notional_usd", 0) or 0
    
    # Fill rate
    if requested > 0:
        fill_rate = min(1.0, executed / requested)
    elif notional > 0:
        fill_rate = 1.0
    else:
        fill_rate = 1.0
    
    # Slippage estimation
    slippage_bps = 5.0  # base 5 bps
    
    # Timing score
    dry_run = trade.get("dry_run", False)
    timing_score = 1.0 if dry_run else 0.85
    
    # Execution cost
    fees = trade.get("fees_usd")
    if fees and notional > 0:
        execution_cost_bps = (fees / notional) * 10000
    else:
        execution_cost_bps = 1.0
    
    return ExecutionMetrics(
        slippage_bps=slippage_bps,
        fill_rate=fill_rate,
        timing_score=timing_score,
        execution_cost_bps=execution_cost_bps
    )


def score_execution(exec_metrics: ExecutionMetrics) -> float:
    """Calculate overall execution quality score (0-1)."""
    slippage_score = max(0, 1.0 - (exec_metrics.slippage_bps / 50))
    fill_score = exec_metrics.fill_rate
    timing_score = exec_metrics.timing_score
    cost_score = max(0, 1.0 - (exec_metrics.execution_cost_bps / 20))
    
    return (
        slippage_score * 0.35 +
        fill_score * 0.30 +
        timing_score * 0.20 +
        cost_score * 0.15
    )


# ============================================================================
# Strategy Recommendation Generation
# ============================================================================

def generate_strategy_for_regime(regime: MarketRegime, symbol: str) -> str:
    """Generate optimal strategy recommendation based on regime."""
    base_size = {
        "high_volatility": "20%",
        "trending": "30%",
        "ranging": "25%",
        "low_volatility": "35%"
    }.get(regime.regime_type, "25%")
    
    stop_loss = {
        "high_volatility": "1.5%",
        "trending": "3% trailing",
        "ranging": "2%",
        "low_volatility": "None (accumulation)"
    }.get(regime.regime_type, "2%")
    
    order_type = {
        "high_volatility": "limit orders at 1% below market",
        "trending": "market orders with TWAP execution",
        "ranging": "limit orders at range boundaries",
        "low_volatility": "market orders, dollar-cost averaging"
    }.get(regime.regime_type, "limit orders")
    
    risk_note = ""
    if regime.regime_type == "high_volatility":
        risk_note = "Reduce exposure; prioritize capital preservation."
    elif regime.trend_direction == "bearish":
        risk_note = "Consider hedging or reduced long exposure."
    
    return (
        f"[{symbol}] Optimal: {base_size} notional allocation. "
        f"Stop-loss: {stop_loss}. Execution: {order_type}. "
        f"{risk_note}"
    ).strip()


def generate_suboptimal_strategy(regime: MarketRegime, symbol: str) -> str:
    """Generate suboptimal strategy for rejection."""
    bad_sizes = {
        "high_volatility": "50%",
        "trending": "15%",
        "ranging": "40%",
        "low_volatility": "50%"
    }
    
    bad_orders = {
        "high_volatility": "market orders at any price",
        "trending": "tight limits that miss fills",
        "ranging": "market orders breaking out",
        "low_volatility": "aggressive market orders every hour"
    }
    
    warning = {
        "high_volatility": "WARNING: High slippage risk!",
        "trending": "WARNING: Fighting momentum!",
        "ranging": "WARNING: False breakout risk!",
        "low_volatility": "WARNING: Excessive trading costs!"
    }
    
    return (
        f"[{symbol}] Suboptimal: {bad_sizes.get(regime.regime_type, '40%')} notional. "
        f"Execution: {bad_orders.get(regime.regime_type, 'market orders')}. "
        f"{warning.get(regime.regime_type, 'WARNING: Poor risk management!')}"
    ).strip()


def generate_regime_comparison_prompt(
    regime_a: MarketRegime,
    regime_b: MarketRegime,
    symbol_a: str,
    symbol_b: str
) -> str:
    """Generate prompt comparing two market regimes."""
    return f"""Compare market conditions for portfolio allocation:

[{symbol_a}]
- Regime: {regime_a.regime_type}
- Volatility: {regime_a.volatility_score:.2f}
- Trend: {regime_a.trend_direction}
- Liquidity: {regime_a.liquidity_state}

[{symbol_b}]
- Regime: {regime_b.regime_type}
- Volatility: {regime_b.volatility_score:.2f}
- Trend: {regime_b.trend_direction}
- Liquidity: {regime_b.liquidity_state}

Which allocation is risk-adjusted superior?"""


# ============================================================================
# Pair Generation
# ============================================================================

def generate_symbol_pairs(
    trades: List[Dict],
    pnl: List[Dict],
    symbols: List[str]
) -> List[PreferencePair]:
    """Generate preference pairs for individual symbols."""
    pairs = []
    
    # Build price history per symbol
    price_history = {}
    volume_by_symbol = defaultdict(float)
    count_by_symbol = defaultdict(int)
    
    for entry in pnl:
        symbol = entry.get("symbol")
        if symbol:
            if entry.get("entry_px"):
                if symbol not in price_history:
                    price_history[symbol] = []
                price_history[symbol].append(entry["entry_px"])
            notional = entry.get("notional_usd", 0) or 0
            volume_by_symbol[symbol] += notional
            count_by_symbol[symbol] += 1
    
    # Also include executed_usd from trades
    for trade in trades:
        symbol = trade.get("symbol")
        if symbol:
            executed = trade.get("executed_usd", 0) or 0
            volume_by_symbol[symbol] += executed
            count_by_symbol[symbol] += 1
    
    for symbol in symbols:
        prices = price_history.get(symbol, [])
        
        # Skip if no data
        if len(prices) < 2 and count_by_symbol[symbol] < 5:
            # Generate synthetic pairs for learning
            regime = MarketRegime(
                regime_type="ranging",
                volatility_score=0.5,
                trend_direction="neutral",
                liquidity_state="medium",
                confidence=0.5
            )
        else:
            volume = volume_by_symbol.get(symbol, 0)
            count = count_by_symbol.get(symbol, 0)
            regime = classify_regime(prices, volume, count)
        
        optimal = generate_strategy_for_regime(regime, symbol)
        suboptimal = generate_suboptimal_strategy(regime, symbol)
        
        # Build prompt
        prompt = f"""You are the ProjectX Market Cognition System. Analyze market state for {symbol}.

**Regime**: {regime.regime_type.upper()}
**Volatility**: {regime.volatility_score:.2f} ({'HIGH' if regime.volatility_score > 0.6 else 'MEDIUM' if regime.volatility_score > 0.3 else 'LOW'})
**Trend**: {regime.trend_direction.upper()}
**Liquidity**: {regime.liquidity_state.upper()}
**Data Points**: {count_by_symbol.get(symbol, 0)}
**Confidence**: {regime.confidence:.0%}

Recommend optimal strategy allocation considering risk-adjusted returns."""
        
        pair = PreferencePair(
            prompt=prompt,
            chosen=optimal,
            rejected=suboptimal,
            metadata={
                "regime_type": regime.regime_type,
                "volatility_score": regime.volatility_score,
                "trend_direction": regime.trend_direction,
                "liquidity_state": regime.liquidity_state,
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "execution_quality_score": 0.75,
                "trade_count": count_by_symbol.get(symbol, 0),
                "regime_confidence": regime.confidence,
                "pair_type": "single_symbol"
            }
        )
        pairs.append(pair)
    
    return pairs


def generate_cross_asset_pairs(
    symbols: List[str],
    regimes: Dict[str, MarketRegime]
) -> List[PreferencePair]:
    """Generate portfolio allocation preference pairs."""
    pairs = []
    
    # Build comparison prompt
    regime_lines = "\n".join([
        f"- {s}: {regimes[s].regime_type}, vol={regimes[s].volatility_score:.2f}, trend={regimes[s].trend_direction}, liq={regimes[s].liquidity_state}"
        for s in symbols
    ])
    
    prompt = f"""You are the ProjectX Portfolio Allocation System. Determine optimal multi-asset allocation.

**Available Symbols**: {', '.join(symbols)}

**Market Regimes**:
{regime_lines}

Which portfolio allocation maximizes risk-adjusted returns?"""
    
    # Calculate optimal weights based on regime
    weights = {}
    for symbol in symbols:
        r = regimes[symbol]
        base = 1.0 - r.volatility_score * 0.4
        if r.liquidity_state == "high":
            base *= 1.2
        elif r.liquidity_state == "low":
            base *= 0.7
        if r.trend_direction == "bearish":
            base *= 0.8
        weights[symbol] = base
    
    total = sum(weights.values())
    norm_weights = {s: w / total for s, w in weights.items()}
    
    optimal = (
        "Regime-aware allocation: " + 
        " | ".join([f"{s}: {norm_weights[s]*100:.0f}%" for s in symbols]) +
        ". Rebalance on regime change. Reduce high-vol exposure."
    )
    
    suboptimal = (
        "Uniform allocation: " +
        " | ".join([f"{s}: {100/len(symbols):.0f}%" for s in symbols]) +
        ". WARNING: Ignores regime differences!"
    )
    
    pair = PreferencePair(
        prompt=prompt,
        chosen=optimal,
        rejected=suboptimal,
        metadata={
            "regime_type": "cross_asset",
            "volatility_score": statistics.mean(r.volatility_score for r in regimes.values()),
            "trend_direction": "mixed",
            "liquidity_state": "varied",
            "symbol": "PORTFOLIO",
            "timestamp": datetime.now().isoformat(),
            "allocation_type": "regime_aware",
            "pair_type": "cross_asset"
        }
    )
    pairs.append(pair)
    
    return pairs


def generate_regime_comparison_pairs(
    symbols: List[str],
    regimes: Dict[str, MarketRegime]
) -> List[PreferencePair]:
    """Generate pairs comparing different regime conditions."""
    pairs = []
    
    # Generate pairs comparing all symbol combinations
    for sym_a, sym_b in combinations(symbols, 2):
        r_a, r_b = regimes[sym_a], regimes[sym_b]
        
        prompt = generate_regime_comparison_prompt(r_a, r_b, sym_a, sym_b)
        
        # Chosen: higher quality regime
        if r_a.volatility_score < r_b.volatility_score and r_a.liquidity_state != "low":
            chosen = f"Prefer {sym_a}: lower vol ({r_a.volatility_score:.2f}) with {r_a.liquidity_state} liquidity"
            rejected = f"Prefer {sym_b}: higher vol ({r_b.volatility_score:.2f}) with {r_b.liquidity_state} liquidity"
        else:
            chosen = f"Prefer {sym_b}: lower vol ({r_b.volatility_score:.2f}) with {r_b.liquidity_state} liquidity"
            rejected = f"Prefer {sym_a}: higher vol ({r_a.volatility_score:.2f}) with {r_a.liquidity_state} liquidity"
        
        pair = PreferencePair(
            prompt=prompt,
            chosen=chosen,
            rejected=rejected,
            metadata={
                "regime_type": f"{r_a.regime_type}_vs_{r_b.regime_type}",
                "volatility_score": (r_a.volatility_score + r_b.volatility_score) / 2,
                "trend_direction": "mixed",
                "liquidity_state": "varied",
                "symbol": f"{sym_a}_vs_{sym_b}",
                "timestamp": datetime.now().isoformat(),
                "pair_type": "regime_comparison"
            }
        )
        pairs.append(pair)
    
    return pairs


def generate_signal_based_pairs(
    trades: List[Dict],
    pnl: List[Dict],
    symbols: List[str]
) -> List[PreferencePair]:
    """Generate pairs based on signal-level analysis."""
    pairs = []
    
    # Group by signal
    pnl_signals = group_by_signal(pnl)
    
    for sig_id, sig_trades in list(pnl_signals.items())[:10]:  # Limit for dataset size
        if len(sig_trades) < 2:
            continue
        
        # Get symbols in this signal
        sig_symbols = list(set(t.get("symbol") for t in sig_trades if t.get("symbol")))
        if not sig_symbols:
            continue
        
        # Calculate aggregate metrics
        total_notional = sum(t.get("notional_usd", 0) or 0 for t in sig_trades)
        prices = [t["entry_px"] for t in sig_trades if t.get("entry_px")]
        
        # Classify based on signal characteristics
        vol_score = calculate_volatility_from_prices(prices) if prices else 0.5
        trend = detect_trend(prices) if len(prices) >= 3 else "neutral"
        
        if vol_score > 0.6:
            regime_type = "high_volatility"
        elif vol_score > 0.35:
            regime_type = "trending" if trend != "neutral" else "ranging"
        else:
            regime_type = "low_volatility"
        
        liquidity = estimate_liquidity(total_notional, len(sig_trades))
        
        regime = MarketRegime(
            regime_type=regime_type,
            volatility_score=vol_score,
            trend_direction=trend,
            liquidity_state=liquidity,
            confidence=0.7
        )
        
        # Generate prompt
        prompt = f"""Signal {sig_id[:8]}... multi-asset execution analysis:

Total notional: ${total_notional:.2f}
Assets: {', '.join(sig_symbols)}
Volatility: {vol_score:.2f}
Trend: {trend}
Liquidity: {liquidity}

Optimal execution strategy?"""
        
        optimal = generate_strategy_for_regime(regime, "MULTI")
        suboptimal = generate_suboptimal_strategy(regime, "MULTI")
        
        pair = PreferencePair(
            prompt=prompt,
            chosen=optimal,
            rejected=suboptimal,
            metadata={
                "regime_type": regime_type,
                "volatility_score": vol_score,
                "trend_direction": trend,
                "liquidity_state": liquidity,
                "symbol": sig_symbols[0] if sig_symbols else "MULTI",
                "signal_id": sig_id[:16],
                "timestamp": sig_trades[0].get("ts", datetime.now().isoformat()),
                "execution_quality_score": 0.75,
                "pair_type": "signal_based"
            }
        )
        pairs.append(pair)
    
    return pairs


# ============================================================================
# Dataset Creation
# ============================================================================

def create_hf_dataset(pairs: List[PreferencePair]) -> Dataset:
    """Convert preference pairs to HuggingFace dataset format."""
    data = []
    
    for pair in pairs:
        record = {
            "prompt": pair.prompt,
            "chosen": pair.chosen,
            "rejected": pair.rejected,
            "regime_type": pair.metadata.get("regime_type", "unknown"),
            "volatility_score": pair.metadata.get("volatility_score", 0.5),
            "trend_direction": pair.metadata.get("trend_direction", "neutral"),
            "liquidity_state": pair.metadata.get("liquidity_state", "medium"),
            "timestamp": pair.metadata.get("timestamp", ""),
            "symbol": pair.metadata.get("symbol", ""),
        }
        data.append(record)
    
    return Dataset.from_list(data)


def save_dataset(
    dataset: Dataset,
    output_dir: str = "data/quantum_dataset",
    name: str = "market_cognition_tranche3"
):
    """Save dataset to disk in HF format."""
    output_path = Path(output_dir) / name
    output_path.mkdir(parents=True, exist_ok=True)
    
    dataset.save_to_disk(str(output_path))
    
    # Also save as JSONL for inspection
    jsonl_path = output_path / "preference_pairs.jsonl"
    with open(jsonl_path, "w") as f:
        for i in range(len(dataset)):
            f.write(json.dumps(dataset[i]) + "\n")
    
    return output_path


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main execution: load data, generate pairs, save dataset."""
    print("=" * 60)
    print("Market Cognition Training Data - Tranche 3 (Phase 13)")
    print("=" * 60)
    
    # Load data
    print("\n[1/5] Loading trade and PNL data...")
    trades, pnl = load_trades_and_pnl()
    print(f"  - Trades loaded: {len(trades)}")
    print(f"  - PNL entries: {len(pnl)}")
    
    # Extract symbols
    symbols = list(set(
        t.get("symbol", "UNKNOWN") 
        for t in trades + pnl 
        if t.get("symbol")
    ))
    print(f"  - Symbols detected: {symbols}")
    
    # Build regimes for all symbols
    price_history = defaultdict(list)
    volume_by_symbol = defaultdict(float)
    count_by_symbol = defaultdict(int)
    
    for entry in pnl:
        symbol = entry.get("symbol")
        if symbol:
            if entry.get("entry_px"):
                price_history[symbol].append(entry["entry_px"])
            volume_by_symbol[symbol] += entry.get("notional_usd", 0) or 0
            count_by_symbol[symbol] += 1
    
    for trade in trades:
        symbol = trade.get("symbol")
        if symbol:
            volume_by_symbol[symbol] += trade.get("executed_usd", 0) or 0
            count_by_symbol[symbol] += 1
    
    regimes = {}
    for symbol in symbols:
        prices = price_history.get(symbol, [])
        regimes[symbol] = classify_regime(
            prices, 
            volume_by_symbol.get(symbol, 0),
            count_by_symbol.get(symbol, 0)
        )
    
    # Generate all preference pairs
    print("\n[2/5] Generating preference pairs...")
    
    all_pairs = []
    
    # Single symbol pairs
    symbol_pairs = generate_symbol_pairs(trades, pnl, symbols)
    all_pairs.extend(symbol_pairs)
    print(f"  - Single symbol pairs: {len(symbol_pairs)}")
    
    # Cross-asset allocation pairs
    cross_pairs = generate_cross_asset_pairs(symbols, regimes)
    all_pairs.extend(cross_pairs)
    print(f"  - Cross-asset pairs: {len(cross_pairs)}")
    
    # Regime comparison pairs
    comparison_pairs = generate_regime_comparison_pairs(symbols, regimes)
    all_pairs.extend(comparison_pairs)
    print(f"  - Regime comparison pairs: {len(comparison_pairs)}")
    
    # Signal-based pairs
    signal_pairs = generate_signal_based_pairs(trades, pnl, symbols)
    all_pairs.extend(signal_pairs)
    print(f"  - Signal-based pairs: {len(signal_pairs)}")
    
    print(f"  - Total pairs: {len(all_pairs)}")
    
    # Show regime distribution
    regime_counts = defaultdict(int)
    for p in all_pairs:
        regime_counts[p.metadata.get("regime_type", "unknown")] += 1
    print("\n  Regime distribution:")
    for regime, count in sorted(regime_counts.items()):
        print(f"    {regime}: {count}")
    
    # Create dataset
    print("\n[3/5] Creating HuggingFace dataset...")
    dataset = create_hf_dataset(all_pairs)
    print(f"  - Dataset size: {len(dataset)} examples")
    
    # Show sample
    print("\n[4/5] Sample preference pairs:")
    for i in range(min(2, len(dataset))):
        sample = dataset[i]
        print(f"\n  Pair {i+1} [{sample['symbol']}]:")
        print(f"    Regime: {sample['regime_type']}")
        print(f"    Volatility: {sample['volatility_score']:.2f}")
        print(f"    Chosen: {sample['chosen'][:80]}...")
        print(f"    Rejected: {sample['rejected'][:80]}...")
    
    # Save
    print("\n[5/5] Saving dataset...")
    output_path = save_dataset(dataset)
    print(f"  - Saved to: {output_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Dataset Summary:")
    print(f"  - Total pairs: {len(dataset)}")
    print(f"  - Symbols: {symbols}")
    print(f"  - Regime types: {list(set(p.metadata.get('regime_type') for p in all_pairs))}")
    print(f"  - Pair types: {list(set(p.metadata.get('pair_type') for p in all_pairs))}")
    print(f"  - Output: {output_path}")
    print("=" * 60)
    
    return dataset


if __name__ == "__main__":
    main()
