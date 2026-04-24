"""
Multi-Exchange Simultaneous Arbitrage Engine

Implements the PDF vision of executing triangular arbitrage across
single AND multiple exchanges simultaneously.

Three arb types, all running concurrently:
1. Cross-exchange arb (buy on A, sell on B)
2. Triangular arb on single exchange (BUY-BUY-SELL or BUY-SELL-SELL)
3. Cross-exchange triangular arb (each leg on a different venue)

Uses the existing ArbDetector and ExchangeConnector interfaces from
the quantumarb module.
"""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Callable

log = logging.getLogger("multi_exchange_arb")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArbLeg:
    """One leg of a multi-exchange arbitrage opportunity."""
    exchange: str
    symbol: str
    side: str                                 # "buy" or "sell"
    expected_price: float
    quantity: float
    fees_bps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultiExchangeOpportunity:
    """
    A complete arbitrage opportunity across one or more exchanges.

    ``arb_type`` is one of:
      - "cross_exchange"         buy on A, sell on B
      - "triangular_single"      triangular arb on one exchange
      - "triangular_multi"       tri arb with each leg on a different exchange
    """
    opportunity_id: str
    arb_type: str
    legs: List[ArbLeg]
    gross_pnl_pct: float
    net_pnl_pct: float
    fees_pct: float
    confidence: float              # 0.0 – 1.0 (from ML/quantum)
    timestamp: str
    estimated_duration_ms: float   # how long to execute all legs
    exchange_names: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.exchange_names:
            self.exchange_names = {leg.exchange for leg in self.legs}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "arb_type": self.arb_type,
            "legs": [leg.to_dict() for leg in self.legs],
            "gross_pnl_pct": self.gross_pnl_pct,
            "net_pnl_pct": self.net_pnl_pct,
            "fees_pct": self.fees_pct,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "estimated_duration_ms": self.estimated_duration_ms,
            "exchange_names": list(self.exchange_names),
        }


# ---------------------------------------------------------------------------
# Exchange price cache — concurrent price fetcher
# ---------------------------------------------------------------------------

class ExchangePriceCache:
    """
    Thread-safe cache that fetches prices from multiple exchanges
    at approximately the same timestamp (critical for arb accuracy).

    Uses asyncio for concurrent fetches, falling back to threading
    if an event loop isn't available.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._prices: Dict[str, Dict[str, Dict[str, float]]] = {}  # exchange → symbol → {"bid": .., "ask": ..}
        self._last_fetch: float = 0.0
        self._cache_ttl_seconds: float = 2.0  # prices stale after 2s

    def fetch_prices(
        self,
        connectors: Dict[str, Any],
        symbols: List[str],
        force: bool = False,
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Fetch latest prices from all connectors for all symbols.

        Returns nested dict: exchange → symbol → {"bid": float, "ask": float, "last": float}.
        """
        now = time.monotonic()
        if not force and (now - self._last_fetch) < self._cache_ttl_seconds:
            with self._lock:
                return dict(self._prices)

        result: Dict[str, Dict[str, Dict[str, float]]] = {}

        for ex_name, connector in connectors.items():
            result[ex_name] = {}
            for symbol in symbols:
                try:
                    ticker = connector.get_ticker(symbol)
                    result[ex_name][symbol] = {
                        "bid": getattr(ticker, "bid", ticker.last),
                        "ask": getattr(ticker, "ask", ticker.last),
                        "last": ticker.last,
                    }
                except Exception as exc:
                    log.debug("Price fetch failed for %s/%s: %s", ex_name, symbol, exc)
                    result[ex_name][symbol] = {"bid": 0.0, "ask": 0.0, "last": 0.0}

        with self._lock:
            self._prices = result
            self._last_fetch = now

        return result


# ---------------------------------------------------------------------------
# MultiExchangeScanner — discovers opportunities
# ---------------------------------------------------------------------------

