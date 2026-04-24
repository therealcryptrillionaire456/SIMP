"""
ProjectX Execution Engine — Wave 5

Translates OrderIntents into broker fills. Paper-mode by default; live
execution requires explicit opt-in via ExecutionConfig.live_mode=True
AND a valid APCA_API_KEY_ID / APCA_API_SECRET_KEY in the environment.

Design:
  - Paper mode: records orders to projectx_logs/paper_fills.jsonl, returns synthetic fills
  - Live mode: submits to Alpaca REST API with idempotency via client_order_id
  - Retry: exponential backoff up to max_retries on transient 5xx errors
  - Circuit breaker: wraps every broker call — opens after 3 consecutive failures
  - All fills written to projectx_logs/fills.jsonl via AtomicWriter.append_line

Paper and live orders share the same Fill schema so downstream consumers
(pnl_tracker, trade_learning) are mode-agnostic.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .risk_engine import OrderIntent, RiskViolation, get_risk_engine

logger = logging.getLogger(__name__)

_FILLS_LOG = Path("projectx_logs/fills.jsonl")
_PAPER_LOG = Path("projectx_logs/paper_fills.jsonl")
_MAX_RETRIES = 3
_BASE_BACKOFF_S = 1.0


@dataclass
class ExecutionConfig:
    live_mode:          bool  = False
    alpaca_base_url:    str   = ""         # populated from env if blank
    max_retries:        int   = _MAX_RETRIES
    order_timeout_s:    float = 10.0
    fills_log:          str   = str(_FILLS_LOG)
    paper_log:          str   = str(_PAPER_LOG)


@dataclass
class Fill:
    """Confirmed execution record — paper or live."""
    fill_id:        str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    signal_id:      str = ""
    symbol:         str = ""
    side:           str = ""
    notional_usd:   float = 0.0
    exec_usd:       float = 0.0
    exec_price:     Optional[float] = None
    fees_usd:       float = 0.0
    order_id:       str = ""
    client_order_id: str = ""
    ts:             str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    paper:          bool = True
    error:          Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "side": self.side,
            "notional_usd": round(self.notional_usd, 6),
            "exec_usd": round(self.exec_usd, 6),
            "exec_price": self.exec_price,
            "fees_usd": round(self.fees_usd, 6),
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "ts": self.ts,
            "paper": self.paper,
            "error": self.error,
        }


class ExecutionEngine:
    """
    Submit OrderIntents to broker (paper or live).

    Usage::

        engine = ExecutionEngine()                       # paper by default
        intent = OrderIntent("sig-1", "BTC-USD", "BUY", 25.0)
        fill   = engine.execute(intent)
        print(fill.order_id, fill.exec_usd)
    """

    def __init__(self, config: Optional[ExecutionConfig] = None) -> None:
        self._cfg = config or ExecutionConfig()
        self._live = self._cfg.live_mode and self._check_live_credentials()
        if self._cfg.live_mode and not self._live:
            logger.warning(
                "live_mode=True but APCA credentials missing — falling back to paper"
            )
        Path(self._cfg.fills_log).parent.mkdir(parents=True, exist_ok=True)
        Path(self._cfg.paper_log).parent.mkdir(parents=True, exist_ok=True)

        # Circuit breaker around broker calls
        try:
            from simp.projectx.hardening import CircuitBreaker, BreakerConfig
            self._cb = CircuitBreaker("broker_api", BreakerConfig(failure_threshold=3, timeout_seconds=60))
        except Exception:
            self._cb = None

    # ── Public API ────────────────────────────────────────────────────────

    def execute(self, intent: OrderIntent) -> Fill:
        """
        Risk-check then execute an order. Returns Fill regardless of success.
        Always logs to fills_log. Raises nothing — errors land in fill.error.
        """
        # Risk gate
        try:
            get_risk_engine().check(intent)
        except RiskViolation as exc:
            fill = Fill(
                signal_id=intent.signal_id,
                symbol=intent.symbol,
                side=intent.side,
                notional_usd=intent.notional_usd,
                paper=not self._live,
                error=str(exc),
            )
            self._log_fill(fill)
            return fill

        if self._live:
            fill = self._execute_live(intent)
        else:
            fill = self._execute_paper(intent)

        self._log_fill(fill)
        if fill.success:
            try:
                get_risk_engine().record_fill(intent)
            except Exception:
                pass
        return fill

    def execute_batch(self, intents: List[OrderIntent]) -> List[Fill]:
        """Execute a list of intents sequentially."""
        return [self.execute(i) for i in intents[:50]]  # cap at 50 per batch

    def is_live(self) -> bool:
        return self._live

    # ── Paper execution ───────────────────────────────────────────────────

    def _execute_paper(self, intent: OrderIntent) -> Fill:
        coid = self._client_order_id(intent)
        fill = Fill(
            signal_id=intent.signal_id,
            symbol=intent.symbol,
            side=intent.side,
            notional_usd=intent.notional_usd,
            exec_usd=intent.notional_usd,
            exec_price=None,
            fees_usd=0.0,
            order_id=f"paper-{uuid.uuid4().hex[:8]}",
            client_order_id=coid,
            paper=True,
        )
        logger.info("[PAPER] %s %s $%.2f → %s", fill.side, fill.symbol, fill.exec_usd, fill.order_id)
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.append_line(self._cfg.paper_log, json.dumps(fill.to_dict()))
        except Exception as exc:
            logger.debug("Paper log write failed: %s", exc)
        return fill

    # ── Live execution (Alpaca) ───────────────────────────────────────────

    def _execute_live(self, intent: OrderIntent) -> Fill:
        coid = self._client_order_id(intent)
        for attempt in range(self._cfg.max_retries):
            try:
                order_data = self._alpaca_submit(intent, coid)
                fill = Fill(
                    signal_id=intent.signal_id,
                    symbol=intent.symbol,
                    side=intent.side,
                    notional_usd=intent.notional_usd,
                    exec_usd=float(order_data.get("notional") or intent.notional_usd),
                    exec_price=_safe_float(order_data.get("filled_avg_price")),
                    fees_usd=0.0,
                    order_id=order_data.get("id", ""),
                    client_order_id=coid,
                    paper=False,
                )
                logger.info(
                    "[LIVE] %s %s $%.2f → order_id=%s",
                    fill.side, fill.symbol, fill.exec_usd, fill.order_id,
                )
                return fill
            except Exception as exc:
                wait = _BASE_BACKOFF_S * (2 ** attempt)
                logger.warning(
                    "Alpaca submit attempt %d/%d failed: %s (retry in %.1fs)",
                    attempt + 1, self._cfg.max_retries, exc, wait,
                )
                if attempt < self._cfg.max_retries - 1:
                    time.sleep(wait)

        return Fill(
            signal_id=intent.signal_id,
            symbol=intent.symbol,
            side=intent.side,
            notional_usd=intent.notional_usd,
            client_order_id=coid,
            paper=False,
            error=f"All {self._cfg.max_retries} Alpaca submit attempts failed",
        )

    def _alpaca_submit(self, intent: OrderIntent, client_order_id: str) -> Dict:
        """POST a notional market order to Alpaca v2 API."""
        import urllib.request
        base = self._cfg.alpaca_base_url or os.environ.get("APCA_BASE_URL", "https://paper-api.alpaca.markets")
        api_key = os.environ.get("APCA_API_KEY_ID", "")
        api_secret = os.environ.get("APCA_API_SECRET_KEY", "")
        if not api_key or not api_secret:
            raise RuntimeError("Alpaca credentials not set in environment")

        payload = json.dumps({
            "symbol": intent.symbol,
            "notional": str(round(intent.notional_usd, 2)),
            "side": intent.side.lower(),
            "type": "market",
            "time_in_force": "day",
            "client_order_id": client_order_id,
        }).encode()

        url = f"{base.rstrip('/')}/v2/orders"
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
                "Content-Type": "application/json",
            },
        )

        def _submit():
            with urllib.request.urlopen(req, timeout=self._cfg.order_timeout_s) as resp:
                return json.loads(resp.read().decode())

        if self._cb:
            return self._cb.call(_submit)
        return _submit()

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _client_order_id(intent: OrderIntent) -> str:
        raw = f"{intent.signal_id}-{intent.symbol}-{int(time.time())}"
        suffix = hashlib.md5(raw.encode()).hexdigest()[:6]
        prefix = f"px-{intent.signal_id[:8]}-{intent.symbol[:8]}"
        return f"{prefix}-{suffix}"[:48]

    def _log_fill(self, fill: Fill) -> None:
        try:
            from simp.projectx.hardening import AtomicWriter
            AtomicWriter.append_line(self._cfg.fills_log, json.dumps(fill.to_dict()))
        except Exception as exc:
            logger.debug("Fill log write failed: %s", exc)

    @staticmethod
    def _check_live_credentials() -> bool:
        return bool(
            os.environ.get("APCA_API_KEY_ID")
            and os.environ.get("APCA_API_SECRET_KEY")
        )


def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# Module-level singleton
_engine: Optional[ExecutionEngine] = None
_engine_lock = __import__("threading").Lock()


def get_execution_engine(config: Optional[ExecutionConfig] = None) -> ExecutionEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ExecutionEngine(config)
    return _engine
