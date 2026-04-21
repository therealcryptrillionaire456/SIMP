"""
SIMP Trade Scorer — Hindsight Engine
======================================

Reads the PnL ledger, enriches every order with its actual fill price
(fetched from Coinbase Advanced Trade API), builds FIFO position lots,
matches buys to sells, and writes a scored trade journal.

What it produces per round-trip:
    - signal_source        : what triggered the trade (timeout_fallback, qip, manual)
    - symbol               : BTC-USD etc.
    - hold_seconds         : how long the position was held
    - buy_price / sell_price: actual execution prices
    - gross_return_pct     : (sell - buy) / buy * 100
    - fee_adj_return_pct   : after estimated fees
    - verdict              : PROFITABLE / BREAKEVEN / LOSS
    - market_moved_with    : did price move in the signal's favour?

Output: data/trade_journal.jsonl  (append-only, deduplicated by round_trip_id)
        data/hindsight_report.txt  (human-readable summary)

Usage:
    python3 -m simp.policies.trade_scorer          # score everything in ledger
    python3 -m simp.policies.trade_scorer --live   # also fetch live Coinbase fills
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("simp.trade_scorer")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent.parent
PNL_LEDGER = REPO / "data" / "phase4_pnl_ledger.jsonl"
SIGNAL_PROCESSED = REPO / "data" / "inboxes" / "gate4_real" / "_processed"
TRADE_JOURNAL = REPO / "data" / "trade_journal.jsonl"
HINDSIGHT_REPORT = REPO / "data" / "hindsight_report.txt"

FEE_RATE = 0.006   # 0.6% taker — conservative for small Coinbase accounts

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Lot:
    """A single buy lot in FIFO position tracking."""
    order_id: str
    signal_id: str
    signal_source: str
    ts: str
    symbol: str
    qty: float          # units (BTC, ETH, SOL)
    price: float        # USD per unit (fill price)
    notional_usd: float
    remaining_qty: float = 0.0

    def __post_init__(self):
        self.remaining_qty = self.qty


@dataclass
class RoundTrip:
    """A matched buy→sell pair with P&L."""
    round_trip_id: str
    symbol: str
    buy_signal_id: str
    buy_signal_source: str
    sell_signal_id: str
    sell_signal_source: str
    buy_ts: str
    sell_ts: str
    hold_seconds: float
    qty: float
    buy_price: float
    sell_price: float
    buy_notional_usd: float
    sell_notional_usd: float
    gross_pnl_usd: float
    gross_return_pct: float
    est_fees_usd: float
    fee_adj_pnl_usd: float
    fee_adj_return_pct: float
    verdict: str            # PROFITABLE / BREAKEVEN / LOSS
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Coinbase Advanced Trade API — fetch order fill price
# ---------------------------------------------------------------------------

def _load_cb_credentials() -> Tuple[str, str]:
    """Load Coinbase API key name + private key from .env or env vars."""
    key_name = os.environ.get("COINBASE_API_KEY_NAME", "")
    private_key = os.environ.get("COINBASE_API_PRIVATE_KEY", "")

    if key_name and private_key:
        return key_name, private_key

    env_path = REPO / ".env"
    if not env_path.exists():
        return "", ""

    current_key = None
    lines_buf: List[str] = []
    in_pem = False
    result: Dict[str, str] = {}

    for raw in env_path.read_text(errors="replace").splitlines():
        line = raw.rstrip()
        if in_pem:
            lines_buf.append(line)
            if line.startswith("-----END"):
                result[current_key] = "\n".join(lines_buf)
                in_pem = False
            continue
        if not line or line.startswith("#"):
            continue
        if "=" in line and not line.startswith(" "):
            k, _, v = line.partition("=")
            v = v.strip().strip('"').strip("'")
            if v.startswith("-----BEGIN"):
                current_key = k.strip()
                lines_buf = [v]
                in_pem = True
            else:
                result[k.strip()] = v

    return (
        result.get("COINBASE_API_KEY_NAME", ""),
        result.get("COINBASE_API_PRIVATE_KEY", ""),
    )


def fetch_order_fill_price(order_id: str) -> Optional[float]:
    """
    Fetch the average fill price for a Coinbase order.
    Returns None on any error — caller falls back to ledger data.
    """
    key_name, private_key = _load_cb_credentials()
    if not key_name or not private_key:
        return None
    try:
        from coinbase.rest import RESTClient
        client = RESTClient(api_key=key_name, api_secret=private_key)
        resp = client.get_order(order_id=order_id)
        order = getattr(resp, "order", None) or {}
        avg_price = (
            getattr(order, "average_filled_price", None)
            or (order.get("average_filled_price") if isinstance(order, dict) else None)
        )
        if avg_price:
            return float(avg_price)
    except Exception as e:
        log.debug("fill price fetch failed for %s: %s", order_id, e)
    return None


# ---------------------------------------------------------------------------
# Signal source loader
# ---------------------------------------------------------------------------

def _load_signals() -> Dict[str, dict]:
    """Load all processed signal files. Returns {signal_id: signal_dict}."""
    signals: Dict[str, dict] = {}
    if not SIGNAL_PROCESSED.exists():
        return signals
    for f in SIGNAL_PROCESSED.glob("quantum_signal_*.json"):
        try:
            d = json.loads(f.read_text())
            sid = d.get("signal_id", "")
            if sid:
                signals[sid] = d
        except Exception:
            pass
    return signals


# ---------------------------------------------------------------------------
# Ledger loader
# ---------------------------------------------------------------------------

def _load_ledger() -> List[dict]:
    if not PNL_LEDGER.exists():
        return []
    orders = []
    with open(PNL_LEDGER) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    orders.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return sorted(orders, key=lambda o: o.get("ts", ""))


# ---------------------------------------------------------------------------
# FIFO position tracker
# ---------------------------------------------------------------------------

class PositionTracker:
    """
    FIFO lot tracker per symbol.

    On BUY  → push a lot
    On SELL → drain lots FIFO, yield matched RoundTrips
    """

    def __init__(self):
        self._lots: Dict[str, deque] = defaultdict(deque)

    def buy(self, order: dict, price: float, signals: Dict[str, dict]) -> None:
        symbol = order["symbol"]
        notional = float(order.get("exec_usd") or order.get("notional_usd") or 0)
        if notional <= 0 or price <= 0:
            return
        qty = notional / price
        sid = order.get("signal_id", "")
        sig_info = signals.get(sid, {})
        source = sig_info.get("source", "unknown")

        lot = Lot(
            order_id=order.get("order_id", ""),
            signal_id=sid,
            signal_source=source,
            ts=order.get("ts", ""),
            symbol=symbol,
            qty=qty,
            price=price,
            notional_usd=notional,
        )
        self._lots[symbol].append(lot)
        log.debug("BUY lot: %s %.6f @ $%.2f", symbol, qty, price)

    def sell(self, order: dict, price: float, signals: Dict[str, dict]) -> List[RoundTrip]:
        """Drain FIFO lots and return matched RoundTrips."""
        symbol = order["symbol"]
        sell_notional = float(order.get("exec_usd") or order.get("notional_usd") or 0)
        if sell_notional <= 0 or price <= 0:
            return []

        sell_qty = sell_notional / price
        sid = order.get("signal_id", "")
        sell_ts = order.get("ts", "")

        trips: List[RoundTrip] = []
        remaining = sell_qty

        while remaining > 1e-10 and self._lots[symbol]:
            lot = self._lots[symbol][0]
            matched = min(lot.remaining_qty, remaining)
            buy_notional_matched = matched * lot.price
            sell_notional_matched = matched * price

            gross_pnl = sell_notional_matched - buy_notional_matched
            gross_pct = (price - lot.price) / lot.price * 100 if lot.price > 0 else 0.0
            fees = (buy_notional_matched + sell_notional_matched) * FEE_RATE
            adj_pnl = gross_pnl - fees
            adj_pct = adj_pnl / buy_notional_matched * 100 if buy_notional_matched > 0 else 0.0

            if adj_pct > 0.05:
                verdict = "PROFITABLE"
            elif adj_pct < -0.05:
                verdict = "LOSS"
            else:
                verdict = "BREAKEVEN"

            # Hold time
            try:
                t_buy = datetime.fromisoformat(lot.ts.replace("Z", "+00:00"))
                t_sell = datetime.fromisoformat(sell_ts.replace("Z", "+00:00"))
                hold_sec = (t_sell - t_buy).total_seconds()
            except Exception:
                hold_sec = 0.0

            rt_id = f"{lot.order_id[:12]}->{order.get('order_id','')[:12]}"

            trip = RoundTrip(
                round_trip_id=rt_id,
                symbol=symbol,
                buy_signal_id=lot.signal_id,
                buy_signal_source=lot.signal_source,
                sell_signal_id=sid,
                sell_signal_source=signals.get(sid, {}).get("source", "unknown"),
                buy_ts=lot.ts,
                sell_ts=sell_ts,
                hold_seconds=hold_sec,
                qty=matched,
                buy_price=lot.price,
                sell_price=price,
                buy_notional_usd=round(buy_notional_matched, 4),
                sell_notional_usd=round(sell_notional_matched, 4),
                gross_pnl_usd=round(gross_pnl, 4),
                gross_return_pct=round(gross_pct, 4),
                est_fees_usd=round(fees, 4),
                fee_adj_pnl_usd=round(adj_pnl, 4),
                fee_adj_return_pct=round(adj_pct, 4),
                verdict=verdict,
            )
            trips.append(trip)

            lot.remaining_qty -= matched
            remaining -= matched
            if lot.remaining_qty < 1e-10:
                self._lots[symbol].popleft()

        return trips

    def open_positions(self) -> Dict[str, float]:
        """Return {symbol: remaining_notional_usd} of unclosed lots."""
        result = {}
        for sym, lots in self._lots.items():
            total = sum(l.remaining_qty * l.price for l in lots)
            if total > 0.001:
                result[sym] = round(total, 4)
        return result


# ---------------------------------------------------------------------------
# Journal writer (append-only, deduplicated)
# ---------------------------------------------------------------------------

def _load_known_rt_ids() -> set:
    known = set()
    if TRADE_JOURNAL.exists():
        for line in TRADE_JOURNAL.read_text().splitlines():
            try:
                d = json.loads(line)
                if d.get("round_trip_id"):
                    known.add(d["round_trip_id"])
            except Exception:
                pass
    return known


def _append_trips(trips: List[RoundTrip]) -> int:
    if not trips:
        return 0
    known = _load_known_rt_ids()
    new_trips = [t for t in trips if t.round_trip_id not in known]
    if not new_trips:
        return 0
    TRADE_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADE_JOURNAL, "a") as f:
        for t in new_trips:
            f.write(json.dumps({
                **t.to_dict(),
                "scored_at": datetime.now(timezone.utc).isoformat(),
            }) + "\n")
    return len(new_trips)


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def score_ledger(fetch_live: bool = False) -> Tuple[List[RoundTrip], dict]:
    """
    Score the full PnL ledger.

    Args:
        fetch_live: If True, call Coinbase API to get exact fill prices for
                    buy orders (slower but more accurate). Default False uses
                    estimated prices from available data.

    Returns:
        (round_trips, summary_stats)
    """
    orders = _load_ledger()
    signals = _load_signals()
    tracker = PositionTracker()
    all_trips: List[RoundTrip] = []

    # Price cache so we don't re-fetch the same order twice
    price_cache: Dict[str, float] = {}

    for order in orders:
        oid = order.get("order_id", "")
        side = order.get("side", "").upper()
        entry_px = order.get("entry_px")   # set on both sides = execution price

        # Determine the fill price for this order
        if entry_px:
            price = float(entry_px)
        elif fetch_live and oid:
            if oid not in price_cache:
                fetched = fetch_order_fill_price(oid)
                price_cache[oid] = fetched or 0.0
                if fetched:
                    log.info("Fetched fill price for %s: $%.2f", oid[:16], fetched)
                time.sleep(0.15)   # respect rate limits
            price = price_cache[oid]
        else:
            # Estimate from exec_usd — we don't have qty so skip
            price = 0.0

        if side == "BUY":
            if price > 0:
                tracker.buy(order, price, signals)
            else:
                log.debug("BUY %s skipped — no fill price available", oid[:16])

        elif side == "SELL":
            if price > 0:
                trips = tracker.sell(order, price, signals)
                all_trips.extend(trips)
            else:
                log.debug("SELL %s skipped — no fill price available", oid[:16])

    # Summary stats
    stats = _summarise(all_trips, tracker)
    return all_trips, stats


def _summarise(trips: List[RoundTrip], tracker: PositionTracker) -> dict:
    if not trips:
        return {
            "total_round_trips": 0,
            "open_positions": tracker.open_positions(),
        }

    profitable = [t for t in trips if t.verdict == "PROFITABLE"]
    losses     = [t for t in trips if t.verdict == "LOSS"]
    breakeven  = [t for t in trips if t.verdict == "BREAKEVEN"]

    total_gross   = sum(t.gross_pnl_usd for t in trips)
    total_fees    = sum(t.est_fees_usd for t in trips)
    total_adj     = sum(t.fee_adj_pnl_usd for t in trips)
    avg_hold      = sum(t.hold_seconds for t in trips) / len(trips)
    avg_gross_pct = sum(t.gross_return_pct for t in trips) / len(trips)

    # By signal source
    by_source: Dict[str, List[RoundTrip]] = defaultdict(list)
    for t in trips:
        by_source[t.buy_signal_source].append(t)

    source_stats = {}
    for src, src_trips in by_source.items():
        wins = sum(1 for t in src_trips if t.verdict == "PROFITABLE")
        adj_pnl = sum(t.fee_adj_pnl_usd for t in src_trips)
        source_stats[src] = {
            "count": len(src_trips),
            "win_rate_pct": round(wins / len(src_trips) * 100, 1),
            "total_fee_adj_pnl_usd": round(adj_pnl, 4),
            "avg_hold_seconds": round(sum(t.hold_seconds for t in src_trips) / len(src_trips), 1),
        }

    return {
        "total_round_trips": len(trips),
        "profitable": len(profitable),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": round(len(profitable) / len(trips) * 100, 1),
        "total_gross_pnl_usd": round(total_gross, 4),
        "total_fees_usd": round(total_fees, 4),
        "total_fee_adj_pnl_usd": round(total_adj, 4),
        "avg_hold_seconds": round(avg_hold, 1),
        "avg_gross_return_pct": round(avg_gross_pct, 4),
        "open_positions": tracker.open_positions(),
        "by_signal_source": source_stats,
    }


# ---------------------------------------------------------------------------
# Hindsight report writer
# ---------------------------------------------------------------------------

def write_hindsight_report(trips: List[RoundTrip], stats: dict) -> str:
    lines = [
        "=" * 80,
        "SIMP HINDSIGHT REPORT",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 80,
        "",
        f"Round trips scored:  {stats.get('total_round_trips', 0)}",
        f"Profitable:          {stats.get('profitable', 0)}",
        f"Loss:                {stats.get('losses', 0)}",
        f"Breakeven:           {stats.get('breakeven', 0)}",
        f"Win rate:            {stats.get('win_rate_pct', 0):.1f}%",
        "",
        f"Gross P&L:           ${stats.get('total_gross_pnl_usd', 0):+.4f}",
        f"Est. fees:           ${stats.get('total_fees_usd', 0):.4f}",
        f"Fee-adjusted P&L:    ${stats.get('total_fee_adj_pnl_usd', 0):+.4f}",
        f"Avg hold time:       {stats.get('avg_hold_seconds', 0):.0f}s",
        f"Avg gross return:    {stats.get('avg_gross_return_pct', 0):+.4f}%",
        "",
        "BY SIGNAL SOURCE",
        "-" * 60,
    ]

    for src, s in sorted(stats.get("by_signal_source", {}).items()):
        lines.append(
            f"  {src:<35} "
            f"n={s['count']:<4} "
            f"win={s['win_rate_pct']:>5.1f}%  "
            f"adj_pnl=${s['total_fee_adj_pnl_usd']:+.4f}  "
            f"avg_hold={s['avg_hold_seconds']:.0f}s"
        )

    lines += ["", "OPEN POSITIONS (unclosed lots)", "-" * 60]
    for sym, notional in stats.get("open_positions", {}).items():
        lines.append(f"  {sym:<12} ${notional:.4f} cost basis (unrealized)")
    if not stats.get("open_positions"):
        lines.append("  None — all positions closed")

    lines += ["", "ROUND TRIP DETAIL", "-" * 80]
    header = (
        f"{'Buy TS':<12} {'Sym':<10} {'Hold':>6}s  "
        f"{'Buy $':>9} {'Sell $':>9} "
        f"{'Gross%':>8} {'AdjP&L':>8}  {'Verdict':<12} Source"
    )
    lines.append(header)
    lines.append("-" * 110)

    for t in sorted(trips, key=lambda x: x.buy_ts):
        lines.append(
            f"{t.buy_ts[5:16]:<12} {t.symbol:<10} {t.hold_seconds:>7.0f}  "
            f"${t.buy_price:>8.2f} ${t.sell_price:>8.2f} "
            f"{t.gross_return_pct:>+7.3f}% ${t.fee_adj_pnl_usd:>+7.4f}  "
            f"{t.verdict:<12} {t.buy_signal_source}"
        )

    lines += [
        "",
        "LEARNING SIGNAL SUMMARY",
        "-" * 60,
        "What influenced the choices and what was the reward:",
        "",
    ]

    src_stats = stats.get("by_signal_source", {})
    for src, s in sorted(src_stats.items(), key=lambda x: x[1]["total_fee_adj_pnl_usd"]):
        adj = s["total_fee_adj_pnl_usd"]
        sign = "✓" if adj > 0 else "✗"
        lines.append(f"  {sign} {src}")
        lines.append(f"      Trades: {s['count']}  Win rate: {s['win_rate_pct']}%  "
                     f"Total P&L after fees: ${adj:+.4f}  Avg hold: {s['avg_hold_seconds']}s")
        if "timeout" in src or "fallback" in src:
            lines.append("      ⚠  This source fires when QIP has no answer — no real analysis.")
            lines.append("         Recommendation: suppress fallback signals. Only trade on real QIP output.")
        elif "bootstrap" in src:
            lines.append("      ⚠  Bootstrap sell = selling existing balance to free capital.")
            lines.append("         Not a strategy signal — just inventory management.")
        elif "manual" in src or "injection" in src:
            lines.append("      ℹ  Operator-injected signal. Treat as intentional.")
        lines.append("")

    report = "\n".join(lines)
    HINDSIGHT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    HINDSIGHT_REPORT.write_text(report)
    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="SIMP Trade Scorer — Hindsight Engine")
    parser.add_argument("--live", action="store_true",
                        help="Fetch actual fill prices from Coinbase API (slower)")
    parser.add_argument("--journal", action="store_true",
                        help="Write new round trips to trade_journal.jsonl")
    args = parser.parse_args()

    print("Loading ledger and scoring round trips...")
    trips, stats = score_ledger(fetch_live=args.live)

    if args.journal:
        written = _append_trips(trips)
        print(f"Wrote {written} new round trips to {TRADE_JOURNAL}")

    report = write_hindsight_report(trips, stats)
    print(report)


if __name__ == "__main__":
    main()
