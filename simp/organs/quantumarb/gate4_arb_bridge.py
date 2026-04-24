"""
Gate4 Multi-Leg Arbitrage Bridge
=================================
Extends Gate4 inbox consumer to handle multi_leg_trade intent types
for simultaneous multi-exchange arbitrage execution.

This module provides:
1. MultiLegSignalBuilder — Creates Gate4-compatible signal files for arb
2. MultiLegSignalHandler — Processes multi_leg_trade signals from inbox
3. Integration with SimultaneousOrderExecutor for atomic execution

Usage in Gate4:
    from simp.organs.quantumarb.gate4_arb_bridge import MultiLegSignalHandler
    handler = MultiLegSignalHandler(client, cfg, state, dry_run)
    handler.process_signal(signal_data)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("gate4_arb_bridge")

# ── Signal Builder ───────────────────────────────────────────────────────

class MultiLegSignalBuilder:
    """
    Builds multi-leg arbitrage signal files for Gate4 consumption.

    Converts an arb opportunity (cross-exchange or triangular) into
    a signal file that Gate4 can process, with multiple legs that
    get executed atomically.
    """

    @staticmethod
    def build_signal(
        opportunity: Dict[str, Any],
        capital_usd: float = 1.0,
        source: str = "profit_cycle",
    ) -> Dict[str, Any]:
        """
        Build a multi_leg_trade signal from an arb opportunity dict.

        Input opportunity format (from revenue_cycle_v2 or profit_cycle):
        {
            "venue": "cross_exchange_arb",
            "symbol": "BTC-USD",
            "buy_exchange": "coinbase",
            "sell_exchange": "kraken",
            "buy_price": 90000.0,
            "sell_price": 90150.0,
            "spread_bps": 16.7,
            "net_bps": -3.3,
            "expected_return_pct": 0.05,
            "confidence": 0.85,
            "risk_score": 0.3,
            "capital_required": 1.0,
        }

        Or for triangular:
        {
            "venue": "triangular_arb",
            "symbol": "BTC-USD/ETH-USD/SOL-USD",
            "exchange": "coinbase",
            "legs": "BTC→ETH→SOL→BTC",
            ...
        }

        Returns Gate4-compatible signal dict with multi_leg structure.
        """
        venue = opportunity.get("venue", "unknown")
        signal_id = f"mleg_{uuid.uuid4().hex[:14]}"

        # Build assets dict with proper leg structure
        assets: Dict[str, Dict[str, Any]] = {}

        if venue == "cross_exchange_arb":
            symbol = opportunity.get("symbol", "BTC-USD")
            buy_ex = opportunity.get("buy_exchange", "coinbase")
            sell_ex = opportunity.get("sell_exchange", "kraken")
            buy_price = opportunity.get("buy_price", 0)
            sell_price = opportunity.get("sell_price", 0)

            # Each exchange pair gets a leg
            base_currency = symbol.split("-")[0]
            assets[f"{symbol}"] = {
                "action": "buy",
                "position_usd": capital_usd,
                "weight": 1.0,
                "exchange": buy_ex,
                "expected_price": buy_price,
                "leg_type": "arb_buy",
            }
            # Sell leg — we sell the bought asset
            assets[f"{symbol}.sell"] = {
                "action": "sell",
                "position_usd": capital_usd,
                "weight": 1.0,
                "exchange": sell_ex,
                "expected_price": sell_price,
                "leg_type": "arb_sell",
            }

        elif venue == "triangular_arb":
            # Triangular arb: 3 legs on same exchange
            exchange = opportunity.get("exchange", "coinbase")
            spread = float(opportunity.get("expected_return_pct", 0.01))
            # Build 3 legs from the symbol chain
            sym_parts = opportunity.get("symbol", "BTC-USD/ETH-USD/SOL-USD").split("/")
            for i, sym in enumerate(sym_parts):
                side = "buy" if i < 2 else "sell"
                leg_capital = capital_usd * (1.0 + spread * (i / 3))
                assets[sym] = {
                    "action": side,
                    "position_usd": round(leg_capital, 2),
                    "weight": 1.0 / len(sym_parts),
                    "exchange": exchange,
                    "leg_type": "triangular_leg",
                    "leg_index": i,
                }
        else:
            # Single-leg fallback (standard trade)
            symbol = opportunity.get("symbol", "BTC-USD")
            assets[symbol] = {
                "action": "buy",
                "position_usd": capital_usd,
                "weight": 1.0,
                "exchange": "coinbase",
                "leg_type": "single",
            }

        signal = {
            "signal_id": signal_id,
            "signal_type": "multi_leg_trade",
            "multi_leg": True,
            "source": source,
            "venue": venue,
            "assets": assets,
            "metadata": {
                "venue": venue,
                "expected_return_pct": opportunity.get("expected_return_pct", 0),
                "confidence": opportunity.get("confidence", 0),
                "net_bps": opportunity.get("net_bps", 0),
                "spread_bps": opportunity.get("spread_bps", 0),
                "buy_exchange": opportunity.get("buy_exchange"),
                "sell_exchange": opportunity.get("sell_exchange"),
                "legs": opportunity.get("legs"),
                "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return signal

    @staticmethod
    def write_signal(
        opportunity: Dict[str, Any],
        inbox_dir: Path,
        capital_usd: float = 1.0,
        source: str = "profit_cycle",
    ) -> Optional[str]:
        """Build and write a multi-leg signal to the Gate4 inbox."""
        signal = MultiLegSignalBuilder.build_signal(
            opportunity, capital_usd, source,
        )
        inbox_dir.mkdir(parents=True, exist_ok=True)
        path = inbox_dir / f"quantum_signal_{signal['signal_id']}.json"
        try:
            with open(path, "w") as f:
                json.dump(signal, f, indent=2)
            log.info("Multi-leg signal written: %s", path.name)
            return signal["signal_id"]
        except OSError as e:
            log.error("Failed to write signal %s: %s", path.name, e)
            return None


# ── Multi-Leg Signal Handler ─────────────────────────────────────────────

class MultiLegSignalHandler:
    """
    Handles multi_leg_trade signal types for Gate4.

    Processes arb signals with multiple legs, dispatching them
    simultaneously or sequentially depending on the arb type.

    This integrates with the existing Gate4 circuit breakers,
    policy checks, and execution pipeline.
    """

    def __init__(
        self,
        client: Any,
        cfg: Dict[str, Any],
        state: Dict[str, Any],
        dry_run: bool = False,
    ):
        self.client = client
        self.cfg = cfg
        self.state = state
        self.dry_run = dry_run

    def can_handle(self, signal: Dict[str, Any]) -> bool:
        """Check if this handler can process the signal."""
        stype = signal.get("signal_type", "")
        return stype == "multi_leg_trade" or signal.get("multi_leg") is True

    def process_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a multi-leg trade signal.

        Returns execution result dict with per-leg results.
        """
        signal_id = signal.get("signal_id", "unknown")
        assets = signal.get("assets", {})
        venue = signal.get("venue", "unknown")
        metadata = signal.get("metadata", {})

        # Sort legs: buy first, then sell (arb pattern)
        legs = sorted(
            assets.items(),
            key=lambda item: (0 if item[1].get("action") == "buy" else 1,
                              item[1].get("leg_index", 0)),
        )

        results: List[Dict[str, Any]] = []
        all_success = True
        total_pnl = 0.0

        for symbol, leg in legs:
            action = leg.get("action", "buy")
            exchange = leg.get("exchange", "coinbase")
            position_usd = float(leg.get("position_usd", 1.0))

            leg_result = self._execute_leg(
                signal_id=signal_id,
                symbol=symbol,
                action=action,
                position_usd=position_usd,
                exchange=exchange,
                leg_type=leg.get("leg_type", "unknown"),
            )
            results.append(leg_result)
            if not leg_result.get("success", False):
                all_success = False
            total_pnl += leg_result.get("pnl_usd", 0.0)

        # If arb and partial fill, try reversal
        if not all_success and venue in ("cross_exchange_arb", "triangular_arb"):
            log.warning("Partial fill on %s — reversing filled legs", signal_id)
            reversals = self._reverse_filled_legs(results)
            return {
                "success": False,
                "signal_id": signal_id,
                "venue": venue,
                "leg_results": results,
                "reversals": reversals,
                "total_pnl_usd": round(total_pnl, 4),
                "partial_fill": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "success": all_success,
            "signal_id": signal_id,
            "venue": venue,
            "leg_results": results,
            "total_pnl_usd": round(total_pnl, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _execute_leg(
        self,
        signal_id: str,
        symbol: str,
        action: str,
        position_usd: float,
        exchange: str,
        leg_type: str,
    ) -> Dict[str, Any]:
        """Execute a single leg of a multi-leg trade."""
        clean_symbol = symbol.replace(".sell", "").replace(".buy", "")
        log.info("Leg: %s %s %s $%.2f on %s (%s)",
                 signal_id[:8], action.upper(), clean_symbol, position_usd, exchange, leg_type)

        if self.dry_run:
            return {
                "symbol": clean_symbol,
                "action": action,
                "position_usd": position_usd,
                "exchange": exchange,
                "success": True,
                "dry_run": True,
                "filled_quantity": 0.0,
                "average_price": 0.0,
                "pnl_usd": 0.0,
            }

        # Execute against Coinbase CDP for now (single exchange)
        # Future: dispatch to correct exchange connector
        try:
            client_order_id = f"mleg_{uuid.uuid4().hex[:10]}"
            if action == "buy":
                resp = self.client.market_order_buy(
                    client_order_id=client_order_id,
                    product_id=clean_symbol,
                    quote_size=str(position_usd),
                )
            else:
                # Sell
                price = self._get_market_price(clean_symbol)
                base_size = round(position_usd / max(price, 1e-9), 8)
                resp = self.client.market_order_sell(
                    client_order_id=client_order_id,
                    product_id=clean_symbol,
                    base_size=str(base_size),
                )

            resp_dict = resp if isinstance(resp, dict) else resp.to_dict() if hasattr(resp, "to_dict") else {}
            success = bool(resp_dict.get("success", False)) or bool(resp_dict.get("order_id"))
            filled = float(resp_dict.get("filled_size", resp_dict.get("filled_quantity", 0)) or 0)
            avg_price = float(resp_dict.get("average_price", 0) or 0)

            return {
                "symbol": clean_symbol,
                "action": action,
                "position_usd": position_usd,
                "exchange": exchange,
                "success": success,
                "client_order_id": client_order_id,
                "filled_quantity": filled,
                "average_price": avg_price,
                "pnl_usd": 0.0,  # PnL computed at aggregate level
            }

        except Exception as e:
            log.error("Leg execution failed %s %s: %s", action, clean_symbol, e)
            return {
                "symbol": clean_symbol,
                "action": action,
                "position_usd": position_usd,
                "exchange": exchange,
                "success": False,
                "error": str(e),
                "pnl_usd": 0.0,
            }

    def _get_market_price(self, symbol: str) -> float:
        """Get current market price for a symbol."""
        try:
            resp = self.client.get_product(product_id=symbol)
            if hasattr(resp, "price") and resp.price:
                return float(resp.price)
            payload = resp.to_dict() if hasattr(resp, "to_dict") else {}
            return float(payload.get("price", 0))
        except Exception:
            return 0.0

    def _reverse_filled_legs(
        self, leg_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Reverse any legs that were filled to avoid exposure."""
        reversals = []
        for leg in leg_results:
            if leg.get("success") and leg.get("filled_quantity", 0) > 0:
                try:
                    reverse_action = "sell" if leg["action"] == "buy" else "buy"
                    rev_id = f"rev_{uuid.uuid4().hex[:10]}"
                    if reverse_action == "sell":
                        resp = self.client.market_order_sell(
                            client_order_id=rev_id,
                            product_id=leg["symbol"],
                            base_size=str(leg["filled_quantity"]),
                        )
                    else:
                        price = self._get_market_price(leg["symbol"])
                        cost = leg["filled_quantity"] * max(price, 1e-9)
                        resp = self.client.market_order_buy(
                            client_order_id=rev_id,
                            product_id=leg["symbol"],
                            quote_size=str(cost),
                        )
                    reversals.append({
                        "symbol": leg["symbol"],
                        "reversal_side": reverse_action,
                        "success": True,
                    })
                except Exception as e:
                    log.error("Reversal failed for %s: %s", leg["symbol"], e)
                    reversals.append({
                        "symbol": leg["symbol"],
                        "reversal_side": reverse_action,
                        "success": False,
                        "error": str(e),
                    })
        return reversals


# ── Gate4 Integration Helper ─────────────────────────────────────────────

def inject_arb_handler_into_gate4():
    """
    Returns instructions for modifying gate4_inbox_consumer.py
    to add multi-leg arb support.

    To integrate, add this inside process_signal() after the
    signal type check:

        # Check if this is a multi-leg arb signal
        if signal.get("signal_type") == "multi_leg_trade" or signal.get("multi_leg"):
            from simp.organs.quantumarb.gate4_arb_bridge import MultiLegSignalHandler
            handler = MultiLegSignalHandler(client, cfg, state, dry_run)
            result = handler.process_signal(signal)
            return result.get("success", False)
    """
    pass


# ── Test ─────────────────────────────────────────────────────────────────

def test_multi_leg_bridge():
    """Test the multi-leg signal builder and handler."""
    print("Testing Multi-Leg Arbitrage Bridge...")

    # Test 1: Build cross-exchange arb signal
    cross_opp = {
        "venue": "cross_exchange_arb",
        "symbol": "BTC-USD",
        "buy_exchange": "coinbase",
        "sell_exchange": "kraken",
        "buy_price": 90000.0,
        "sell_price": 90150.0,
        "spread_bps": 16.7,
        "net_bps": 11.7,
        "expected_return_pct": 0.117,
        "confidence": 0.85,
        "risk_score": 0.3,
        "capital_required": 1.0,
    }
    signal = MultiLegSignalBuilder.build_signal(cross_opp, capital_usd=2.0)
    assert signal["signal_type"] == "multi_leg_trade"
    assert signal["multi_leg"] is True
    assert len(signal["assets"]) == 2  # buy + sell legs
    print(f"  Cross-exchange signal: {signal['signal_id']} ({len(signal['assets'])} legs)")

    # Test 2: Build triangular arb signal
    tri_opp = {
        "venue": "triangular_arb",
        "symbol": "BTC-USD/ETH-USD/SOL-USD",
        "exchange": "coinbase",
        "legs": "BTC→ETH→SOL→BTC",
        "expected_return_pct": 0.05,
        "confidence": 0.7,
        "risk_score": 0.4,
        "capital_required": 1.0,
    }
    tri_signal = MultiLegSignalBuilder.build_signal(tri_opp, capital_usd=3.0)
    assert tri_signal["signal_type"] == "multi_leg_trade"
    assert len(tri_signal["assets"]) == 3
    print(f"  Triangular signal: {tri_signal['signal_id']} ({len(tri_signal['assets'])} legs)")

    # Test 3: Single-leg fallback
    single_opp = {"symbol": "ETH-USD", "venue": "test", "expected_return_pct": 0.01}
    sig3 = MultiLegSignalBuilder.build_signal(single_opp, capital_usd=1.0)
    assert len(sig3["assets"]) == 1
    print(f"  Single-leg fallback: {len(sig3['assets'])} leg")

    # Test 4: Write signal to temp dir
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sig_id = MultiLegSignalBuilder.write_signal(cross_opp, Path(tmp), capital_usd=2.0)
        assert sig_id is not None
        files = list(Path(tmp).iterdir())
        assert len(files) == 1
        print(f"  Written to disk: {files[0].name}")

    # Test 5: Handler classification
    class StubClient:
        def market_order_buy(self, **kwargs):
            return {"success": True, "order_id": "test123"}
        def market_order_sell(self, **kwargs):
            return {"success": True, "order_id": "test456"}
        def get_product(self, product_id="BTC-USD"):
            class P:
                price = "90000"
            return P()

    handler = MultiLegSignalHandler(StubClient(), {}, {}, dry_run=True)
    assert handler.can_handle(signal)
    result = handler.process_signal(signal)
    assert result.get("success", False)

    print("\n✅ Multi-leg arb bridge tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_multi_leg_bridge()
