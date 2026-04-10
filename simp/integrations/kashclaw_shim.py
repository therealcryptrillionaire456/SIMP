"""
KashClaw SIMP Integration Shim

This module provides the integration layer between KashClaw trading organs
and the SIMP protocol. It wraps trading organs as SIMP agents, enabling
them to communicate via standardized SIMP intents and responses.

The shim handles:
- Intent routing to appropriate organs
- Parameter validation and transformation
- Result serialization for SIMP responses
- Error handling and recovery
- Execution tracking and audit logging
"""

import asyncio
import uuid
import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import json

from simp.agent import SimpAgent
from simp.intent import Intent, SimpResponse
from simp.integrations.trading_organ import (
    TradingOrgan, OrganType, OrganExecutionResult, ExecutionStatus
)
from simp.integrations.timesfm_service import (
    get_timesfm_service,
    ForecastRequest,
)
from simp.integrations.timesfm_policy_engine import (
    PolicyEngine,
    make_agent_context_for,
)


class KashClawSimpAgent(SimpAgent):
    """
    SIMP Agent wrapper for KashClaw trading organs.

    This agent acts as a gateway between the SIMP protocol and trading organs.
    When it receives a trade intent, it:
    1. Routes to the appropriate organ
    2. Validates parameters
    3. Executes the trade
    4. Returns results as a SIMP response
    """

    # Per-pair volatility history buffer: series_id → list[float]
    # Keyed by "{asset_pair}:{organ_id}:volatility"
    _VOLATILITY_BUFFER_CAP: int = 256

    def __init__(
        self,
        agent_id: str = "kashclaw:agent",
        organization: str = "kashclaw.trading",
        organs: Optional[Dict[str, TradingOrgan]] = None
    ):
        """
        Initialize KashClaw SIMP Agent.

        Args:
            agent_id: Unique identifier for this agent
            organization: Organization namespace
            organs: Dictionary of organ_id -> TradingOrgan instance
        """
        super().__init__(agent_id, organization)
        self.organs: Dict[str, TradingOrgan] = organs or {}
        self.execution_log: List[Dict[str, Any]] = []
        self._volatility_buffers: Dict[str, List[float]] = {}

        # Register intent handlers
        self.register_handler("trade", self.handle_trade)
        self.register_handler("validate_trade", self.handle_validate_trade)
        self.register_handler("organ_status", self.handle_organ_status)
        self.register_handler("execution_history", self.handle_execution_history)

    def _record_volatility(self, series_id: str, value: float) -> List[float]:
        """Append a volatility observation to the named buffer."""
        buf = self._volatility_buffers.setdefault(series_id, [])
        buf.append(value)
        if len(buf) > self._VOLATILITY_BUFFER_CAP:
            self._volatility_buffers[series_id] = buf[-self._VOLATILITY_BUFFER_CAP:]
        return self._volatility_buffers[series_id]

    async def _get_pre_trade_sizing_advice(
        self,
        asset_pair: str,
        organ_id: str,
        quantity: float,
        slippage_tolerance: float,
    ) -> Dict[str, Any]:
        """
        Call TimesFM to get volatility-adjusted sizing advice before execution.

        Returns a dict with:
            adjusted_quantity:           float — original or reduced quantity
            adjusted_slippage_tolerance: float — original or widened tolerance
            timesfm_applied:             bool  — whether TimesFM influenced sizing
            timesfm_rationale:           str   — explanation

        Safety contract:
        - Never raises. Falls back to original values on any error.
        - Never blocks trade execution (called with try/except wrapper).
        - Advisory only — organ.execute() always proceeds after this call.
        """
        result = {
            "original_quantity": quantity,
            "original_slippage_tolerance": slippage_tolerance,
            "adjusted_quantity": max(quantity, 0.0),  # Clamp to non-negative
            "adjusted_slippage_tolerance": max(slippage_tolerance, 0.0),  # Clamp to non-negative
            "timesfm_applied": False,
            "timesfm_rationale": "TimesFM sizing advice unavailable (shadow mode or disabled)",
            "risk_posture": "neutral",  # Default posture when TimesFM not involved
        }
        try:
            series_id = f"{asset_pair}:{organ_id}:volatility"
            # Use slippage_tolerance as volatility proxy (widens under stress)
            history = self._record_volatility(series_id, slippage_tolerance)

            if len(history) < 16:
                result["timesfm_rationale"] = (
                    f"TimesFM: insufficient history ({len(history)}/16 observations)"
                )
                result["risk_posture"] = "conservative"  # Insufficient data = conservative
                return result

            svc = await get_timesfm_service()
            ctx = make_agent_context_for(
                agent_id=self.agent_id,
                series_id=series_id,
                series_length=len(history),
                requesting_handler="handle_trade",
            )
            engine = PolicyEngine()
            decision = engine.evaluate(ctx)
            if decision.denied:
                result["timesfm_rationale"] = f"TimesFM policy denied: {decision.reason}"
                result["risk_posture"] = "conservative"  # Policy denied = conservative
                return result

            req = ForecastRequest(
                series_id=series_id,
                values=history,
                requesting_agent=self.agent_id,
                horizon=8,  # Short horizon for pre-trade sizing
            )
            resp = await svc.forecast(req)

            if not resp.available:
                result["timesfm_rationale"] = (
                    "TimesFM: shadow mode active — sizing unchanged"
                )
                result["risk_posture"] = "neutral"  # Shadow mode = neutral
                return result

            if resp.point_forecast and len(resp.point_forecast) > 0:
                # Filter out NaN/inf values for numerical stability
                valid_forecasts = [
                    f for f in resp.point_forecast 
                    if isinstance(f, (int, float)) and not math.isnan(f) and not math.isinf(f)
                ]
                
                if len(valid_forecasts) == 0:
                    result["timesfm_rationale"] = (
                        "TimesFM: forecast contains only invalid values (NaN/inf)"
                    )
                    result["risk_posture"] = "conservative"  # Invalid forecast = conservative
                    return result
                
                forecast_vol = sum(valid_forecasts) / len(valid_forecasts)
                current_vol = max(slippage_tolerance, 0.0001)  # Avoid division by zero
                
                # Ensure forecast_vol is finite
                if math.isnan(forecast_vol) or math.isinf(forecast_vol):
                    result["timesfm_rationale"] = (
                        f"TimesFM: invalid forecast volatility (NaN/inf)"
                    )
                    result["risk_posture"] = "conservative"  # Invalid volatility = conservative
                    return result

                if forecast_vol > current_vol * 1.5:
                    # High-volatility forecast: reduce size by 20%, widen slippage
                    adjusted_qty = round(max(quantity * 0.80, 0.0), 8)  # Ensure non-negative
                    adjusted_slip = round(min(max(slippage_tolerance, 0.0) * 1.25, 0.05), 6)
                    result.update({
                        "adjusted_quantity": adjusted_qty,
                        "adjusted_slippage_tolerance": adjusted_slip,
                        "timesfm_applied": True,
                        "timesfm_rationale": (
                            f"TimesFM volatility rising: forecast_vol={forecast_vol:.4f} "
                            f"> 1.5x current={current_vol:.4f}. "
                            f"Reduced qty by 20%, slippage widened to {adjusted_slip:.4f}."
                        ),
                        "risk_posture": "conservative",  # High volatility = conservative posture
                    })
                else:
                    result.update({
                        "timesfm_applied": False,
                        "timesfm_rationale": (
                            f"TimesFM: stable volatility forecast "
                            f"(forecast_vol={forecast_vol:.4f}). Sizing unchanged."
                        ),
                        "risk_posture": "neutral",  # Stable volatility = neutral posture
                    })
            else:
                # Empty or None forecast
                result["timesfm_rationale"] = (
                    "TimesFM: no forecast data available"
                )
                result["risk_posture"] = "conservative"  # No forecast data = conservative

        except Exception as exc:
            result["timesfm_rationale"] = f"TimesFM sizing advice error: {exc}"
            result["risk_posture"] = "conservative"  # Error = conservative

        return result

    # -----------------------------------------------------------------
    # A2A/FinancialOps Integration Hooks
    # -----------------------------------------------------------------

    def prepare_a2a_summary(
        self,
        trade_result: Dict[str, Any],
        sizing_advice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare a minimal A2A-ready summary of a KashClaw trade decision.
        
        This is a pure function that can be called by future A2A/FinancialOps
        modules to get structured data without exposing internal details.
        
        Args:
            trade_result: The full trade execution result from handle_trade()
            sizing_advice: The TimesFM sizing advice dictionary
            
        Returns:
            A2A-ready summary with:
            - Essential trade metadata
            - Risk posture and TimesFM involvement
            - No secrets, no raw API keys, no internal state
        """
        # Extract essential information
        execution = trade_result.get("execution", {})
        timesfm_sizing = trade_result.get("timesfm_sizing", {})
        
        # Build A2A summary
        summary = {
            # Trade metadata
            "trade_id": execution.get("trade_id", "unknown"),
            "asset_pair": execution.get("asset_pair", "unknown/unknown"),
            "side": execution.get("side", "unknown"),
            "quantity": execution.get("quantity", 0.0),
            "executed_price": execution.get("price", 0.0),
            "timestamp": trade_result.get("timestamp", ""),
            
            # Risk and sizing
            "risk_posture": trade_result.get("risk_posture", "neutral"),
            "timesfm_involved": timesfm_sizing.get("applied", False),
            "timesfm_rationale": timesfm_sizing.get("rationale", ""),
            
            # Execution status
            "status": trade_result.get("status", "unknown"),
            "organ_id": execution.get("organ_id", "unknown"),
            "organ_type": execution.get("organ_type", "unknown"),
            
            # Financial metrics (safe to expose)
            "fee": execution.get("fee", 0.0),
            "slippage_percent": execution.get("slippage", 0.0),
            
            # A2A compatibility markers
            "a2a_version": "0.7.0",
            "source_agent": self.agent_id,
            "summary_type": "kashclaw_trade_decision",
        }
        
        # Add sizing adjustments if TimesFM was applied
        if sizing_advice.get("timesfm_applied", False):
            summary.update({
                "original_quantity": sizing_advice.get("original_quantity", summary["quantity"]),
                "adjusted_quantity": sizing_advice.get("adjusted_quantity", summary["quantity"]),
                "original_slippage": sizing_advice.get("original_slippage_tolerance", 0.01),
                "adjusted_slippage": sizing_advice.get("adjusted_slippage_tolerance", 0.01),
                "sizing_adjustment_percent": (
                    (sizing_advice.get("adjusted_quantity", summary["quantity"]) / 
                     max(sizing_advice.get("original_quantity", summary["quantity"]), 0.0001) - 1) * 100
                    if sizing_advice.get("original_quantity", 0) > 0 else 0.0
                ),
            })
        
        return summary

    def register_organ(self, organ: TradingOrgan):
        """
        Register a trading organ with this agent.

        Args:
            organ: TradingOrgan instance to register
        """
        self.organs[organ.organ_id] = organ
        print(f"✅ Registered organ: {organ.organ_id} ({organ.organ_type.value})")

    async def handle_trade(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trading intent.

        Intent parameters:
        {
            "organ_id": "spot:001",              # Which organ to use
            "asset_pair": "SOL/USDC",            # What to trade
            "side": "BUY" | "SELL",              # Buy or sell
            "quantity": 10.5,                    # How much
            "price": 150.0,                      # Optional: limit price
            "slippage_tolerance": 0.01,          # Optional: max slippage
            "strategy_params": {...}             # Organ-specific params
        }
        """
        try:
            # Extract parameters
            organ_id = params.get("organ_id")
            if not organ_id:
                return {
                    "status": "error",
                    "error_code": "MISSING_ORGAN_ID",
                    "error_message": "organ_id is required"
                }

            # Find organ
            if organ_id not in self.organs:
                return {
                    "status": "error",
                    "error_code": "ORGAN_NOT_FOUND",
                    "error_message": f"Organ '{organ_id}' not registered"
                }

            organ = self.organs[organ_id]

            # Validate parameters
            is_valid = await organ.validate_params(params)
            if not is_valid:
                return {
                    "status": "error",
                    "error_code": "INVALID_PARAMS",
                    "error_message": f"Invalid parameters for {organ.organ_type.value}"
                }

            # TimesFM pre-trade sizing advice (advisory — never blocks execution)
            asset_pair = params.get("asset_pair", "UNKNOWN/UNKNOWN")
            quantity = float(params.get("quantity", 0.0))
            slippage_tolerance = float(params.get("slippage_tolerance", 0.01))
            sizing_advice = await self._get_pre_trade_sizing_advice(
                asset_pair=asset_pair,
                organ_id=organ_id,
                quantity=quantity,
                slippage_tolerance=slippage_tolerance,
            )
            if sizing_advice["timesfm_applied"]:
                params = dict(params)  # don't mutate the original
                params["quantity"] = sizing_advice["adjusted_quantity"]
                params["slippage_tolerance"] = sizing_advice["adjusted_slippage_tolerance"]
                params["timesfm_sizing_rationale"] = sizing_advice["timesfm_rationale"]
            else:
                params = dict(params)
                params["timesfm_sizing_rationale"] = sizing_advice["timesfm_rationale"]

            # Execute trade
            intent_id = params.get("intent_id", str(uuid.uuid4()))
            result: OrganExecutionResult = await organ.execute(params, intent_id)

            # Log execution
            await self._log_execution(result)

            # Return standardized result
            return {
                "status": "success",
                "execution": result.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
                "timesfm_sizing": {
                    "applied": sizing_advice["timesfm_applied"],
                    "rationale": sizing_advice["timesfm_rationale"],
                    "risk_posture": sizing_advice.get("risk_posture", "neutral"),
                },
                "risk_posture": sizing_advice.get("risk_posture", "neutral"),  # Also at top level for A2A
            }

        except Exception as e:
            return {
                "status": "error",
                "error_code": "EXECUTION_FAILED",
                "error_message": str(e)
            }

    async def handle_validate_trade(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate trade parameters without executing.

        Returns validation status and any warnings.
        """
        try:
            organ_id = params.get("organ_id")
            if not organ_id or organ_id not in self.organs:
                return {
                    "valid": False,
                    "error": f"Organ '{organ_id}' not found"
                }

            organ = self.organs[organ_id]
            is_valid = await organ.validate_params(params)

            return {
                "valid": is_valid,
                "organ_id": organ_id,
                "organ_type": organ.organ_type.value,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

    async def handle_organ_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get status of one or all organs.

        If organ_id is provided, returns status of that organ.
        Otherwise returns status of all registered organs.
        """
        try:
            organ_id = params.get("organ_id")

            if organ_id:
                # Single organ status
                if organ_id not in self.organs:
                    return {
                        "status": "error",
                        "error": f"Organ '{organ_id}' not found"
                    }
                organ = self.organs[organ_id]
                organ_status = await organ.get_status()
                return {
                    "organ_id": organ_id,
                    "organ_type": organ.organ_type.value,
                    "status": organ_status
                }
            else:
                # All organs status
                statuses = {}
                for oid, organ in self.organs.items():
                    organ_status = await organ.get_status()
                    statuses[oid] = {
                        "organ_type": organ.organ_type.value,
                        "status": organ_status
                    }
                return {
                    "total_organs": len(self.organs),
                    "organs": statuses
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def handle_execution_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve execution history.

        Optional parameters:
        - organ_id: Get history for specific organ
        - limit: Maximum number of records to return
        - offset: Skip this many records
        """
        try:
            organ_id = params.get("organ_id")
            limit = params.get("limit", 100)
            offset = params.get("offset", 0)

            if organ_id:
                # History for single organ
                if organ_id not in self.organs:
                    return {
                        "error": f"Organ '{organ_id}' not found"
                    }
                organ = self.organs[organ_id]
                history = organ.get_execution_history()
            else:
                # Execution log from this agent
                history = self.execution_log

            # Apply limit and offset
            sliced = history[offset:offset + limit]

            return {
                "total_records": len(history),
                "returned": len(sliced),
                "offset": offset,
                "limit": limit,
                "history": [
                    e.to_dict() if hasattr(e, 'to_dict') else e
                    for e in sliced
                ]
            }
        except Exception as e:
            return {
                "error": str(e)
            }

    async def _log_execution(self, result: OrganExecutionResult):
        """Log execution for audit trail"""
        self.execution_log.append(result.to_dict())
        if len(self.execution_log) > 1000:
            # Keep only recent 1000 executions in memory
            self.execution_log = self.execution_log[-1000:]


class KashClawRegistry:
    """
    Central registry for all KashClaw organs and agents.

    Manages organ registration, agent instantiation, and inter-organ communication.
    """

    def __init__(self):
        self.organs: Dict[str, TradingOrgan] = {}
        self.agents: Dict[str, KashClawSimpAgent] = {}

    def register_organ(self, organ: TradingOrgan):
        """Register a trading organ"""
        self.organs[organ.organ_id] = organ

    def register_agent(self, agent: KashClawSimpAgent):
        """Register a SIMP agent"""
        self.agents[agent.agent_id] = agent

    def create_agent(
        self,
        agent_id: str,
        organ_ids: Optional[List[str]] = None
    ) -> KashClawSimpAgent:
        """
        Create a new KashClaw SIMP agent with specified organs.

        Args:
            agent_id: Unique agent identifier
            organ_ids: List of organ IDs to attach to this agent

        Returns:
            KashClawSimpAgent instance
        """
        organ_dict = {}
        if organ_ids:
            for oid in organ_ids:
                if oid in self.organs:
                    organ_dict[oid] = self.organs[oid]

        agent = KashClawSimpAgent(agent_id=agent_id, organs=organ_dict)
        self.register_agent(agent)
        return agent

    def get_agent(self, agent_id: str) -> Optional[KashClawSimpAgent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)

    def get_organ(self, organ_id: str) -> Optional[TradingOrgan]:
        """Get organ by ID"""
        return self.organs.get(organ_id)

    def list_organs(self) -> List[Dict[str, str]]:
        """List all registered organs"""
        return [
            {
                "organ_id": organ.organ_id,
                "organ_type": organ.organ_type.value
            }
            for organ in self.organs.values()
        ]

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents"""
        return [
            {
                "agent_id": agent.agent_id,
                "organization": agent.organization,
                "attached_organs": len(agent.organs)
            }
            for agent in self.agents.values()
        ]


# Global registry instance
_global_registry = KashClawRegistry()


def get_registry() -> KashClawRegistry:
    """Get the global KashClaw registry"""
    return _global_registry
