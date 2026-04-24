#!/usr/bin/env python3.10
"""
Revenue Cycle Runner — Multi-Exchange Arbitrage Engine
=======================================================
Orchestrates cross-exchange arb detection, prediction market signals,
and multi-exchange scanning into one autonomous revenue loop.

Usage:
    python3 scripts/revenue_cycle.py                    # single cycle
    python3 scripts/revenue_cycle.py --loop             # continuous (every 60s)
    python3 scripts/revenue_cycle.py --loop --interval 120
"""

import os, sys, json, time, logging, argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(REPO / "logs" / "revenue_cycle.log"), mode="a"),
    ],
)
log = logging.getLogger("revenue_cycle")

# ── Config ──────────────────────────────────────────────────────────────

DECISION_JOURNAL = REPO / "state" / "decision_journal.ndjson"
GATE4_INBOX = REPO / "data" / "inboxes" / "gate4_real"
ARB_LOG = REPO / "logs" / "arb_cycle.jsonl"

DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD"]
DEFAULT_EXCHANGES = ["coinbase", "kraken", "binance", "gemini", "bitstamp", "huobi"]

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
    from datetime import datetime, timezone
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

def _append_journal(entry: dict):
    with open(DECISION_JOURNAL, "a") as f:
        f.write(json.dumps(entry) + "\n")
    log.info("Journal: %s %s %s $%.2f", entry["type"], entry["symbol"], entry["side"], entry["usd_value"])

# ── Price Fetching ──────────────────────────────────────────────────────

def _fetch_price(symbol: str, exchange: str) -> Optional[float]:
    """Fetch current price from an exchange's public API."""
    import urllib.request, urllib.error
    try:
        if exchange == "coinbase":
            # Coinbase Advanced Trade API (CDP key required)
            return _fetch_coinbase_cdp(symbol)
            # Fallback: public endpoint
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
        elif exchange == "binance":
            pair = symbol.replace("-", "")
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            return float(data["price"])
        elif exchange == "gemini":
            url = f"https://api.gemini.com/v1/pubticker/{symbol.lower()}"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            return float(data["last"])
        elif exchange == "bitstamp":
            pair = symbol.replace("-", "").lower()
            url = f"https://www.bitstamp.net/api/v2/ticker/{pair}/"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            return float(data["last"])
        elif exchange == "huobi":
            pair = symbol.replace("-", "").lower()
            url = f"https://api.huobi.pro/market/detail/merged?symbol={pair}"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            if data.get("status") == "ok":
                return float(data.get("tick", {}).get("close", 0))

    except Exception as e:
        log.warning("Price fetch %s/%s: %s", exchange, symbol, e)
    return None

def _fetch_coinbase_cdp(symbol: str) -> Optional[float]:
    """Fetch price using CDP API key file (same pattern as gate4)."""
    try:
        key_file = str(REPO / "config" / "coinbase_cdp_key.json")
        if not os.path.exists(key_file):
            # Try home dir
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

# ── Arb Detection ───────────────────────────────────────────────────────

def _scan_for_arb(prices: Dict[str, Dict[str, float]]) -> List[dict]:
    """Scan for cross-exchange arb opportunities."""
    opportunities = []
    for symbol, exch_prices in prices.items():
        ex_list = list(exch_prices.items())
        for i in range(len(ex_list)):
            for j in range(i + 1, len(ex_list)):
                ex_a, price_a = ex_list[i]
                ex_b, price_b = ex_list[j]
                if price_a <= 0 or price_b <= 0:
                    continue
                
                # Spread in bps
                spread_bps = abs(price_a - price_b) / min(price_a, price_b) * 10000
                
                # Estimate fees (~10 bps per exchange)
                total_fees_bps = 20  # 10 bps each side
                net_bps = spread_bps - total_fees_bps
                
                if net_bps > 5:  # Minimum 5 bps net after fees
                    direction = "buy" if price_a < price_b else "sell"
                    buy_ex = ex_a if price_a < price_b else ex_b
                    sell_ex = ex_b if price_a < price_b else ex_a
                    low_price = min(price_a, price_b)
                    high_price = max(price_a, price_b)
                    
                    # Compute max position based on available balance
                    # For paper mode: $1.00 per trade
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
                    }
                    opportunities.append(opp)
                    log.info("ARB: %s %s→%s spread=%.1fbps profit=$%.4f",
                             symbol, opp["buy_exchange"], opp["sell_exchange"],
                             net_bps, expected_profit)
    return opportunities

# ── Prediction Market Signal ────────────────────────────────────────────

def _check_prediction_markets(prices: dict) -> Optional[dict]:
    """Check if Kalshi signals are available (stub when API is down)."""
    # Kalshi API is currently down (migration in progress)
    # This will activate when KalshiLiveOrgan becomes available
    return None

# ── Main Cycle ──────────────────────────────────────────────────────────

def run_cycle(loop: bool = False, interval: int = 60, symbols: list = None, exchanges: list = None):
    """Run one revenue cycle."""
    symbols = symbols or DEFAULT_SYMBOLS
    exchanges = exchanges or DEFAULT_EXCHANGES
    
    log.info("=== Revenue Cycle ===")
    log.info("Symbols: %s", symbols)
    log.info("Exchanges: %s", exchanges)
    
    # Phase 1: Fetch prices from all exchanges
    prices = _fetch_prices(symbols, exchanges)
    
    active_count = sum(1 for exs in prices.values() for _ in exs)
    log.info("Prices fetched: %d active pairs", active_count)
    for sym, exs in prices.items():
        for ex, price in exs.items():
            log.info("  %s %s: $%.2f", sym, ex, price)
    
    if not active_count:
        log.warning("No prices fetched — check network/exchange availability")
        return 1
    
    # Phase 2: Scan for arbitrage
    arb_opps = _scan_for_arb(prices)
    log.info("Arb opportunities: %d", len(arb_opps))
    
    # Phase 3: Check prediction markets
    pm_signal = _check_prediction_markets(prices)
    
    # Phase 4: Execute (paper-mode, $1.00 positions)
    for opp in arb_opps[:2]:  # Max 2 arb trades per cycle
        entry = _journal_entry(
            entry_type="arbitrage",
            source="revenue_cycle",
            symbol=opp["symbol"],
            side=opp["direction"],
            usd_value=1.00,
            detail=opp,
        )
        _append_journal(entry)
    
    # Phase 5: Record summary
    summary = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pairs_fetched": active_count,
        "opportunities": len(arb_opps),
        "arb_executed": min(len(arb_opps), 2),
        "pm_signal": bool(pm_signal),
    }
    print(json.dumps(summary))
    log.info("Cycle complete: %d arb opportunities, %d executed", len(arb_opps), min(len(arb_opps), 2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Revenue Cycle Runner")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS, help="Symbols to scan")
    parser.add_argument("--exchanges", nargs="*", default=DEFAULT_EXCHANGES, help="Exchanges to scan")
    args = parser.parse_args()
    
    if args.loop:
        log.info("Starting revenue cycle loop (interval=%ds)", args.interval)
        while True:
            try:
                run_cycle(symbols=args.symbols, exchanges=args.exchanges)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                log.info("Stopping revenue cycle loop")
                break
            except Exception as e:
                log.error("Cycle error: %s", e)
                time.sleep(args.interval)
    else:
        sys.exit(run_cycle(symbols=args.symbols, exchanges=args.exchanges))
