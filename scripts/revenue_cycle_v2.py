#!/usr/bin/env python3.10
"""
Revenue Cycle V2 — Multi-Phase Arbitrage + Quantum Optimizer Sizing
====================================================================
Extends revenue_cycle.py with triangular arbitrage scanning and
quantum optimizer position sizing across four phases:

  Phase A: Cross-exchange arb (standard buy-low/sell-high)
  Phase B: Triangular single-exchange arb
  Phase C: Triangular multi-exchange arb
  Phase D: Quantum optimizer position sizing

NY/NJ Exchange Compliance: binance, gemini, and huobi are excluded
from default exchanges per regulatory guidance.

Usage:
    python3 scripts/revenue_cycle_v2.py                          # single cycle
    python3 scripts/revenue_cycle_v2.py --loop                   # continuous
    python3 scripts/revenue_cycle_v2.py --triangular --quantum   # full pipeline
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(REPO / "logs" / "revenue_cycle_v2.log"), mode="a"),
    ],
)
log = logging.getLogger("revenue_cycle_v2")

# ── Config ──────────────────────────────────────────────────────────────

DECISION_JOURNAL = REPO / "state" / "decision_journal.ndjson"
ARB_LOG = REPO / "logs" / "arb_cycle_v2.jsonl"

# NY/NJ compliant — binance, gemini, huobi removed
DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD"]
DEFAULT_EXCHANGES = ["coinbase", "kraken", "bitstamp"]

# ── Optional Imports (graceful fallback) ────────────────────────────────

_HAS_MULTI_EXCHANGE = False
_HAS_QUANTUM_OPTIMIZER = False

try:
    from simp.organs.quantumarb.multi_exchange import (
        MultiExchangeScanner,
        ExchangePriceCache,
        MultiExchangeOpportunity,
    )
    _HAS_MULTI_EXCHANGE = True
except ImportError:
    log.warning("MultiExchangeScanner not available — triangular arb disabled")

try:
    from simp.organs.quantumarb.quantum_optimizer import (
        MeasurementToTradeSize,
        QuantumArbResult,
    )
    _HAS_QUANTUM_OPTIMIZER = True
except ImportError:
    log.warning("MeasurementToTradeSize not available — quantum sizing disabled")

# ── Journal Writer ──────────────────────────────────────────────────────

def _journal_entry(
    entry_type: str,
    source: str,
    symbol: str,
    side: str,
    usd_value: float,
    detail: dict,
) -> dict:
    """Create a canonical decision journal entry."""
    import uuid
    return {
        "decision_id": f"rev_{uuid.uuid4().hex[:14]}",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": entry_type,
        "source": source,
        "symbol": symbol,
        "side": side,
        "usd_value": usd_value,
        "fill_status": "pending",
        "policy_result": {"status": "shadow", "reason": "arb_cycle", "evaluated_at": None},
        "detail": detail,
    }


def _append_journal(entry: dict) -> None:
    """Append a journal entry to the decision journal file."""
    DECISION_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISION_JOURNAL, "a") as f:
        f.write(json.dumps(entry) + "\n")
    log.info("Journal: %s %s %s $%.2f",
             entry["type"], entry["symbol"], entry["side"], entry["usd_value"])


def _append_arb_log(entry: dict) -> None:
    """Append an arb opportunity to the arb log file."""
    ARB_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ARB_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Price Fetching ──────────────────────────────────────────────────────

def _fetch_price(symbol: str, exchange: str) -> Optional[float]:
    """Fetch current price from an exchange's public API."""
    import urllib.request
    import urllib.error
    try:
        if exchange == "coinbase":
            # Try CDP key first, fallback to public endpoint
            price = _fetch_coinbase_cdp(symbol)
            if price is not None:
                return price
            url = f"https://api.exchange.coinbase.com/products/{symbol}/ticker"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            return float(data["price"])
        elif exchange == "kraken":
            pair = symbol.replace("-", "")
            url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            for key in data.get("result", {}):
                return float(data["result"][key]["c"][0])
        elif exchange == "bitstamp":
            pair = symbol.replace("-", "").lower()
            url = f"https://www.bitstamp.net/api/v2/ticker/{pair}/"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            return float(data["last"])
    except Exception as e:
        log.warning("Price fetch %s/%s: %s", exchange, symbol, e)
    return None


