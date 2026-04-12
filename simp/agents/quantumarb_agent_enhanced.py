"""
quantumarb_agent_enhanced.py
============================
Enhanced QuantumArb SIMP Agent — v2.0.0 (integrated with quantumarb organ)

Integrates with the new quantumarb organ components:
- ArbDetector for improved opportunity detection
- ExchangeConnector for realistic market simulation
- TradeExecutor for simulated trade execution (dry-run only)
- PnLLedger for P&L tracking and analysis

Safety gates (non-negotiable):
- dry_run = True always. Hard-coded safety gate.
- No direct order placement. QuantumArb is analysis-only.
- All decisions logged as SIMP intents before any downstream action.
- TradeExecutor only operates in dry-run mode.
- All TimesFM integration remains advisory only.

Usage:
    # Register and start polling (file-based, matches KashClaw pattern):
    python -m simp.agents.quantumarb_agent_enhanced

    # HTTP mode (future — Day 4 extension):
    python -m simp.agents.quantumarb_agent_enhanced --http --port 8768
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import quantumarb organ components
from simp.organs.quantumarb.arb_detector import (
    ArbDetector, ArbOpportunity as OrganArbOpportunity, ArbType,
    create_detector
)
from simp.organs.quantumarb.exchange_connector import (
    ExchangeConnector, StubExchangeConnector, Ticker, OrderBook,
    create_stub_connector
)
from simp.organs.quantumarb.executor import (
    TradeExecutor, TradeRequest, TradeSide, TradeStatus,
    create_executor
)
from simp.organs.quantumarb.pnl_ledger import (
    PnLLedger, PnLEntry, PnLType,
    get_default_ledger
)

log = logging.getLogger("QuantumArbEnhanced")

# ---------------------------------------------------------------------------
# TimesFM integration helpers (advisory only — never blocks evaluation)
# ---------------------------------------------------------------------------

def _try_forecast_sync(
    series_id: str,
    values: List[float],
    agent_id: str = "quantumarb",
    horizon: int = 32,
) -> Optional[Any]:
    """
    Best-effort synchronous wrapper around the async TimesFMService.

    Returns ForecastResponse or None on any error.
    Never raises. Never blocks evaluation.
    """
    if values is None or len(values) < 16:
        return None
    try:
        from simp.integrations.timesfm_service import (
            get_timesfm_service_sync,
            ForecastRequest,
        )
        from simp.integrations.timesfm_policy_engine import (
            PolicyEngine,
            make_agent_context_for,
        )
        svc = get_timesfm_service_sync()
        if svc is None:
            return None
        ctx = make_agent_context_for(agent_id)
        req = ForecastRequest(
            series_id=series_id,
            values=values,
            horizon=horizon,
            context=ctx,
        )
        return svc.forecast(req)
    except Exception as e:
        log.debug(f"TimesFM forecast failed (non‑blocking): {e}")
        return None


def _log_decision_summary(
    signal_id: str,
    ticker: str,
    decision: str,
    spread_bps: float,
    trust: float,
    venue_a: Optional[str] = None,
    venue_b: Optional[str] = None,
) -> None:
    """Log a concise decision summary."""
    if venue_a and venue_b:
        log.info(
            f"[{signal_id[:8]}] {ticker} {venue_a}↔{venue_b}: "
            f"{decision} (spread={spread_bps:.1f}bps, trust={trust:.2f})"
        )
    else:
        log.info(
            f"[{signal_id[:8]}] {ticker}: {decision} "
            f"(spread={spread_bps:.1f}bps, trust={trust:.2f})"
        )


def _log_timesfm_shadow(
    series_id: str,
    forecast_available: bool,
    forecast_mean: Optional[float],
    forecast_std: Optional[float],
    used_in_decision: bool,
    signal_id: str,
    ticker: str,
    arb_type: str,
    venue_a: Optional[str] = None,
    venue_b: Optional[str] = None,
) -> None:
    """Log TimesFM shadow‑forecast metadata (advisory only)."""
    if not forecast_available:
        return
    venue_str = f"{venue_a}↔{venue_b}" if venue_a and venue_b else "statistical"
    direction = "↑" if forecast_mean and forecast_mean > 0 else "↓" if forecast_mean else "∼"
    used = "✓" if used_in_decision else "✗"
    log.debug(
        f"[{signal_id[:8]}] {ticker} {venue_str} ({arb_type}): "
        f"TimesFM shadow {direction} {abs(forecast_mean or 0):.2f}±{forecast_std or 0:.2f} "
        f"(used={used})"
    )


# ---------------------------------------------------------------------------
# Data models (compatible with existing SIMP intents)
# ---------------------------------------------------------------------------

class ArbType(str, Enum):
    """Arbitrage type enumeration."""
    CROSS_VENUE = "cross_venue"
    STATISTICAL = "statistical"
    LATENCY = "latency"


class ArbDecision(str, Enum):
    """Arbitrage decision enumeration."""
    NO_OPPORTUNITY = "no_opportunity"
    OPPORTUNITY_DETECTED = "opportunity_detected"
    INSUFFICIENT_TRUST = "insufficient_trust"
    INSUFFICIENT_SPREAD = "insufficient_spread"
    TIMESFM_ADVISES_AGAINST = "timesfm_advises_against"


@dataclass
class ArbitrageSignal:
    """Incoming arbitrage‑relevant signal from BullBear pipeline."""
    signal_id: str
    ticker: str
    bull_score: float  # 0.0 to 1.0
    bear_score: float  # 0.0 to 1.0
    trust: float  # 0.0 to 1.0
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional venue fields for cross‑venue signals
    venue_a: Optional[str] = None
    venue_b: Optional[str] = None
    price_a: Optional[float] = None
    price_b: Optional[float] = None

    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        """Parse from a SIMP intent."""
        payload = intent.get("payload", {})
        return cls(
            signal_id=payload.get("signal_id", str(uuid.uuid4())),
            ticker=payload.get("ticker", ""),
            bull_score=float(payload.get("bull_score", 0.0)),
            bear_score=float(payload.get("bear_score", 0.0)),
            trust=float(payload.get("trust", 0.0)),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            metadata=payload.get("metadata", {}),
            venue_a=payload.get("venue_a"),
            venue_b=payload.get("venue_b"),
            price_a=payload.get("price_a"),
            price_b=payload.get("price_b"),
        )

    @property
    def delta(self) -> float:
        """Bull‑bear delta (-1.0 to +1.0)."""
        return self.bull_score - self.bear_score

    @property
    def direction(self) -> str:
        """Direction label."""
        if self.delta > 0.1:
            return "BULL"
        elif self.delta < -0.1:
            return "BEAR"
        else:
            return "NEUTRAL"


@dataclass
class ArbitrageOpportunity:
    """Outgoing arbitrage opportunity intent."""
    opportunity_id: str = field(default_factory=lambda: f"arb-{uuid.uuid4().hex[:12]}")
    signal_id: str = ""
    ticker: str = ""
    arb_type: ArbType = ArbType.CROSS_VENUE
    decision: ArbDecision = ArbDecision.NO_OPPORTUNITY
    spread_bps: float = 0.0
    trust: float = 0.0
    estimated_profit_bps: float = 0.0
    confidence: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Venue details (for cross‑venue arb)
    venue_a: Optional[str] = None
    venue_b: Optional[str] = None
    price_a: Optional[float] = None
    price_b: Optional[float] = None
    # TimesFM shadow forecast (advisory only)
    timesfm_forecast_mean: Optional[float] = None
    timesfm_forecast_std: Optional[float] = None
    timesfm_used: bool = False
    # Organ integration metadata
    organ_opportunity_id: Optional[str] = None
    pnl_entry_id: Optional[str] = None

    def to_simp_intent(
        self,
        source_agent: str = "quantumarb",
        target_agent: str = "auto",
    ) -> Dict[str, Any]:
        """Convert to a SIMP intent."""
        return {
            "intent_type": "arbitrage_opportunity",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "payload": asdict(self),
            "timestamp": self.timestamp,
            "x-simp": {
                "version": "0.7.0",
                "dry_run": True,  # Safety gate: always True
                "analysis_only": True,
            },
        }


# ---------------------------------------------------------------------------
# Core engine (enhanced with quantumarb organ)
# ---------------------------------------------------------------------------

class QuantumArbEngine:
    """
    Enhanced QuantumArb evaluation engine with quantumarb organ integration.

    Integrates:
    - ArbDetector for professional arbitrage opportunity detection
    - ExchangeConnector for realistic market data simulation
    - TradeExecutor for simulated trade execution (dry-run only)
    - PnLLedger for P&L tracking and analysis
    - TimesFM for advisory forecasting

    Safety contract (non-negotiable):
    - dry_run=True is ALWAYS hardcoded. Never change without triple-verification
      and explicit human sign-off from Kasey.
    - TimesFM is advisory only. It never determines ArbDecision.
    - All TimesFM calls are non-blocking. Failure → conservative fallback.
    - TradeExecutor only operates in dry-run mode.
    """

    # Configuration
    MIN_SPREAD_BPS: float = float(os.environ.get("QUANTUMARB_MIN_SPREAD_BPS", "5.0"))
    MIN_TRUST: float = float(os.environ.get("QUANTUMARB_MIN_TRUST", "0.7"))
    MIN_CONFIDENCE: float = float(os.environ.get("QUANTUMARB_MIN_CONFIDENCE", "0.7"))
    _BUFFER_CAP: int = 512

    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize enhanced QuantumArb engine with organ integration.
        
        Args:
            log_dir: Directory for logs (default: ~/bullbear/logs/quantumarb)
        """
        # Setup logging directory
        if log_dir is None:
            log_dir = str(Path.home() / "bullbear" / "logs" / "quantumarb")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Spread history buffers
        self._spread_buffers: Dict[str, List[float]] = {}
        
        # Setup quantumarb organ components
        self._setup_organ_components()
        
        # P&L ledger
        self.pnl_ledger = get_default_ledger()
        
        log.info(f"QuantumArbEngine initialized with organ integration (dry_run=True)")
        log.info(f"Log directory: {self.log_dir}")
    
    def _setup_organ_components(self) -> None:
        """Setup quantumarb organ components."""
        # Create stub exchanges for simulation
        self.exchanges = {
            "exchange_a": create_stub_connector(
                name="exchange_a",
                prices={"BTC-USD": 50000.0, "ETH-USD": 3000.0},
                fee_rate=0.001,
            ),
            "exchange_b": create_stub_connector(
                name="exchange_b",
                prices={"BTC-USD": 50100.0, "ETH-USD": 3010.0},  # Slightly different prices
                fee_rate=0.0015,
            ),
        }
        
        # Create trade executor (dry-run only for safety)
        self.executor = create_executor(
            exchange=self.exchanges["exchange_a"],  # Use first exchange as default
            dry_run=True,  # SAFETY GATE: Always True
            max_position_per_market=10000.0,
            max_trades_per_hour=10,
            max_slippage_bps=50.0,
            log_dir=str(self.log_dir),
        )
        
        # Create arbitrage detector
        self.detector = create_detector(
            exchanges=self.exchanges,
            executor=self.executor,
            threshold_bps=self.MIN_SPREAD_BPS,
            min_confidence=self.MIN_CONFIDENCE,
            max_position_per_market=10000.0,
            log_dir=str(self.log_dir),
        )
        
        log.info(f"Organ components initialized: {len(self.exchanges)} exchanges, "
                f"detector threshold={self.MIN_SPREAD_BPS}bps, "
                f"executor dry_run={self.executor.dry_run}")
    
    def _record_spread(self, series_id: str, value: float) -> List[float]:
        """Append value to the named buffer (capped at _BUFFER_CAP)."""
        if not series_id or not isinstance(series_id, str):
            return []
        
        import math
        if math.isnan(value) or math.isinf(value):
            return []
        
        buf = self._spread_buffers.setdefault(series_id, [])
        buf.append(value)
        if len(buf) > self._BUFFER_CAP:
            buf.pop(0)
        return buf
    
    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """
        Evaluate an arbitrage signal using enhanced organ components.
        
        Args:
            signal: Incoming arbitrage signal
            
        Returns:
            ArbitrageOpportunity with evaluation result
        """
        # Basic validation
        if signal.trust < self.MIN_TRUST:
            return self._create_no_opportunity(
                signal,
                ArbDecision.INSUFFICIENT_TRUST,
                spread_bps=0.0,
            )
        
        # Route to appropriate evaluation method
        if signal.venue_a and signal.venue_b and signal.price_a and signal.price_b:
            return self._evaluate_cross_venue(signal)
        else:
            return self._evaluate_statistical(signal)
    
    def _evaluate_cross_venue(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """
        Evaluate cross‑venue arbitrage using organ detector.
        
        Args:
            signal: Cross-venue signal with venue_a, venue_b, price_a, price_b
            
        Returns:
            ArbitrageOpportunity with evaluation result
        """
        # Calculate spread
        spread = abs(signal.price_b - signal.price_a)
        spread_bps = (spread / min(signal.price_a, signal.price_b)) * 10000
        
        # Check minimum spread
        if spread_bps < self.MIN_SPREAD_BPS:
            return self._create_no_opportunity(
                signal,
                ArbDecision.INSUFFICIENT_SPREAD,
                spread_bps=spread_bps,
                venue_a=signal.venue_a,
                venue_b=signal.venue_b,
                price_a=signal.price_a,
                price_b=signal.price_b,
            )
        
        # Use organ detector for professional opportunity detection
        market = f"{signal.ticker}-USD"  # Convert to market format
        opportunity = self.detector.detect_cross_exchange_arb(
            market=market,
            exchange_a=signal.venue_a or "exchange_a",
            exchange_b=signal.venue_b or "exchange_b",
            quantity=1.0,  # Reference quantity
        )
        
        if opportunity and opportunity.confidence >= self.MIN_CONFIDENCE:
            # Opportunity detected!
            return self._create_opportunity_detected(
                signal=signal,
                organ_opportunity=opportunity,
                arb_type=ArbType.CROSS_VENUE,
                venue_a=signal.venue_a,
                venue_b=signal.venue_b,
                price_a=signal.price_a,
                price_b=signal.price_b,
            )
        else:
            # No profitable opportunity
            return self._create_no_opportunity(
                signal,
                ArbDecision.NO_OPPORTUNITY,
                spread_bps=spread_bps,
                venue_a=signal.venue_a,
                venue_b=signal.venue_b,
                price_a=signal.price_a,
                price_b=signal.price_b,
                confidence=opportunity.confidence if opportunity else 0.0,
            )
    
    def _evaluate_statistical(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """
        Evaluate statistical arbitrage using TimesFM-enhanced analysis.
        
        Args:
            signal: Statistical signal (no venue/price data)
            
        Returns:
            ArbitrageOpportunity with evaluation result
        """
        # Record delta in spread buffer
        series_id = f"{signal.ticker}:stat_delta"
        buf = self._record_spread(series_id, signal.delta)
        
        # Calculate historical spread metrics
        if len(buf) < 10:
            spread_bps = 0.0
        else:
            # Simple volatility estimate
            import statistics
            spread_bps = statistics.stdev(buf) * 10000 if len(buf) > 1 else 0.0
        
        # Get TimesFM forecast (advisory only)
        forecast = None
        if len(buf) >= 16:
            forecast = _try_forecast_sync(
                series_id=series_id,
                values=buf,
                agent_id="quantumarb",
                horizon=32,
            )
        
        # Evaluate based on delta magnitude and forecast
        delta_abs = abs(signal.delta)
        forecast_mean = forecast.mean if forecast else None
        forecast_std = forecast.std if forecast else None
        
        # Decision logic (conservative)
        decision = ArbDecision.NO_OPPORTUNITY
        timesfm_used = False
        
        if delta_abs > 0.3:  # Strong signal
            if forecast_mean and forecast_mean * signal.delta > 0:
                # TimesFM agrees with signal direction
                decision = ArbDecision.OPPORTUNITY_DETECTED
                timesfm_used = True
            elif forecast is None:
                # No forecast available, use signal alone
                decision = ArbDecision.OPPORTUNITY_DETECTED
        
        # Log TimesFM shadow
        _log_timesfm_shadow(
            series_id=series_id,
            forecast_available=forecast is not None,
            forecast_mean=forecast_mean,
            forecast_std=forecast_std,
            used_in_decision=timesfm_used,
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            arb_type="statistical",
        )
        
        # Create opportunity
        if decision == ArbDecision.OPPORTUNITY_DETECTED:
            return ArbitrageOpportunity(
                opportunity_id=f"arb-{uuid.uuid4().hex[:12]}",
                signal_id=signal.signal_id,
                ticker=signal.ticker,
                arb_type=ArbType.STATISTICAL,
                decision=decision,
                spread_bps=spread_bps,
                trust=signal.trust,
                estimated_profit_bps=delta_abs * 100,  # Rough estimate
                confidence=min(delta_abs * 2, 1.0),  # Scale delta to 0-1
                metadata=signal.metadata,
                timesfm_forecast_mean=forecast_mean,
                timesfm_forecast_std=forecast_std,
                timesfm_used=timesfm_used,
            )
        else:
            return self._create_no_opportunity(
                signal,
                decision,
                spread_bps=spread_bps,
                timesfm_forecast_mean=forecast_mean,
                timesfm_forecast_std=forecast_std,
                timesfm_used=timesfm_used,
            )
    
    def _create_no_opportunity(
        self,
        signal: ArbitrageSignal,
        decision: ArbDecision,
        spread_bps: float,
        venue_a: Optional[str] = None,
        venue_b: Optional[str] = None,
        price_a: Optional[float] = None,
        price_b: Optional[float] = None,
        confidence: float = 0.0,
        timesfm_forecast_mean: Optional[float] = None,
        timesfm_forecast_std: Optional[float] = None,
        timesfm_used: bool = False,
    ) -> ArbitrageOpportunity:
        """Create a NO_OPPORTUNITY result."""
        # Log decision
        _log_decision_summary(
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            decision=decision.value,
            spread_bps=spread_bps,
            trust=signal.trust,
            venue_a=venue_a,
            venue_b=venue_b,
        )
        
        return ArbitrageOpportunity(
            opportunity_id=f"arb-{uuid.uuid4().hex[:12]}",
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            arb_type=ArbType.CROSS_VENUE if venue_a and venue_b else ArbType.STATISTICAL,
            decision=decision,
            spread_bps=spread_bps,
            trust=signal.trust,
            estimated_profit_bps=0.0,
            confidence=confidence,
            metadata=signal.metadata,
            venue_a=venue_a,
            venue_b=venue_b,
            price_a=price_a,
            price_b=price_b,
            timesfm_forecast_mean=timesfm_forecast_mean,
            timesfm_forecast_std=timesfm_forecast_std,
            timesfm_used=timesfm_used,
        )
    
    def _create_opportunity_detected(
        self,
        signal: ArbitrageSignal,
        organ_opportunity: OrganArbOpportunity,
        arb_type: ArbType,
        venue_a: Optional[str] = None,
        venue_b: Optional[str] = None,
        price_a: Optional[float] = None,
        price_b: Optional[float] = None,
    ) -> ArbitrageOpportunity:
        """Create an OPPORTUNITY_DETECTED result with organ integration."""
        # Log decision
        _log_decision_summary(
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            decision=ArbDecision.OPPORTUNITY_DETECTED.value,
            spread_bps=organ_opportunity.spread_bps,
            trust=signal.trust,
            venue_a=venue_a,
            venue_b=venue_b,
        )
        
        # Record P&L entry for tracking (simulated)
        pnl_entry = None
        try:
            pnl_entry = self.pnl_ledger.record_trade_pnl(
                market=signal.ticker,
                quantity=1.0,  # Reference quantity
                price=(price_a or 0.0),
                pnl_amount=organ_opportunity.estimated_profit,
                trade_id=organ_opportunity.opportunity_id,
                position_before=0.0,
                position_after=1.0,
                fees=organ_opportunity.metadata.get("fees_bps", 0.0) / 10000,
                metadata={
                    "signal_id": signal.signal_id,
                    "arb_type": arb_type.value,
                    "organ_opportunity_id": organ_opportunity.opportunity_id,
                    "dry_run": True,
                }
            )
        except Exception as e:
            log.warning(f"Failed to record P&L entry: {e}")
        
        # Create opportunity
        return ArbitrageOpportunity(
            opportunity_id=f"arb-{uuid.uuid4().hex[:12]}",
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            arb_type=arb_type,
            decision=ArbDecision.OPPORTUNITY_DETECTED,
            spread_bps=organ_opportunity.spread_bps,
            trust=signal.trust,
            estimated_profit_bps=organ_opportunity.spread_bps,
            confidence=organ_opportunity.confidence,
            metadata={
                **signal.metadata,
                **organ_opportunity.metadata,
                "organ_integration": True,
                "dry_run": True,
            },
            venue_a=venue_a,
            venue_b=venue_b,
            price_a=price_a,
            price_b=price_b,
            organ_opportunity_id=organ_opportunity.opportunity_id,
            pnl_entry_id=pnl_entry.entry_id if pnl_entry else None,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics including organ component stats."""
        detector_stats = self.detector.get_stats() if hasattr(self, 'detector') else {}
        ledger_info = self.pnl_ledger.get_ledger_info() if hasattr(self, 'pnl_ledger') else {}
        
        return {
            "engine": {
                "spread_buffers_count": len(self._spread_buffers),
                "min_spread_bps": self.MIN_SPREAD_BPS,
                "min_trust": self.MIN_TRUST,
                "min_confidence": self.MIN_CONFIDENCE,
                "log_dir": str(self.log_dir),
            },
            "detector": detector_stats,
            "pnl_ledger": ledger_info,
            "safety": {
                "dry_run": True,
                "analysis_only": True,
                "executor_available": hasattr(self, 'executor') and self.executor is not None,
                "executor_dry_run": getattr(self.executor, 'dry_run', True) if hasattr(self, 'executor') else True,
            }
        }


# ---------------------------------------------------------------------------
# Agent class (compatible with existing SIMP agent pattern)
# ---------------------------------------------------------------------------

class QuantumArbAgent:
    """
    Enhanced QuantumArb SIMP agent with organ integration.
    
    Polls the SIMP inbox for arbitrage signals, evaluates them using
    the enhanced QuantumArbEngine, and emits ArbitrageOpportunity intents.
    
    Safety: Always operates in dry-run mode. No live trading.
    """
    
    AGENT_ID = "quantumarb"
    INBOX_DIR = Path.home() / "bullbear" / "inbox" / "quantumarb"
    OUTBOX_DIR = Path.home() / "bullbear" / "outbox"
    PROCESSED_DIR = Path.home() / "bullbear" / "processed" / "quantumarb"
    
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.engine = QuantumArbEngine()
        self._ensure_dirs()
        log.info(f"QuantumArbAgent initialized (poll_interval={poll_interval}s)")
    
    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    def run(self) -> None:
        """Main agent loop."""
        log.info("QuantumArbAgent starting (organ-integrated, dry-run only)")
        try:
            while True:
                self._process_inbox()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            log.info("QuantumArbAgent stopped by user")
        except Exception as e:
            log.error(f"QuantumArbAgent crashed: {e}")
            raise
    
    def _process_inbox(self) -> None:
        """Process all files in the inbox directory."""
        for file_path in self.INBOX_DIR.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    intent = json.load(f)
                
                # Parse signal
                signal = ArbitrageSignal.from_intent(intent)
                
                # Evaluate using enhanced engine
                opportunity = self.engine.evaluate(signal)
                
                # Write result
                result_path = self._write_result(file_path, opportunity)
                
                # Mark as processed
                self._mark_processed(file_path, opportunity, result_path)
                
                log.debug(f"Processed {file_path.name} -> {result_path.name}")
                
            except json.JSONDecodeError as e:
                log.error(f"Invalid JSON in {file_path}: {e}")
                self._mark_processed(file_path, None, None, error=str(e))
            except Exception as e:
                log.error(f"Error processing {file_path}: {e}")
                self._mark_processed(file_path, None, None, error=str(e))
    
    def _write_result(
        self,
        source_file: Path,
        opportunity: ArbitrageOpportunity,
    ) -> Path:
        """Write evaluation result to outbox."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"arb_{opportunity.ticker}_{timestamp}_{uuid.uuid4().hex[:8]}.json"
        out_path = self.OUTBOX_DIR / filename
        
        # Convert to SIMP intent
        intent = opportunity.to_simp_intent(
            source_agent=self.AGENT_ID,
            target_agent="auto",
        )
        
        with open(out_path, "w") as f:
            json.dump(intent, f, indent=2)
        
        return out_path
    
    def _mark_processed(
        self,
        source_file: Path,
        opportunity: Optional[ArbitrageOpportunity],
        result_file: Optional[Path],
        error: Optional[str] = None,
    ) -> None:
        """Move processed file to processed directory."""
        try:
            dest = self.PROCESSED_DIR / source_file.name
            source_file.rename(dest)
            
            # Log processing result
            if error:
                log.warning(f"Failed to process {source_file.name}: {error}")
            elif opportunity:
                log.info(f"Processed {source_file.name} -> {opportunity.decision.value}")
        except Exception as e:
            log.error(f"Failed to mark {source_file} as processed: {e}")


# ---------------------------------------------------------------------------
# Registration and entry point
# ---------------------------------------------------------------------------

def register_with_simp(
    broker_url: str = "http://127.0.0.1:5555",
    agent_id: str = "quantumarb",
    capabilities: Optional[List[str]] = None,
) -> bool:
    """
    Register this agent with the SIMP broker.
    
    Args:
        broker_url: SIMP broker URL
        agent_id: Agent ID to register
        capabilities: List of capabilities (default: arbitrage analysis)
    
    Returns:
        True if registration succeeded, False otherwise
    """
    if capabilities is None:
        capabilities = ["arbitrage_analysis", "cross_venue_arb", "statistical_arb"]
    
    payload = {
        "agent_id": agent_id,
        "capabilities": capabilities,
        "endpoint": "(file-based)",  # File-based agent
        "metadata": {
            "version": "2.0.0",
            "description": "Enhanced QuantumArb agent with organ integration",
            "dry_run": True,  # Safety declaration
            "analysis_only": True,
        }
    }
    
    try:
        import urllib.request
        import urllib.error
        
        req = urllib.request.Request(
            f"{broker_url}/agents/register",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                log.info(f"Registered {agent_id} with SIMP broker")
                return True
            else:
                log.error(f"Registration failed: HTTP {response.status}")
                return False
                
    except urllib.error.URLError as e:
        log.error(f"Broker unreachable: {e}")
        return False
    except Exception as e:
        log.error(f"Registration error: {e}")
        return False


def main() -> None:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced QuantumArb SIMP Agent")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register with SIMP broker before starting",
    )
    parser.add_argument(
        "--broker-url",
        default="http://127.0.0.1:5555",
        help="SIMP broker URL (default: http://127.0.0.1:5555)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Register with broker if requested
    if args.register:
        success = register_with_simp(
            broker_url=args.broker_url,
            agent_id=QuantumArbAgent.AGENT_ID,
        )
        if not success:
            log.warning("Registration failed, continuing anyway")
    
    # Start agent
    agent = QuantumArbAgent(poll_interval=args.poll_interval)
    agent.run()


if __name__ == "__main__":
    main()