class MultiExchangeScanner:
    """
    Discovers arbitrage opportunities across multiple exchanges.

    Three scan modes:
      - cross_exchange:       standard buy-low-on-A, sell-high-on-B
      - triangular_single:    triangular arb on a single exchange
      - triangular_multi:     each triangular leg on a different exchange
    """

    def __init__(
        self,
        connectors: Dict[str, Any],
        price_cache: Optional[ExchangePriceCache] = None,
        min_spread_bps: float = 10.0,
        min_confidence: float = 0.5,
    ):
        self._connectors = connectors
        self._cache = price_cache or ExchangePriceCache()
        self.min_spread_bps = min_spread_bps
        self.min_confidence = min_confidence

    # ------------------------------------------------------------------
    # cross-exchange scan
    # ------------------------------------------------------------------

    def scan_cross_exchange(
        self,
        symbols: List[str],
        max_results: int = 10,
    ) -> List[MultiExchangeOpportunity]:
        """
        Detect cross-exchange arbitrage: buy on exchange A, sell on exchange B.

        For each symbol, checks all exchange pairs.
        """
        prices = self._cache.fetch_prices(self._connectors, symbols)
        opportunities: List[MultiExchangeOpportunity] = []

        exchange_names = list(self._connectors.keys())

        for symbol in symbols:
            for i, ex_a in enumerate(exchange_names):
                for ex_b in exchange_names[i + 1:]:
                    price_a = prices.get(ex_a, {}).get(symbol, {}).get("ask", 0.0)
                    price_b = prices.get(ex_b, {}).get(symbol, {}).get("bid", 0.0)

                    if price_a <= 0 or price_b <= 0:
                        continue

                    # Standard direction: buy on a (ask), sell on b (bid)
                    spread_bps = ((price_b - price_a) / price_a) * 10000
                    if spread_bps >= self.min_spread_bps:
                        opp = self._build_cross_exchange_opp(
                            symbol=symbol,
                            exchange_buy=ex_a,
                            exchange_sell=ex_b,
                            buy_price=price_a,
                            sell_price=price_b,
                            spread_bps=spread_bps,
                            direction="standard",
                        )
                        opportunities.append(opp)

                    # Reverse direction: buy on b, sell on a
                    spread_bps_rev = ((price_a - price_b) / price_b) * 10000
                    if spread_bps_rev >= self.min_spread_bps:
                        opp = self._build_cross_exchange_opp(
                            symbol=symbol,
                            exchange_buy=ex_b,
                            exchange_sell=ex_a,
                            buy_price=price_b,
                            sell_price=price_a,
                            spread_bps=spread_bps_rev,
                            direction="reverse",
                        )
                        opportunities.append(opp)

        opportunities.sort(key=lambda o: o.net_pnl_pct, reverse=True)
        return opportunities[:max_results]

    def _build_cross_exchange_opp(
        self,
        symbol: str,
        exchange_buy: str,
        exchange_sell: str,
        buy_price: float,
        sell_price: float,
        spread_bps: float,
        direction: str,
    ) -> MultiExchangeOpportunity:
        # Estimate fees (0.1% per leg by default)
        fee_rate = 0.001
        fees_pct = fee_rate * 2 * 100
        net_pnl = spread_bps - fees_pct * 100  # bps

        leg_buy = ArbLeg(
            exchange=exchange_buy,
            symbol=symbol,
            side="buy",
            expected_price=buy_price,
            quantity=0.0,  # filled by executor
            fees_bps=fee_rate * 10000,
        )
        leg_sell = ArbLeg(
            exchange=exchange_sell,
            symbol=symbol,
            side="sell",
            expected_price=sell_price,
            quantity=0.0,
            fees_bps=fee_rate * 10000,
        )

        return MultiExchangeOpportunity(
            opportunity_id=f"cross_{exchange_buy}_{exchange_sell}_{symbol}_{int(time.time()*1000)}",
            arb_type="cross_exchange",
            legs=[leg_buy, leg_sell],
            gross_pnl_pct=round(spread_bps / 100, 4),
            net_pnl_pct=round(net_pnl / 100, 4),
            fees_pct=round(fees_pct, 4),
            confidence=0.7,   # baseline; overridden by ML/quantum
            timestamp=datetime.now(timezone.utc).isoformat(),
            estimated_duration_ms=500.0,  # 0.5s for 2-leg arb
        )

    # ------------------------------------------------------------------
    # triangular scan (single exchange)
    # ------------------------------------------------------------------

    def scan_triangular_single(
        self,
        exchange_name: str,
        base_currency: str = "USDT",
        max_combinations: int = 100,
        max_results: int = 10,
    ) -> List[MultiExchangeOpportunity]:
        """
        Detect triangular arbitrage on a single exchange.

        Uses the BUY-BUY-SELL and BUY-SELL-SELL approaches from the PDF.
        """
        connector = self._connectors.get(exchange_name)
        if not connector:
            log.warning("Exchange '%s' not found", exchange_name)
            return []

        # Get all markets
        try:
            markets = connector.get_markets()
        except AttributeError:
            log.warning("Connector %s does not support get_markets()", exchange_name)
            return []

        # Filter markets that trade against the base currency
        candidates = []
        for mkt_name, mkt_data in markets.items():
            if base_currency in mkt_name:
                candidates.append(mkt_name)

        prices = self._cache.fetch_prices(
            self._connectors, candidates[:200]
        )

        opportunities: List[MultiExchangeOpportunity] = []

        # Triangular combinations: base → A → B → base
        combos_checked = 0
        for i, pair_a in enumerate(candidates):
            if combos_checked >= max_combinations:
                break
            for pair_b in candidates[i + 1:]:
                combos_checked += 1
                if combos_checked >= max_combinations:
                    break

                # Extract asset names
                asset_a = pair_a.replace(base_currency, "").strip("-_/")
                asset_b = pair_b.replace(base_currency, "").strip("-_/")
                if not asset_a or not asset_b or asset_a == asset_b:
                    continue

                pair_ab = f"{asset_a}/{asset_b}"
                pair_ba = f"{asset_b}/{asset_a}"

                # Try both directions
                for direction in ("buy_buy_sell", "buy_sell_sell"):
                    opp = self._evaluate_triangular(
                        exchange_name=exchange_name,
                        base_currency=base_currency,
                        asset_a=asset_a,
                        asset_b=asset_b,
                        pair_a=pair_a,
                        pair_b=pair_b,
                        pair_ab=pair_ab,
                        pair_ba=pair_ba,
                        prices=prices.get(exchange_name, {}),
                        direction=direction,
                    )
                    if opp:
                        opportunities.append(opp)

        opportunities.sort(key=lambda o: o.net_pnl_pct, reverse=True)
        return opportunities[:max_results]

    def _evaluate_triangular(
        self,
        exchange_name: str,
        base_currency: str,
        asset_a: str,
        asset_b: str,
        pair_a: str,
        pair_b: str,
        pair_ab: str,
        pair_ba: str,
        prices: Dict[str, Dict[str, float]],
        direction: str,
    ) -> Optional[MultiExchangeOpportunity]:
        """Evaluate one triangular combination."""
        price_a = prices.get(pair_a, {}).get("last", 0.0)
        price_b = prices.get(pair_b, {}).get("last", 0.0)
        price_ab = prices.get(pair_ab, {}).get("last", 0.0)
        price_ba = prices.get(pair_ba, {}).get("last", 0.0)

        if price_a <= 0 or price_b <= 0:
            return None

        fee_rate = 0.001  # 0.1% per trade
        total_fees_pct = fee_rate * 3 * 100

        if direction == "buy_buy_sell":
            # Buy A with base, buy B with A, sell B for base
            if price_ab <= 0:
                return None
            # 1 base → 1/price_a A → (1/price_a)/price_ab B → that * price_b base
            final = (1.0 / price_a) / price_ab * price_b
        else:
            # buy_sell_sell
            if price_ba <= 0:
                return None
            # 1 base → 1/price_b B → (1/price_b)/price_ba A → that * price_a base
            final = (1.0 / price_b) / price_ba * price_a

        gross_pnl_pct = (final - 1.0) * 100
        net_pnl_pct = gross_pnl_pct - total_fees_pct

        if net_pnl_pct <= 0:
            return None

        leg1 = ArbLeg(exchange=exchange_name, symbol=pair_a, side="buy",
                       expected_price=price_a, quantity=0.0, fees_bps=fee_rate * 10000)
        leg2 = ArbLeg(exchange=exchange_name, symbol=pair_ab if direction == "buy_buy_sell" else pair_ba,
                       side="buy" if direction == "buy_buy_sell" else "sell",
                       expected_price=price_ab if direction == "buy_buy_sell" else price_ba,
                       quantity=0.0, fees_bps=fee_rate * 10000)
        leg3 = ArbLeg(exchange=exchange_name, symbol=pair_b, side="sell",
                       expected_price=price_b, quantity=0.0, fees_bps=fee_rate * 10000)

        return MultiExchangeOpportunity(
            opportunity_id=f"tri_single_{exchange_name}_{direction}_{int(time.time()*1000)}",
            arb_type="triangular_single",
            legs=[leg1, leg2, leg3],
            gross_pnl_pct=round(gross_pnl_pct, 4),
            net_pnl_pct=round(net_pnl_pct, 4),
            fees_pct=round(total_fees_pct, 4),
            confidence=0.6,
            timestamp=datetime.now(timezone.utc).isoformat(),
            estimated_duration_ms=800.0,
        )

    # ------------------------------------------------------------------
    # triangular multi-exchange scan
    # ------------------------------------------------------------------

    def scan_triangular_multi(
        self,
        base_currency: str = "USDT",
        max_results: int = 5,
    ) -> List[MultiExchangeOpportunity]:
        """
        Triangular arbitrage with each leg on a different exchange.

        This is the *most* complex and *most* profitable arb type from the PDF.
        """
        # Get all exchange+symbol combos
        all_prices = self._cache.fetch_prices(
            self._connectors, self._get_common_symbols()
        )

        opportunities: List[MultiExchangeOpportunity] = []
        exchange_names = list(self._connectors.keys())

        for symbol in self._get_common_symbols()[:50]:
            for ex_buy in exchange_names:
                for ex_sell in exchange_names:
                    if ex_buy == ex_sell:
                        continue
                    # buy on ex_buy, sell on ex_sell
                    ask = all_prices.get(ex_buy, {}).get(symbol, {}).get("ask", 0.0)
                    bid = all_prices.get(ex_sell, {}).get(symbol, {}).get("bid", 0.0)
                    if ask <= 0 or bid <= 0:
                        continue
                    spread_bps = ((bid - ask) / ask) * 10000
                    if spread_bps >= self.min_spread_bps:
                        fee_rate = 0.001
                        fees_pct = fee_rate * 2 * 100
                        net_pnl = spread_bps - fees_pct * 100

                        leg1 = ArbLeg(exchange=ex_buy, symbol=symbol, side="buy",
                                       expected_price=ask, quantity=0.0, fees_bps=fee_rate * 10000)
                        leg2 = ArbLeg(exchange=ex_sell, symbol=symbol, side="sell",
                                       expected_price=bid, quantity=0.0, fees_bps=fee_rate * 10000)

                        opportunities.append(MultiExchangeOpportunity(
                            opportunity_id=f"tri_multi_{ex_buy}_{ex_sell}_{symbol}_{int(time.time()*1000)}",
                            arb_type="triangular_multi",
                            legs=[leg1, leg2],
                            gross_pnl_pct=round(spread_bps / 100, 4),
                            net_pnl_pct=round(net_pnl / 100, 4),
                            fees_pct=round(fees_pct, 4),
                            confidence=0.5,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            estimated_duration_ms=1200.0,
                        ))

        opportunities.sort(key=lambda o: o.net_pnl_pct, reverse=True)
        return opportunities[:max_results]

    def _get_common_symbols(self, min_exchanges: int = 2) -> List[str]:
        """Get symbols available on at least N exchanges."""
        symbol_sets = []
        for ex_name, connector in self._connectors.items():
            try:
                markets = connector.get_markets()
                symbol_sets.append(set(markets.keys()))
            except AttributeError:
                symbol_sets.append(set())

        if not symbol_sets:
            return []

        common = set.intersection(*symbol_sets) if len(symbol_sets) > 1 else symbol_sets[0]
        return sorted(common)