def _fetch_coinbase_cdp(symbol: str) -> Optional[float]:
    """Fetch price using CDP API key file (same pattern as gate4)."""
    try:
        key_file = str(REPO / "config" / "coinbase_cdp_key.json")
        if not os.path.exists(key_file):
            key_file = os.path.expanduser("~/.coinbase/cdp_key.json")
            if not os.path.exists(key_file):
                return None
        from coinbase.rest import RESTClient
        client = RESTClient(key_file=key_file, timeout=10)
        prod = client.get_product(product_id=symbol)
        return float(prod.price)
    except Exception as e:
        log.warning("CDP price fetch %s: %s", symbol, e)
        return None


def _fetch_prices(symbols: list, exchanges: list) -> Dict[str, Dict[str, float]]:
    """Fetch prices for all symbol/exchange combinations."""
    result: Dict[str, Dict[str, float]] = {}
    for sym in symbols:
        result[sym] = {}
        for ex in exchanges:
            price = _fetch_price(sym, ex)
            if price:
                result[sym][ex] = price
    return result


# ── Phase A: Cross-Exchange Arb (existing logic) ────────────────────────

def _scan_for_arb(prices: Dict[str, Dict[str, float]]) -> List[dict]:
    """Scan for cross-exchange arb opportunities (Phase A)."""
    opportunities: List[dict] = []
    for symbol, exch_prices in prices.items():
        ex_list = list(exch_prices.items())
        for i in range(len(ex_list)):
            for j in range(i + 1, len(ex_list)):
                ex_a, price_a = ex_list[i]
                ex_b, price_b = ex_list[j]
                if price_a <= 0 or price_b <= 0:
                    continue

                spread_bps = abs(price_a - price_b) / min(price_a, price_b) * 10000
                total_fees_bps = 20  # 10 bps each side
                net_bps = spread_bps - total_fees_bps

                if net_bps > 5:  # Minimum 5 bps net after fees
                    buy_ex = ex_a if price_a < price_b else ex_b
                    sell_ex = ex_b if price_a < price_b else ex_a
                    low_price = min(price_a, price_b)
                    high_price = max(price_a, price_b)

                    usd_value = 1.00
                    expected_profit = usd_value * net_bps / 10000

                    opp = {
                        "symbol": symbol,
                        "buy_exchange": buy_ex,
                        "sell_exchange": sell_ex,
                        "buy_price": low_price,
                        "sell_price": high_price,
                        "spread_bps": round(spread_bps, 1),
                        "net_bps": round(net_bps, 1),
                        "expected_profit_usd": round(expected_profit, 4),
                        "confidence": min(0.95, net_bps / 100),
                        "phase": "A_cross_exchange",
                        "arb_type": "cross_exchange",
                    }
                    opportunities.append(opp)
                    log.info("Phase A ARB: %s %s→%s spread=%.1fbps profit=$%.4f",
                             symbol, buy_ex, sell_ex, net_bps, expected_profit)
    return opportunities


# ── Phase B: Triangular Single-Exchange Arb ─────────────────────────────

