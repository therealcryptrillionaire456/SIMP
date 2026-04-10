"""
quantumarb_agent.py
===================
QuantumArb SIMP Agent — v1.0.0 (scaffold)
Day 4 roadmap: Multi-Agent Orchestration with QuantumArb

Processed from CoWork inbox intent: cowork-680cc47e3431
Source: perplexity_research via SIMP broker
Task: "Scaffold QuantumArb agent class — Day 4 roadmap item"

Architecture:
    QuantumArb listens for arbitrage-relevant signals from the BullBear
    pipeline and evaluates cross-venue / latency arbitrage opportunities.
    It NEVER executes trades directly — it emits ArbitrageOpportunity
    intents back through SIMP for human or KashClaw review.

    BullBear signal (BULL/BEAR)
        → SIMP router
            → quantumarb (evaluate_arb)
                → ArbitrageOpportunity intent (dry_run only)
                    → SIMP router
                        → kashclaw / kloutbot (review)

Safety gates (non-negotiable):
    - dry_run = True always in this scaffold. Hard-coded until
      Day 4 verification passes triple-verification and Kasey
      explicitly enables live mode via config.
    - No direct order placement. QuantumArb is analysis-only.
    - All decisions logged as SIMP intents before any downstream action.

Usage:
    # Register and start polling (file-based, matches KashClaw pattern):
    python -m simp.agents.quantumarb_agent

    # HTTP mode (future — Day 4 extension):
    python -m simp.agents.quantumarb_agent --http --port 8768
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

log = logging.getLogger("QuantumArb")

# ---------------------------------------------------------------------------
# BRP integration (shadow mode — never alters arb decisions)
# ---------------------------------------------------------------------------

_brp_bridge = None  # Module-level singleton, initialised lazily

def _get_brp_bridge():
    """Lazily create a BRP bridge for shadow observations."""
    global _brp_bridge
    if _brp_bridge is None:
        try:
            from simp.security.brp_bridge import BRPBridge
            _brp_bridge = BRPBridge()
        except Exception:
            log.debug("BRP bridge not available — shadow observations disabled")
    return _brp_bridge


def _emit_brp_shadow_observation(
    action: str,
    outcome: str,
    result_data: Dict[str, Any],
    event_id: str = "",
    tags: Optional[List[str]] = None,
) -> None:
    """Emit a BRP observation in shadow mode. Never raises. Never alters decisions."""
    try:
        bridge = _get_brp_bridge()
        if bridge is None:
            return
        from simp.security.brp_models import BRPEvent, BRPEventType, BRPMode, BRPObservation

        brp_event = BRPEvent(
            source_agent="quantumarb",
            event_type=BRPEventType.ARBITRAGE.value,
            action=action,
            params=result_data,
            mode=BRPMode.SHADOW.value,
            tags=tags or ["quantumarb", "shadow"],
        )
        bridge.evaluate_event(brp_event)

        obs = BRPObservation(
            source_agent="quantumarb",
            event_id=brp_event.event_id,
            action=action,
            outcome=outcome,
            result_data=result_data,
            mode=BRPMode.SHADOW.value,
            tags=tags or ["quantumarb", "shadow"],
        )
        bridge.ingest_observation(obs)
    except Exception:
        log.debug("BRP shadow observation failed", exc_info=True)

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
        ctx = make_agent_context_for(
            agent_id=agent_id,
            series_id=series_id,
            series_length=len(values),
            requesting_handler="_try_forecast_sync",
        )
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        if decision.denied:
            log.debug("TimesFM policy denied for %s: %s", series_id, decision.reason)
            return None

        req = ForecastRequest(
            series_id=series_id,
            values=values,
            requesting_agent=agent_id,
            horizon=horizon,
        )
        # Attempt to get or create an event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run_until_complete inside a running loop;
                # schedule as a fire-and-forget (result not available synchronously)
                return None
            return loop.run_until_complete(svc.forecast(req))
        except RuntimeError:
            return asyncio.run(svc.forecast(req))
    except Exception as exc:
        log.debug("TimesFM forecast skipped for %s: %s", series_id, exc)
        return None


def _log_decision_summary(
    signal: ArbitrageSignal,
    opportunity: ArbitrageOpportunity,
    timesfm_used: bool = False,
    timesfm_rationale: Optional[str] = None,
    log_dir: Optional[str] = None,
) -> None:
    """
    Log structured decision summary for A2A/FinancialOps consumption.
    
    Args:
        signal: Input arbitrage signal
        opportunity: Output arbitrage opportunity
        timesfm_used: Whether TimesFM was consulted
        timesfm_rationale: TimesFM-specific rationale if any
        log_dir: Optional directory for logs (defaults to ~/bullbear/logs/quantumarb)
    """
    try:
        if log_dir is None:
            log_dir = os.path.expanduser("~/bullbear/logs/quantumarb")
        
        # Safely create directory
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as dir_exc:
            log.debug(f"Could not create log directory {log_dir}: {dir_exc}")
            return
        
        log_file = Path(log_dir) / "decision_summary.jsonl"
        
        # Build structured summary
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intent_id": signal.intent_id,
            "source_agent": signal.source_agent,
            "asset_pair": signal.ticker,
            "side": signal.direction,
            "decision": opportunity.decision.value.upper(),
            "arb_type": opportunity.arb_type.value,
            "dry_run": opportunity.dry_run,
            "confidence": getattr(opportunity, 'confidence', 0.0),
            "timesfm_used": timesfm_used,
            "timesfm_rationale": timesfm_rationale,
            "rationale_preview": opportunity.rationale[:200] + "..." if len(opportunity.rationale) > 200 else opportunity.rationale,
        }
        
        # Add optional fields if present
        if signal.venue_a and signal.venue_b:
            summary["venue_a"] = signal.venue_a
            summary["venue_b"] = signal.venue_b
        
        if hasattr(opportunity, 'estimated_spread_bps') and opportunity.estimated_spread_bps is not None:
            summary["estimated_spread_bps"] = opportunity.estimated_spread_bps
        
        # Safely write to file
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary) + "\n")
            log.debug("Logged decision summary for %s", signal.intent_id)
        except (IOError, OSError, PermissionError) as write_exc:
            log.debug("Could not write to decision summary log %s: %s", log_file, write_exc)
        
    except Exception as exc:
        # Catch-all for any unexpected errors
        log.debug("Failed to log decision summary for %s: %s", signal.intent_id, exc)


def _log_timesfm_shadow(
    series_id: str,
    forecast_resp: Any,
    decision: ArbDecision,
    rationale: str,
    log_dir: Optional[str] = None,
    intent_id: Optional[str] = None,
    ticker: Optional[str] = None,
    direction: Optional[str] = None,
    quantity: Optional[float] = None,
    arb_type: Optional[str] = None,
) -> None:
    """
    Log TimesFM shadow forecast to a dedicated JSONL file.
    
    Args:
        series_id: Time series identifier
        forecast_resp: ForecastResponse object (or mock)
        decision: ArbDecision (should always be NO_OPPORTUNITY in shadow mode)
        rationale: Enriched rationale string
        log_dir: Optional directory for logs (defaults to ~/bullbear/logs/quantumarb)
        intent_id: Source intent identifier for traceability
        ticker: Asset pair being evaluated
        direction: BULL/BEAR/NOTRADE direction
        quantity: Optional quantity/size context
        arb_type: Type of arbitrage being evaluated (cross_venue, statistical, etc.)
    """
    try:
        if log_dir is None:
            log_dir = os.path.expanduser("~/bullbear/logs/quantumarb")
        
        # Safely create directory
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as dir_exc:
            log.debug(f"Could not create log directory {log_dir}: {dir_exc}")
            return
        
        log_file = Path(log_dir) / "timesfm_shadow_log.jsonl"
        
        # Extract forecast summary with robust type checking
        forecast_summary = {}
        if forecast_resp is not None and hasattr(forecast_resp, 'point_forecast'):
            pf = forecast_resp.point_forecast
            # Only process if point_forecast is a non-empty list
            if isinstance(pf, list) and len(pf) > 0:
                try:
                    # Ensure all elements are numeric
                    numeric_pf = [float(x) for x in pf if isinstance(x, (int, float))]
                    if numeric_pf:
                        forecast_summary = {
                            "forecast_length": len(numeric_pf),
                            "forecast_mean": sum(numeric_pf) / len(numeric_pf),
                            "forecast_min": min(numeric_pf),
                            "forecast_max": max(numeric_pf),
                            "forecast_trend": "up" if numeric_pf[-1] > numeric_pf[0] else 
                                            "down" if numeric_pf[-1] < numeric_pf[0] else "flat",
                        }
                except (TypeError, ValueError) as calc_exc:
                    log.debug(f"Could not calculate forecast summary for {series_id}: {calc_exc}")
                    # Keep empty forecast_summary on calculation error
        
        # Safely get attributes with defaults, handling Mock objects specially
        shadow_mode = True  # Default to True for safety
        forecast_available = False
        forecast_cached = False
        
        if forecast_resp is not None:
            # For Mock objects, hasattr returns False for missing attributes
            # but getattr returns a new Mock. We need to check differently.
            if hasattr(forecast_resp, 'shadow_mode'):
                shadow_mode = forecast_resp.shadow_mode
            if hasattr(forecast_resp, 'available'):
                forecast_available = forecast_resp.available
            if hasattr(forecast_resp, 'cached'):
                forecast_cached = forecast_resp.cached
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "series_id": series_id,
            "decision": decision.value.upper(),  # Ensure consistent uppercase
            "shadow_mode": shadow_mode,
            "forecast_available": forecast_available,
            "forecast_cached": forecast_cached,
            "forecast_summary": forecast_summary,
            "rationale_preview": rationale[:200] + "..." if len(rationale) > 200 else rationale,
            "intent_id": intent_id,
            "ticker": ticker,
            "direction": direction,
            "quantity": quantity,
            "arb_type": arb_type,
        }
        
        # Safely write to file
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            log.debug("Logged TimesFM shadow forecast for %s", series_id)
        except (IOError, OSError, PermissionError) as write_exc:
            log.debug("Could not write to log file %s: %s", log_file, write_exc)
        
    except Exception as exc:
        # Catch-all for any unexpected errors
        log.debug("Failed to log TimesFM shadow forecast for %s: %s", series_id, exc)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_ID      = "quantumarb"
AGENT_VERSION = "1.0.0-scaffold"

# Safety gate — never change to False without triple-verification + human sign-off
DRY_RUN = True

# Inbox: QuantumArb watches for arb-relevant SIMP intents
ARB_INBOX = os.environ.get(
    "QUANTUMARB_INBOX",
    os.path.expanduser("~/bullbear/signals/quantumarb_inbox")
)
# Outbox: QuantumArb writes ArbitrageOpportunity intents here
ARB_OUTBOX = os.environ.get(
    "QUANTUMARB_OUTBOX",
    os.path.expanduser("~/bullbear/signals/quantumarb_outbox")
)

# Intent types this agent consumes
CONSUMED_INTENT_TYPES = frozenset({
    "evaluate_arb",           # Direct arb evaluation request
    "bullbear_signal",        # BullBear BULL/BEAR signal — check for arb angle
    "cross_venue_check",      # Explicit cross-venue check request
    "latency_arb_scan",       # Latency arbitrage scan
})

# Intent types this agent produces
PRODUCED_INTENT_TYPES = frozenset({
    "arbitrage_opportunity",  # Arb found — send to kashclaw/kloutbot for review
    "arb_no_opportunity",     # Evaluated, no arb found
    "arb_execution_decision", # Final decision (always DRY_RUN in scaffold)
})

# Hard stop — never consume these
BLOCKED_INTENT_TYPES = frozenset({
    "execute_trade", "trade", "market_order", "limit_order",
    "position_sizing", "kashclaw_execute",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ArbType(str, Enum):
    CROSS_VENUE  = "cross_venue"
    LATENCY      = "latency"
    STATISTICAL  = "statistical"
    TRIANGULAR   = "triangular"


class ArbDecision(str, Enum):
    OPPORTUNITY  = "opportunity"   # Arb exists, above threshold
    NO_OPPORTUNITY = "no_opportunity"
    BLOCKED      = "blocked"       # Safety gate triggered
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class ArbitrageSignal:
    """Input: a BullBear or arb evaluation signal received from SIMP."""
    intent_id: str
    source_agent: str
    direction: str                    # BULL / BEAR / NOTRADE
    delta: float = 0.0
    trust: float = 0.0
    contradiction_score: float = 0.0
    ticker: Optional[str] = None
    venue_a: Optional[str] = None
    venue_b: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    raw_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_intent(cls, intent: Dict[str, Any]) -> "ArbitrageSignal":
        params = intent.get("params", {})
        return cls(
            intent_id=intent.get("intent_id", str(uuid.uuid4())),
            source_agent=intent.get("source_agent", "unknown"),
            direction=params.get("direction", "NOTRADE"),
            delta=float(params.get("delta", 0.0)),
            trust=float(params.get("trust", 0.0)),
            contradiction_score=float(params.get("contradiction_score", 0.0)),
            ticker=params.get("ticker"),
            venue_a=params.get("venue_a"),
            venue_b=params.get("venue_b"),
            raw_params=params,
        )


@dataclass
class ArbitrageOpportunity:
    """Output: an arb opportunity intent written to outbox and routed via SIMP."""
    opportunity_id: str = field(
        default_factory=lambda: f"arb-{uuid.uuid4().hex[:12]}"
    )
    arb_type: ArbType = ArbType.CROSS_VENUE
    decision: ArbDecision = ArbDecision.NO_OPPORTUNITY
    source_signal_id: str = ""
    ticker: Optional[str] = None
    venue_a: Optional[str] = None
    venue_b: Optional[str] = None
    estimated_spread_bps: float = 0.0   # Basis points
    confidence: float = 0.0             # 0–1
    dry_run: bool = True                # ALWAYS True in scaffold
    rationale: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_id: str = AGENT_ID
    agent_version: str = AGENT_VERSION

    def to_simp_intent(
        self,
        target_agent: str = "simp_router",
        source_agent: str = AGENT_ID,
    ) -> Dict[str, Any]:
        """Serialize as a SIMP-routable intent dict."""
        intent_type = (
            "arbitrage_opportunity"
            if self.decision == ArbDecision.OPPORTUNITY
            else "arb_no_opportunity"
        )
        return {
            "intent_id": f"quantumarb-{uuid.uuid4().hex[:8]}",
            "intent_type": intent_type,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "params": {
                **asdict(self),
                "dry_run": True,   # Hard-coded safety gate
            },
        }


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

class QuantumArbEngine:
    """
    QuantumArb evaluation engine — TimesFM-enhanced spread trajectory analysis.

    Implements:
    - Cross-venue spread trajectory: BullBear delta history → TimesFM forecast
      of expected spread direction. Conservative: still returns NO_OPPORTUNITY
      until live order books are wired (Day 4), but enriches rationale with
      TimesFM-derived trajectory outlook.
    - Statistical arb: contradiction_score + delta series → TimesFM mean-
      reversion horizon estimate. Enriches rationale with forecast-derived
      decay signal.

    Safety contract (non-negotiable):
    - dry_run=True is ALWAYS hardcoded. Never change without triple-verification
      and explicit human sign-off from Kasey.
    - TimesFM is advisory only. It never determines ArbDecision.
    - All TimesFM calls are non-blocking. Failure → conservative fallback.
    """

    # Minimum spread in basis points before flagging an opportunity
    MIN_SPREAD_BPS: float = float(os.environ.get("QUANTUMARB_MIN_SPREAD_BPS", "5.0"))

    # Minimum BullBear trust score before engaging arb analysis
    MIN_TRUST: float = float(os.environ.get("QUANTUMARB_MIN_TRUST", "0.7"))

    # Spread history buffer cap (per series)
    _BUFFER_CAP: int = 512

    def __init__(self):
        # Per-series spread history buffers: series_id → list of float observations
        # Cross-venue key: "{ticker}:{venue_a}_vs_{venue_b}"
        # Statistical key:  "{ticker}:stat_delta"
        self._spread_buffers: Dict[str, List[float]] = {}

    def _record_spread(self, series_id: str, value: float) -> List[float]:
        """Append value to the named buffer (capped at _BUFFER_CAP)."""
        # Validate inputs
        if not series_id or not isinstance(series_id, str):
            return []
        
        # Check for NaN or infinite values
        import math
        if math.isnan(value) or math.isinf(value):
            return []
        
        buf = self._spread_buffers.setdefault(series_id, [])
        buf.append(value)
        if len(buf) > self._BUFFER_CAP:
            self._spread_buffers[series_id] = buf[-self._BUFFER_CAP:]
        return self._spread_buffers[series_id]

    def evaluate(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """
        Main evaluation entry point.
        Routes to the appropriate arb type based on signal content.
        """
        log.info(
            f"Evaluating arb for signal {signal.intent_id} "
            f"direction={signal.direction} trust={signal.trust:.2f}"
        )

        # Safety: skip low-confidence signals
        if signal.trust < self.MIN_TRUST:
            opportunity = ArbitrageOpportunity(
                decision=ArbDecision.INSUFFICIENT_DATA,
                source_signal_id=signal.intent_id,
                rationale=(
                    f"Trust score {signal.trust:.2f} below minimum "
                    f"{self.MIN_TRUST:.2f}. Skipping arb evaluation."
                ),
                dry_run=True,
            )
            # Log decision summary
            _log_decision_summary(
                signal=signal,
                opportunity=opportunity,
                timesfm_used=False,
                timesfm_rationale=None,
            )
            return opportunity

        # Safety: NOTRADE signals don't trigger arb
        if signal.direction == "NOTRADE":
            opportunity = ArbitrageOpportunity(
                decision=ArbDecision.NO_OPPORTUNITY,
                source_signal_id=signal.intent_id,
                rationale="BullBear direction=NOTRADE. No arb evaluation.",
                dry_run=True,
            )
            # Log decision summary
            _log_decision_summary(
                signal=signal,
                opportunity=opportunity,
                timesfm_used=False,
                timesfm_rationale=None,
            )
            return opportunity

        # Route to appropriate arb type
        if signal.venue_a and signal.venue_b:
            return self._evaluate_cross_venue(signal)
        else:
            return self._evaluate_statistical(signal)

    def _evaluate_cross_venue(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """
        Cross-venue arb: compare mid-prices between venue_a and venue_b.

        Live order book fetching (Day 4) is not yet implemented. Until then,
        we use the BullBear delta as a synthetic spread proxy, record it in
        the per-series history buffer, and call TimesFM (shadow mode) to derive
        a spread trajectory outlook that enriches the rationale.

        Safety: decision is always NO_OPPORTUNITY until live feeds are wired.
        dry_run is always True.
        """
        ticker = signal.ticker or "UNKNOWN"
        venue_a = signal.venue_a or "venue_a"
        venue_b = signal.venue_b or "venue_b"

        log.info(
            "Cross-venue check: %s vs %s ticker=%s delta=%.4f",
            venue_a, venue_b, ticker, signal.delta,
        )

        # Synthetic spread proxy: |delta| scaled to basis-point range
        # Real spread requires live order books (Day 4).
        synthetic_spread_bps = abs(signal.delta) * 100.0

        # Record to spread history buffer
        series_id = f"{ticker}:{venue_a}_vs_{venue_b}:spread_bps"
        history = self._record_spread(series_id, synthetic_spread_bps)

        # TimesFM: forecast spread trajectory (advisory — shadow mode)
        timesfm_rationale = ""
        forecast_resp = _try_forecast_sync(
            series_id=series_id,
            values=history,
            agent_id=AGENT_ID,
            horizon=16,
        )
        if forecast_resp is not None and forecast_resp.available and forecast_resp.point_forecast:
            pf = forecast_resp.point_forecast
            forecast_mean = sum(pf) / len(pf)
            trend = "widening" if forecast_mean > synthetic_spread_bps else "narrowing"
            timesfm_rationale = (
                f" | TimesFM spread trajectory: {trend} "
                f"(forecast_mean={forecast_mean:.2f} bps over {len(pf)} steps)"
            )
            log.debug("TimesFM cross-venue trajectory: %s for %s", trend, series_id)
        elif forecast_resp is not None and forecast_resp.shadow_mode:
            timesfm_rationale = " | TimesFM: shadow mode active (forecast suppressed)"
        
        rationale = (
            f"Cross-venue proxy spread={synthetic_spread_bps:.2f} bps "
            f"(synthetic — live order books pending Day 4). "
            f"History buffer: {len(history)} observations.{timesfm_rationale}"
        )
        
        # Log TimesFM shadow forecast with full context
        if forecast_resp is not None:
            _log_timesfm_shadow(
                series_id=series_id,
                forecast_resp=forecast_resp,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale=rationale,
                intent_id=signal.intent_id,
                ticker=ticker,
                direction=signal.direction,
                arb_type="cross_venue",
            )

        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.CROSS_VENUE,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id=signal.intent_id,
            ticker=ticker,
            venue_a=venue_a,
            venue_b=venue_b,
            estimated_spread_bps=synthetic_spread_bps,
            confidence=0.0,   # No confidence without live feeds
            rationale=rationale,
            dry_run=True,     # SAFETY GATE — hardcoded, never change
        )
        
        # Log decision summary
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=forecast_resp is not None,
            timesfm_rationale=timesfm_rationale,
        )
        
        return opportunity

    def _evaluate_statistical(self, signal: ArbitrageSignal) -> ArbitrageOpportunity:
        """
        Statistical arb: use BullBear delta + contradiction_score as proxy
        for mean-reversion opportunity.

        Uses the contradiction_score as a z-score proxy (high contradiction
        = extreme deviation from expected pair relationship). Records delta
        history and calls TimesFM (shadow mode) to estimate mean-reversion
        horizon — how many steps before the delta is expected to decay.

        Safety: decision is always NO_OPPORTUNITY until co-integration tests
        are implemented with real pair data (Day 4).
        dry_run is always True.
        """
        ticker = signal.ticker or "UNKNOWN"

        log.info(
            "Statistical arb check: ticker=%s delta=%.4f contradiction=%.4f",
            ticker, signal.delta, signal.contradiction_score,
        )

        # Use delta as the observable time series (proxy for pair spread)
        series_id = f"{ticker}:stat_delta"
        history = self._record_spread(series_id, signal.delta)

        # Contradiction score as z-score proxy
        # High contradiction (>0.5) suggests mean-reversion opportunity
        contradiction_proxy_bps = signal.contradiction_score * 100.0

        # TimesFM: forecast delta trajectory to estimate mean-reversion horizon
        timesfm_rationale = ""
        decay_horizon_estimate: Optional[int] = None

        forecast_resp = _try_forecast_sync(
            series_id=series_id,
            values=history,
            agent_id=AGENT_ID,
            horizon=32,
        )
        if forecast_resp is not None and forecast_resp.available and forecast_resp.point_forecast:
            pf = forecast_resp.point_forecast
            current_delta = signal.delta
            # Estimate steps until delta crosses zero (mean-reversion proxy)
            crossed = next(
                (i for i, v in enumerate(pf) if (v * current_delta) <= 0),
                None,
            )
            decay_horizon_estimate = crossed
            if crossed is not None:
                timesfm_rationale = (
                    f" | TimesFM mean-reversion horizon: ~{crossed} steps "
                    f"(forecast projects delta sign flip)"
                )
            else:
                timesfm_rationale = (
                    f" | TimesFM: no sign flip within {len(pf)}-step horizon "
                    f"(persistent deviation signal)"
                )
            log.debug(
                "TimesFM stat-arb horizon for %s: %s steps",
                series_id,
                crossed,
            )
        elif forecast_resp is not None and forecast_resp.shadow_mode:
            timesfm_rationale = " | TimesFM: shadow mode active (forecast suppressed)"
        
        rationale = (
            f"Statistical arb proxy: delta={signal.delta:.4f} "
            f"contradiction={signal.contradiction_score:.4f} "
            f"({contradiction_proxy_bps:.2f} bps equivalent). "
            f"History buffer: {len(history)} observations. "
            f"Co-integration test pending Day 4.{timesfm_rationale}"
        )
        
        # Log TimesFM shadow forecast with full context
        if forecast_resp is not None:
            _log_timesfm_shadow(
                series_id=series_id,
                forecast_resp=forecast_resp,
                decision=ArbDecision.NO_OPPORTUNITY,
                rationale=rationale,
                intent_id=signal.intent_id,
                ticker=ticker,
                direction=signal.direction,
                arb_type="statistical",
            )

        opportunity = ArbitrageOpportunity(
            arb_type=ArbType.STATISTICAL,
            decision=ArbDecision.NO_OPPORTUNITY,
            source_signal_id=signal.intent_id,
            ticker=ticker,
            estimated_spread_bps=contradiction_proxy_bps,
            confidence=0.0,   # No confidence without co-integration test
            rationale=rationale,
            dry_run=True,     # SAFETY GATE — hardcoded, never change
        )
        
        # Log decision summary
        _log_decision_summary(
            signal=signal,
            opportunity=opportunity,
            timesfm_used=forecast_resp is not None,
            timesfm_rationale=timesfm_rationale,
        )
        
        return opportunity


# ---------------------------------------------------------------------------
# File-based SIMP agent loop (matches KashClaw file-based pattern)
# ---------------------------------------------------------------------------

class QuantumArbAgent:
    """
    SIMP-compatible QuantumArb agent.
    Polls ARB_INBOX for incoming intents, evaluates, writes results to ARB_OUTBOX.
    """

    def __init__(self, poll_interval: float = 2.0):
        self.engine = QuantumArbEngine()
        self.poll_interval = poll_interval
        self._ensure_dirs()

    def _ensure_dirs(self):
        Path(ARB_INBOX).mkdir(parents=True, exist_ok=True)
        Path(ARB_OUTBOX).mkdir(parents=True, exist_ok=True)

    def run(self):
        log.info(f"QuantumArb Agent {AGENT_VERSION} starting")
        log.info(f"  DRY_RUN  : {DRY_RUN}  ← hardcoded True until Day 4 verification")
        log.info(f"  Inbox    : {ARB_INBOX}")
        log.info(f"  Outbox   : {ARB_OUTBOX}")
        log.info(f"  Poll     : every {self.poll_interval}s")
        log.info("Press Ctrl+C to stop")

        while True:
            try:
                self._process_inbox()
            except Exception as e:
                log.error(f"Inbox processing error: {e}")
            time.sleep(self.poll_interval)

    def _process_inbox(self):
        for fpath in sorted(Path(ARB_INBOX).glob("intent_*.json")):
            try:
                with open(fpath, encoding="utf-8") as f:
                    intent = json.load(f)

                if intent.get("_processed"):
                    continue

                intent_type = intent.get("intent_type", "").lower()

                # Firewall
                if intent_type in BLOCKED_INTENT_TYPES:
                    log.warning(
                        f"BLOCKED intent {intent.get('intent_id')} "
                        f"type={intent_type} — not a trade execution agent"
                    )
                    self._mark_processed(fpath, intent, blocked=True)
                    continue

                if intent_type not in CONSUMED_INTENT_TYPES:
                    log.debug(f"Skipping unknown intent type: {intent_type}")
                    continue

                # Process
                signal = ArbitrageSignal.from_intent(intent)
                opportunity = self.engine.evaluate(signal)

                # BRP shadow observation (never alters decision)
                _emit_brp_shadow_observation(
                    action="arb_evaluate",
                    outcome=opportunity.decision.value,
                    result_data={
                        "intent_id": intent.get("intent_id", ""),
                        "ticker": signal.ticker,
                        "direction": signal.direction,
                        "decision": opportunity.decision.value,
                        "spread_bps": opportunity.estimated_spread_bps,
                        "dry_run": opportunity.dry_run,
                    },
                    tags=["quantumarb", "shadow", signal.ticker or ""],
                )

                self._write_result(opportunity, intent)
                self._mark_processed(fpath, intent)

                log.info(
                    f"Processed {intent.get('intent_id')} → "
                    f"{opportunity.decision.value} "
                    f"(spread={opportunity.estimated_spread_bps:.1f}bps)"
                )

            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Could not process {fpath.name}: {e}")

    def _write_result(
        self,
        opportunity: ArbitrageOpportunity,
        source_intent: Dict[str, Any],
    ) -> str:
        result_intent = opportunity.to_simp_intent(
            target_agent=source_intent.get("source_agent", "simp_router"),
            source_agent=AGENT_ID,
        )
        filename = f"arb_{opportunity.opportunity_id}.json"
        path = os.path.join(ARB_OUTBOX, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result_intent, f, indent=2)
        return path

    def _mark_processed(
        self,
        fpath: Path,
        intent: Dict[str, Any],
        blocked: bool = False,
    ):
        intent["_processed"] = True
        intent["_processed_at"] = datetime.now(timezone.utc).isoformat()
        if blocked:
            intent["_blocked"] = True
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(intent, f, indent=2)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_with_simp(
    simp_url: str = "http://127.0.0.1:5555",
    api_key: Optional[str] = None,
) -> bool:
    """Register quantumarb with the SIMP broker."""
    from urllib import request as urllib_request
    from urllib.error import URLError

    payload = {
        "agent_id": AGENT_ID,
        "agent_type": "arbitrage",
        "endpoint": f"file://{ARB_INBOX}",
        "metadata": {
            "capabilities": ["arbitrage", "cross_venue", "latency_arbitrage"],
            "description": (
                "QuantumArb arbitrage agent — evaluates cross-venue and "
                "statistical arb opportunities from BullBear signals. "
                "Analysis only. dry_run=True always."
            ),
            "version": AGENT_VERSION,
            "dry_run_safe": True,
            "trade_execution": False,
            "inbox_path": ARB_INBOX,
            "outbox_path": ARB_OUTBOX,
            "scaffold": True,   # Flag: Day 4 implementation pending
        },
    }
    url = f"{simp_url}/agents/register"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-SIMP-API-Key"] = api_key
    try:
        req = urllib_request.Request(url, data=data, headers=headers, method="POST")
        with urllib_request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            log.info(f"Registered quantumarb with SIMP: {body}")
            return True
    except URLError as e:
        log.warning(f"Could not register with SIMP: {e}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="QuantumArb SIMP Agent")
    parser.add_argument("--simp-url", default="http://127.0.0.1:5555")
    parser.add_argument("--simp-api-key", default=os.environ.get("SIMP_API_KEY"))
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    if not args.no_register:
        register_with_simp(args.simp_url, args.simp_api_key)

    agent = QuantumArbAgent(poll_interval=args.poll_interval)
    agent.run()


if __name__ == "__main__":
    main()