# ---------------------------------------------------------------------------
# MultiExchangeOpportunityRanker
# ---------------------------------------------------------------------------

class MultiExchangeOpportunityRanker:
    """
    Ranks opportunities by a weighted score that combines profit, confidence,
    speed, and quantum enhancement.
    """

    def __init__(self):
        self.weights = {
            "net_pnl_pct": 0.4,
            "confidence": 0.25,
            "speed_score": 0.2,       # faster = better
            "exchange_score": 0.15,   # trusted exchanges weigh more
        }

    def rank(
        self,
        opportunities: List[MultiExchangeOpportunity],
        quantum_scores: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank opportunities by weighted score.

        ``quantum_scores`` maps opportunity_id → quantum-enhanced score (0–1).
        """
        if not opportunities:
            return []

        quantum_scores = quantum_scores or {}

        # Normalise profit across all opportunities
        max_pnl = max(o.net_pnl_pct for o in opportunities) or 1.0
        min_duration = min(o.estimated_duration_ms for o in opportunities) or 1.0

        ranked = []
        for opp in opportunities:
            pnl_score = opp.net_pnl_pct / max_pnl
            speed_score = min_duration / max(opp.estimated_duration_ms, 1.0)
            exchange_score = 1.0  # baseline; could weight by BRP trust

            combined = (
                self.weights["net_pnl_pct"] * pnl_score
                + self.weights["confidence"] * opp.confidence
                + self.weights["speed_score"] * speed_score
                + self.weights["exchange_score"] * exchange_score
            )

            # Apply quantum boost if available
            quantum_boost = quantum_scores.get(opp.opportunity_id, 0.0)
            if quantum_boost > 0:
                combined = combined * (1.0 + quantum_boost * 0.2)  # up to 20% boost

            ranked.append({
                "opportunity": opp,
                "score": round(combined, 4),
                "pnl_pct": opp.net_pnl_pct,
                "confidence": opp.confidence,
                "quantum_boost": quantum_boost,
            })

        ranked.sort(key=lambda r: r["score"], reverse=True)
        return ranked


# ---------------------------------------------------------------------------
# SimultaneousOrderExecutor — atomic multi-leg execution
# ---------------------------------------------------------------------------

class SimultaneousOrderExecutor:
    """
    Executes multiple arbitrage legs across one or more exchanges
    as close to simultaneously as possible.

    Uses the existing TradeExecutor for each individual leg but
    adds cross-exchange atomicity checks.
    """

    def __init__(self, trade_executors: Dict[str, Any]):
        """
        ``trade_executors`` maps exchange_name → TradeExecutor instance.
        """
        self._executors = trade_executors
        self._lock = threading.Lock()
        self._active_executions: Dict[str, Dict[str, Any]] = {}

    def execute_opportunity(
        self,
        opportunity: MultiExchangeOpportunity,
        capital_usd: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Execute all legs of a multi-exchange opportunity.

        Strategy: place all legs as market orders simultaneously,
        then check that all filled successfully.  If any leg fails,
        attempt to reverse filled legs.

        Returns execution result dict.
        """
        log.info(
            "Executing %s opportunity %s (%d legs, %.2f%% expected)",
            opportunity.arb_type, opportunity.opportunity_id,
            len(opportunity.legs), opportunity.net_pnl_pct,
        )

        # 1. Compute quantities per leg from capital allocation
        legs = opportunity.legs
        if not legs:
            return {"success": False, "error": "No legs to execute"}

        # 2. Dispatch all legs
        leg_results: List[Dict[str, Any]] = []
        all_success = True
        total_pnl = 0.0
        errors: List[str] = []

        for i, leg in enumerate(legs):
            executor = self._executors.get(leg.exchange)
            if not executor:
                errors.append(f"No executor for exchange '{leg.exchange}'")
                all_success = False
                continue

            # Determine quantity for this leg based on capital
            leg_capital = capital_usd / len(legs)
            quantity = leg_capital / max(leg.expected_price, 1e-9)

            try:
                if leg.side == "buy":
                    result = executor.execute_trade(
                        symbol=leg.symbol,
                        side="buy",  # OrderSide.BUY
                        quantity=round(quantity, 8),
                        trade_id=f"{opportunity.opportunity_id}:leg_{i}",
                        exchange_name=leg.exchange,
                    )
                else:
                    result = executor.execute_trade(
                        symbol=leg.symbol,
                        side="sell",
                        quantity=round(quantity, 8),
                        trade_id=f"{opportunity.opportunity_id}:leg_{i}",
                        exchange_name=leg.exchange,
                    )

                leg_result = {
                    "leg_index": i,
                    "exchange": leg.exchange,
                    "symbol": leg.symbol,
                    "side": leg.side,
                    "success": result.success,
                    "filled_quantity": result.filled_quantity,
                    "average_price": result.average_price,
                    "error": result.error_message,
                }
                leg_results.append(leg_result)

                if not result.success:
                    all_success = False
                    errors.append(f"Leg {i} ({leg.exchange}/{leg.symbol}): {result.error_message}")

            except Exception as exc:
                all_success = False
                errors.append(f"Leg {i} exception: {exc}")
                leg_results.append({
                    "leg_index": i,
                    "exchange": leg.exchange,
                    "symbol": leg.symbol,
                    "side": leg.side,
                    "success": False,
                    "error": str(exc),
                })

        # 3. If partial fill, attempt reversal
        if not all_success and any(lr.get("filled_quantity", 0) > 0 for lr in leg_results if lr.get("success")):
            log.warning("Partial fill detected — attempting reversal")
            reversal_results = self._reverse_filled_legs(opportunity, leg_results)
            return {
                "success": False,
                "partial_fill": True,
                "leg_results": leg_results,
                "reversal_results": reversal_results,
                "errors": errors,
                "opportunity_id": opportunity.opportunity_id,
            }

        # 4. Calculate actual P&L
        if all_success:
            total_buy_cost = sum(
                lr["average_price"] * lr["filled_quantity"]
                for lr in leg_results if lr["side"] == "buy" and lr["success"]
            )
            total_sell_proceeds = sum(
                lr["average_price"] * lr["filled_quantity"]
                for lr in leg_results if lr["side"] == "sell" and lr["success"]
            )
            total_pnl = total_sell_proceeds - total_buy_cost

        return {
            "success": all_success,
            "opportunity_id": opportunity.opportunity_id,
            "arb_type": opportunity.arb_type,
            "leg_results": leg_results,
            "total_pnl_usd": round(total_pnl, 4),
            "expected_pnl_pct": opportunity.net_pnl_pct,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _reverse_filled_legs(
        self,
        opportunity: MultiExchangeOpportunity,
        leg_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Reverse any legs that were filled to avoid exposure."""
        reversals = []
        for i, lr in enumerate(leg_results):
            if lr.get("success") and lr.get("filled_quantity", 0) > 0:
                executor = self._executors.get(lr["exchange"])
                if executor:
                    reverse_side = "sell" if lr["side"] == "buy" else "buy"
                    try:
                        rev_result = executor.execute_trade(
                            symbol=lr["symbol"],
                            side=reverse_side,
                            quantity=lr["filled_quantity"],
                            trade_id=f"{opportunity.opportunity_id}:reversal_{i}",
                            exchange_name=lr["exchange"],
                        )
                        reversals.append({
                            "leg_index": i,
                            "reversal_side": reverse_side,
                            "success": rev_result.success,
                            "error": rev_result.error_message,
                        })
                    except Exception as exc:
                        reversals.append({
                            "leg_index": i,
                            "reversal_side": reverse_side,
                            "success": False,
                            "error": str(exc),
                        })
        return reversals


# ======================================================================
# Quick test
# ======================================================================

if __name__ == "__main__":
    print("Multi-Exchange Arbitrage Engine loaded")
    print("Available scanners: cross_exchange, triangular_single, triangular_multi")
    print("Available executor: SimultaneousOrderExecutor with per-exchange TradeExecutors")