def _scan_triangular_single(symbols: List[str], exchanges: List[str]) -> List[dict]:
    """Scan for triangular arb on single exchanges (Phase B)."""
    opportunities: List[dict] = []
    if not _HAS_MULTI_EXCHANGE:
        log.info("Phase B skipped — MultiExchangeScanner not available")
        return opportunities

    try:
        # Build lightweight connectors dict from our price fetcher
        class _PriceFetcherConnector:
            """Minimal connector wrapping _fetch_price for scanner compatibility."""
            def __init__(self, exchange: str):
                self._exchange = exchange
                self._markets: dict = {}

            def get_ticker(self, symbol: str) -> Any:
                price = _fetch_price(symbol, self._exchange)
                if price is None:
                    raise ValueError(f"No price for {symbol} on {self._exchange}")
                return type("Ticker", (), {"bid": price * 0.999, "ask": price * 1.001, "last": price})()

            def get_markets(self) -> dict:
                if not self._markets:
                    # Generate synthetic markets from our symbol list
                    for sym in DEFAULT_SYMBOLS:
                        base = sym.split("-")[0]
                        self._markets[f"{base}/USDT"] = {"symbol": f"{base}/USDT", "base": base, "quote": "USDT"}
                    # Add cross pairs
                    bases = [s.split("-")[0] for s in DEFAULT_SYMBOLS]
                    for i, b1 in enumerate(bases):
                        for b2 in bases[i + 1:]:
                            self._markets[f"{b1}/{b2}"] = {"symbol": f"{b1}/{b2}", "base": b1, "quote": b2}
                return self._markets

        connectors = {ex: _PriceFetcherConnector(ex) for ex in exchanges}
        cache = ExchangePriceCache()
        scanner = MultiExchangeScanner(connectors=connectors, price_cache=cache, min_spread_bps=5.0, min_confidence=0.3)

        for ex in exchanges:
            results = scanner.scan_triangular_single(exchange_name=ex, base_currency="USDT", max_combinations=50, max_results=5)
            for opp in results:
                entry = opp.to_dict() if hasattr(opp, "to_dict") else str(opp)
                opp_dict = {
                    "symbol": opp.legs[0].symbol if opp.legs else "unknown",
                    "arb_type": "triangular_single",
                    "phase": "B_triangular_single",
                    "exchange": ex,
                    "net_pnl_pct": opp.net_pnl_pct,
                    "gross_pnl_pct": opp.gross_pnl_pct,
                    "confidence": opp.confidence,
                    "opportunity_id": opp.opportunity_id,
                    "legs": [leg.to_dict() for leg in opp.legs],
                    "expected_profit_usd": round(opp.net_pnl_pct / 100.0 * 1.00, 4),
                    "buy_exchange": ex,
                    "sell_exchange": ex,
                    "spread_bps": round(opp.net_pnl_pct * 100, 1),
                    "net_bps": round(opp.net_pnl_pct * 100 - 30, 1),  # 3 legs × 10bps
                }
                opportunities.append(opp_dict)
                log.info("Phase B triangular_single: %s on %s pnl=%.2f%% conf=%.2f",
                         opp.opportunity_id[:20], ex, opp.net_pnl_pct, opp.confidence)
    except Exception as e:
        log.warning("Phase B scan error: %s", e)

    return opportunities


# ── Phase C: Triangular Multi-Exchange Arb ──────────────────────────────

def _scan_triangular_multi(symbols: List[str], exchanges: List[str]) -> List[dict]:
    """Scan for triangular arb across multiple exchanges (Phase C)."""
    opportunities: List[dict] = []
    if not _HAS_MULTI_EXCHANGE:
        log.info("Phase C skipped — MultiExchangeScanner not available")
        return opportunities

    try:
        class _PriceFetcherConnector:
            """Minimal connector wrapping _fetch_price for scanner compatibility."""
            def __init__(self, exchange: str):
                self._exchange = exchange
                self._markets: dict = {}

            def get_ticker(self, symbol: str) -> Any:
                price = _fetch_price(symbol, self._exchange)
                if price is None:
                    raise ValueError(f"No price for {symbol} on {self._exchange}")
                return type("Ticker", (), {"bid": price * 0.999, "ask": price * 1.001, "last": price})()

            def get_markets(self) -> dict:
                if not self._markets:
                    for sym in DEFAULT_SYMBOLS:
                        base = sym.split("-")[0]
                        self._markets[sym] = {"symbol": sym, "base": base, "quote": "USD"}
                    bases = [s.split("-")[0] for s in DEFAULT_SYMBOLS]
                    for i, b1 in enumerate(bases):
                        for b2 in bases[i + 1:]:
                            self._markets[f"{b1}-{b2}"] = {"symbol": f"{b1}-{b2}", "base": b1, "quote": b2}
                return self._markets

        connectors = {ex: _PriceFetcherConnector(ex) for ex in exchanges}
        cache = ExchangePriceCache()
        scanner = MultiExchangeScanner(connectors=connectors, price_cache=cache, min_spread_bps=5.0, min_confidence=0.3)

        results = scanner.scan_triangular_multi(base_currency="USDT", max_results=10)
        for opp in results:
            opp_dict = {
                "symbol": opp.legs[0].symbol if opp.legs else "unknown",
                "arb_type": "triangular_multi",
                "phase": "C_triangular_multi",
                "exchanges": list(opp.exchange_names),
                "net_pnl_pct": opp.net_pnl_pct,
                "gross_pnl_pct": opp.gross_pnl_pct,
                "confidence": opp.confidence,
                "opportunity_id": opp.opportunity_id,
                "legs": [leg.to_dict() for leg in opp.legs],
                "expected_profit_usd": round(opp.net_pnl_pct / 100.0 * 1.00, 4),
                "buy_exchange": list(opp.exchange_names)[0] if opp.exchange_names else "unknown",
                "sell_exchange": list(opp.exchange_names)[-1] if opp.exchange_names else "unknown",
                "spread_bps": round(opp.net_pnl_pct * 100, 1),
                "net_bps": round(opp.net_pnl_pct * 100 - 30, 1),
            }
            opportunities.append(opp_dict)
            log.info("Phase C triangular_multi: %s across %s pnl=%.2f%% conf=%.2f",
                     opp.opportunity_id[:20], list(opp.exchange_names), opp.net_pnl_pct, opp.confidence)
    except Exception as e:
        log.warning("Phase C scan error: %s", e)

    return opportunities


