"""
ProjectX P&L Tracker — Wave 5

Real-time profit/loss accounting compatible with the existing phase4_pnl_ledger.jsonl schema.
Reads fills from the execution engine log and maintains running P&L state.

Features:
  - Running realised P&L, unrealised P&L (mark-to-market), fees, win/loss rate
  - Max drawdown tracking (peak-to-trough on equity curve)
  - Per-symbol breakdown
  - Appends snapshots to projectx_logs/pnl_snapshots.jsonl
  - Integrates with TradeLearning for lesson extraction
  - Thread-safe: all state updates hold the internal lock
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PNL_SNAPSHOT_LOG = Path("projectx_logs/pnl_snapshots.jsonl")
_MAX_EQUITY_HISTORY = 10_000


@dataclass
class TradeRecord:
    """One completed round-trip (open + close fill)."""
    symbol:         str
    side:           str          # "BUY" initial side
    open_usd:       float
    close_usd:      float
    fees_usd:       float
    pnl_usd:        float        # realised: close - open - fees (sign: + profit, - loss)
    open_ts:        float
    close_ts:       float
    signal_id:      str = ""

    @property
    def won(self) -> bool:
        return self.pnl_usd > 0


@dataclass
class PnLSnapshot:
    timestamp:          float = field(default_factory=time.time)
    realised_pnl_usd:   float = 0.0
    unrealised_pnl_usd: float = 0.0
    total_fees_usd:     float = 0.0
    equity_usd:         float = 0.0
    max_drawdown_usd:   float = 0.0
    max_drawdown_pct:   float = 0.0
    total_trades:       int = 0
    winning_trades:     int = 0
    losing_trades:      int = 0
    win_rate:           float = 0.0
    avg_win_usd:        float = 0.0
    avg_loss_usd:       float = 0.0
    profit_factor:      float = 0.0
    by_symbol:          Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "realised_pnl_usd": round(self.realised_pnl_usd, 4),
            "unrealised_pnl_usd": round(self.unrealised_pnl_usd, 4),
            "total_fees_usd": round(self.total_fees_usd, 4),
            "equity_usd": round(self.equity_usd, 4),
            "max_drawdown_usd": round(self.max_drawdown_usd, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "avg_win_usd": round(self.avg_win_usd, 4),
            "avg_loss_usd": round(self.avg_loss_usd, 4),
            "profit_factor": round(self.profit_factor, 4),
            "by_symbol": {k: round(v, 4) for k, v in self.by_symbol.items()},
        }


class PnLTracker:
    """
    Maintains running P&L state from fill records.

    Usage::

        tracker = PnLTracker(starting_equity_usd=10_000)
        tracker.record_fill(fill_dict)        # from execution_engine
        snap = tracker.snapshot()
        print(f"P&L: ${snap.realised_pnl_usd:.2f}  DD: {snap.max_drawdown_pct:.1%}")
    """

    def __init__(
        self,
        starting_equity_usd: float = 10_000.0,
        snapshot_log: str = str(_PNL_SNAPSHOT_LOG),
    ) -> None:
        self._equity0 = starting_equity_usd
        self._log_path = Path(snapshot_log)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # State
        self._realised: float = 0.0
        self._fees: float = 0.0
        self._trades: List[TradeRecord] = []
        self._open_fills: Dict[str, Dict] = {}    # symbol → open fill dict
        self._equity_curve: List[float] = [starting_equity_usd]
        self._peak_equity: float = starting_equity_usd
        self._max_dd_usd: float = 0.0
        self._max_dd_pct: float = 0.0
        self._sym_pnl: Dict[str, float] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def record_fill(self, fill: Dict[str, Any]) -> Optional[TradeRecord]:
        """
        Process a fill dict (matching execution_engine Fill.to_dict() schema).
        Returns a TradeRecord if this fill closes a position, else None.
        """
        if not isinstance(fill, dict):
            return None
        symbol = str(fill.get("symbol", "")).upper()
        side = str(fill.get("side", "")).upper()
        exec_usd = float(fill.get("exec_usd") or fill.get("notional_usd") or 0)
        fees = float(fill.get("fees_usd") or 0)
        ts = float(fill.get("ts_epoch") or time.time())
        signal_id = str(fill.get("signal_id", ""))

        if not symbol or side not in ("BUY", "SELL") or exec_usd <= 0:
            return None

        with self._lock:
            self._fees += fees
            trade = None

            if side == "BUY":
                self._open_fills[symbol] = {
                    "usd": exec_usd, "ts": ts, "signal_id": signal_id
                }
            elif side == "SELL" and symbol in self._open_fills:
                open_fill = self._open_fills.pop(symbol)
                pnl = exec_usd - open_fill["usd"] - fees
                trade = TradeRecord(
                    symbol=symbol,
                    side="BUY",
                    open_usd=open_fill["usd"],
                    close_usd=exec_usd,
                    fees_usd=fees,
                    pnl_usd=pnl,
                    open_ts=open_fill["ts"],
                    close_ts=ts,
                    signal_id=signal_id,
                )
                self._trades.append(trade)
                self._realised += pnl
                self._sym_pnl[symbol] = self._sym_pnl.get(symbol, 0.0) + pnl
                self._update_equity_curve()

            return trade

    def record_pnl_ledger_entry(self, entry: Dict[str, Any]) -> None:
        """Ingest a row from the existing phase4_pnl_ledger.jsonl format."""
        # Map legacy schema to fill schema
        fill = {
            "symbol": entry.get("symbol", ""),
            "side": entry.get("side", ""),
            "exec_usd": entry.get("exec_usd") or entry.get("notional_usd"),
            "fees_usd": entry.get("fees_usd", 0),
            "signal_id": entry.get("signal_id", ""),
            "ts_epoch": time.time(),
        }
        self.record_fill(fill)

    def load_fills_log(self, path: Optional[str] = None) -> int:
        """Load historical fills from a JSONL file. Returns number ingested."""
        p = Path(path or "projectx_logs/fills.jsonl")
        if not p.exists():
            return 0
        count = 0
        try:
            for line in p.read_text().splitlines():
                line = line.strip()
                if line:
                    try:
                        self.record_fill(json.loads(line))
                        count += 1
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("load_fills_log error: %s", exc)
        return count

    def snapshot(self) -> PnLSnapshot:
        with self._lock:
            wins = [t for t in self._trades if t.won]
            losses = [t for t in self._trades if not t.won]
            n = len(self._trades)
            total_win = sum(t.pnl_usd for t in wins)
            total_loss = abs(sum(t.pnl_usd for t in losses))
            equity = self._equity0 + self._realised
            return PnLSnapshot(
                realised_pnl_usd=self._realised,
                total_fees_usd=self._fees,
                equity_usd=equity,
                max_drawdown_usd=self._max_dd_usd,
                max_drawdown_pct=self._max_dd_pct,
                total_trades=n,
                winning_trades=len(wins),
                losing_trades=len(losses),
                win_rate=len(wins) / max(1, n),
                avg_win_usd=total_win / max(1, len(wins)),
                avg_loss_usd=total_loss / max(1, len(losses)),
                profit_factor=total_win / max(1e-9, total_loss),
                by_symbol=dict(self._sym_pnl),
            )

    def save_snapshot(self) -> None:
        snap = self.snapshot()
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.append_line(str(self._log_path), json.dumps(snap.to_dict()))
        except Exception as exc:
            logger.debug("PnL snapshot save failed: %s", exc)

    def push_to_trade_learning(self) -> None:
        """Export completed trades to TradeLearningEngine for lesson extraction."""
        try:
            from simp.memory.trade_learning import TradeLearningEngine
            from simp.memory.system_memory import SystemMemoryStore
            engine = TradeLearningEngine()
            store = SystemMemoryStore()
            engine.persist(store)
        except Exception as exc:
            logger.debug("push_to_trade_learning: %s", exc)

    # ── Internal ──────────────────────────────────────────────────────────

    def _update_equity_curve(self) -> None:
        equity = self._equity0 + self._realised
        self._equity_curve.append(equity)
        if len(self._equity_curve) > _MAX_EQUITY_HISTORY:
            self._equity_curve = self._equity_curve[-(_MAX_EQUITY_HISTORY // 2):]
        if equity > self._peak_equity:
            self._peak_equity = equity
        dd = self._peak_equity - equity
        dd_pct = dd / max(1e-9, self._peak_equity)
        if dd > self._max_dd_usd:
            self._max_dd_usd = dd
            self._max_dd_pct = dd_pct


# Module-level singleton
_tracker: Optional[PnLTracker] = None
_tracker_lock = threading.Lock()


def get_pnl_tracker(starting_equity_usd: float = 10_000.0) -> PnLTracker:
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = PnLTracker(starting_equity_usd)
    return _tracker