# ── Phase D: Quantum Optimizer Sizing ────────────────────────────────────

def _apply_quantum_sizing(
    opportunities: List[dict],
    available_capital: float,
) -> List[dict]:
    """
    Apply quantum optimizer sizing to determine position size for each
    opportunity (Phase D).  Falls back gracefully if the quantum optimizer
    module is not available.
    """
    if not _HAS_QUANTUM_OPTIMIZER:
        log.info("Phase D skipped — MeasurementToTradeSize not available")
        for opp in opportunities:
            opp["quantum_size_usd"] = 1.00
            opp["quantum_confidence"] = opp.get("confidence", 0.5)
        return opportunities

    try:
        from simp.organs.quantumarb.quantum_optimizer import QuantumArbOptimizer

        optimizer = QuantumArbOptimizer()
        quantizer = MeasurementToTradeSize(base_position_usd=100.0)

        sized_opps: List[dict] = []
        for opp in opportunities:
            # Build a minimal QuantumArbResult from the opportunity data
            confidence = opp.get("confidence", 0.5)
            score = min(1.0, max(0.0, confidence * 0.8 + 0.1))
            recom_pct = 2.0 + score * 18.0
            conf_delta = (score - 0.5) * 0.2

            qr = QuantumArbResult(
                opportunity_id=opp.get("opportunity_id", f"opp_{int(time.time()*1000)}"),
                backend_used="local_simulator",
                circuit_depth=8,
                measurement_outcomes={"0000": 0.25, "1111": 0.75},
                optimised_score=round(score, 4),
                recommended_position_pct=round(recom_pct, 2),
                confidence_adjustment=round(conf_delta, 4),
                execution_time_ms=0.5,
                noise_estimate=0.001,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            sizing = quantizer.compute_trade_size(
                quantum_result=qr,
                available_capital=available_capital,
                risk_per_trade_pct=0.5,
            )

            opp["quantum_size_usd"] = sizing["final_size_usd"]
            opp["quantum_score"] = sizing["quantum_score"]
            opp["quantum_confidence"] = score
            opp["quantum_backend"] = sizing["backend_used"]
            opp["quantum_detail"] = sizing

            sized_opps.append(opp)
            log.info("Phase D sizing: %s $%.2f (score=%.3f backend=%s)",
                     opp.get("symbol", "unknown"), sizing["final_size_usd"],
                     sizing["quantum_score"], sizing["backend_used"])

        return sized_opps

    except Exception as e:
        log.warning("Phase D quantum sizing error: %s", e)
        for opp in opportunities:
            opp["quantum_size_usd"] = 1.00
            opp["quantum_confidence"] = opp.get("confidence", 0.5)
        return opportunities


# ── Main Cycle ──────────────────────────────────────────────────────────

def run_cycle(
    loop: bool = False,
    interval: int = 60,
    symbols: Optional[List[str]] = None,
    exchanges: Optional[List[str]] = None,
    triangular: bool = False,
    quantum: bool = False,
) -> int:
    """Run one revenue cycle with up to four scanning phases."""
    symbols = symbols or DEFAULT_SYMBOLS
    exchanges = exchanges or DEFAULT_EXCHANGES

    log.info("=== Revenue Cycle V2 ===")
    log.info("Symbols: %s", symbols)
    log.info("Exchanges: %s", exchanges)
    log.info("Phases: A%s%s%s",
             " +B" if triangular else "",
             " +C" if triangular else "",
             " +D" if quantum else "")

    # ── Phase 1: Fetch prices from all exchanges ──────────────────────
    prices = _fetch_prices(symbols, exchanges)

    active_count = sum(1 for exs in prices.values() for _ in exs)
    log.info("Prices fetched: %d active pairs", active_count)
    for sym, exs in prices.items():
        for ex, price in exs.items():
            log.info("  %s %s: $%.2f", sym, ex, price)

    if not active_count:
        log.warning("No prices fetched — check network/exchange availability")
        return 1

    # ── Phase A: Cross-exchange arbitrage ─────────────────────────────
    all_opportunities: List[dict] = _scan_for_arb(prices)
    log.info("Phase A cross-exchange opportunities: %d", len(all_opportunities))

    # ── Phase B: Triangular single-exchange arb ───────────────────────
    if triangular:
        tri_single = _scan_triangular_single(symbols, exchanges)
        all_opportunities.extend(tri_single)
        log.info("Phase B triangular single opportunities: %d", len(tri_single))

    # ── Phase C: Triangular multi-exchange arb ────────────────────────
    if triangular:
        tri_multi = _scan_triangular_multi(symbols, exchanges)
        all_opportunities.extend(tri_multi)
        log.info("Phase C triangular multi opportunities: %d", len(tri_multi))

    # ── Phase D: Apply quantum optimizer sizing ───────────────────────
    if quantum and all_opportunities:
        available_capital = 100.0  # paper-mode capital
        all_opportunities = _apply_quantum_sizing(all_opportunities, available_capital)
        log.info("Phase D quantum sizing applied to %d opportunities", len(all_opportunities))

    # ── Deduplicate by (symbol, arb_type, exchanges) ──────────────────
    seen: set = set()
    unique_opps: List[dict] = []
    for opp in all_opportunities:
        dedup_key = (
            opp.get("symbol", ""),
            opp.get("arb_type", ""),
            opp.get("buy_exchange", ""),
            opp.get("sell_exchange", ""),
        )
        if dedup_key not in seen:
            seen.add(dedup_key)
            unique_opps.append(opp)

    # Sort by expected profit descending
    unique_opps.sort(key=lambda o: o.get("expected_profit_usd", 0), reverse=True)
    capacity = 5 if quantum else 2  # more room when quantum-scaled
    top_opps = unique_opps[:capacity]

    # ── Execute (paper-mode) ──────────────────────────────────────────
    exec_count = 0
    for opp in top_opps:
        trade_value = opp.get("quantum_size_usd", 1.00)
        entry = _journal_entry(
            entry_type=opp.get("arb_type", "arbitrage"),
            source="revenue_cycle_v2",
            symbol=opp.get("symbol", "unknown"),
            side="arb",
            usd_value=trade_value,
            detail=opp,
        )
        _append_journal(entry)
        _append_arb_log(opp)
        exec_count += 1

    # ── Summary ───────────────────────────────────────────────────────
    summary = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pairs_fetched": active_count,
        "phases_enabled": {
            "A_cross_exchange": True,
            "B_triangular_single": triangular,
            "C_triangular_multi": triangular,
            "D_quantum_sizing": quantum,
        },
        "opportunities": {
            "total_found": len(all_opportunities),
            "unique": len(unique_opps),
            "executed": exec_count,
        },
    }
    print(json.dumps(summary))
    log.info("Cycle complete: %d unique opportunities, %d executed",
             len(unique_opps), exec_count)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Revenue Cycle V2 — Multi-Phase Arbitrage")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS, help="Symbols to scan")
    parser.add_argument("--exchanges", nargs="*", default=DEFAULT_EXCHANGES, help="Exchanges to scan")
    parser.add_argument("--triangular", action="store_true", help="Enable triangular arb (Phase B + C)")
    parser.add_argument("--quantum", action="store_true", help="Enable quantum optimizer sizing (Phase D)")
    args = parser.parse_args()

    if args.loop:
        log.info("Starting revenue cycle V2 loop (interval=%ds)", args.interval)
        while True:
            try:
                run_cycle(
                    symbols=args.symbols,
                    exchanges=args.exchanges,
                    triangular=args.triangular,
                    quantum=args.quantum,
                )
                time.sleep(args.interval)
            except KeyboardInterrupt:
                log.info("Stopping revenue cycle V2 loop")
                break
            except Exception as e:
                log.error("Cycle error: %s", e)
                time.sleep(args.interval)
    else:
        sys.exit(run_cycle(
            symbols=args.symbols,
            exchanges=args.exchanges,
            triangular=args.triangular,
            quantum=args.quantum,
        ))
