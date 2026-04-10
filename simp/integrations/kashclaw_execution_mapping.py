"""
KashClaw Execution Mapping.

This module provides mapping functions to convert AgentDecisionSummary objects
into executable trade parameters for KashClaw organs.

The mapping handles:
1. Asset pair normalization (e.g., "BTC-USD" → "BTC/USDC")
2. Side mapping (buy/sell → BUY/SELL)
3. Quantity and units conversion
4. Organ selection based on asset class
5. Execution parameter generation
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from simp.financial.a2a_schema import AgentDecisionSummary, Side
from simp.integrations.trading_organ import OrganType


class AssetClass(str, Enum):
    """Asset classes for execution mapping."""
    CRYPTO = "crypto"
    STOCKS = "stocks"
    FUTURES = "futures"
    OPTIONS = "options"
    PREDICTION_MARKETS = "prediction_markets"
    REAL_ESTATE = "real_estate"
    UNKNOWN = "unknown"


class ExecutionVenue(str, Enum):
    """Supported execution venues."""
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BINANCE = "binance"
    ALPACA = "alpaca"
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    SIMULATED = "simulated"


@dataclass
class ExecutionMappingResult:
    """Result of execution mapping."""
    success: bool
    trade_params: Optional[Dict[str, Any]] = None
    organ_id: Optional[str] = None
    organ_type: Optional[OrganType] = None
    warnings: List[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class KashClawExecutionMapper:
    """
    Maps AgentDecisionSummary to KashClaw execution parameters.
    
    This class handles the conversion from agent decision summaries
    to executable trade parameters for KashClaw organs.
    """
    
    # Mapping from instrument patterns to asset classes
    ASSET_CLASS_PATTERNS = {
        r"BTC-.*|ETH-.*|SOL-.*|XRP-.*|ADA-.*": AssetClass.CRYPTO,
        r"AAPL|TSLA|SPY|QQQ|IWM|VTI": AssetClass.STOCKS,
        r"ES.*|NQ.*|YM.*|ZN.*|CL.*|NG.*": AssetClass.FUTURES,
        r".*CALL$|.*PUT$": AssetClass.OPTIONS,
        r"KALSHI-.*": AssetClass.PREDICTION_MARKETS,
        r"POLYMARKET-.*": AssetClass.PREDICTION_MARKETS,
    }
    
    # Mapping from asset classes to organ types
    ASSET_TO_ORGAN_TYPE = {
        AssetClass.CRYPTO: OrganType.SPOT_TRADING,
        AssetClass.STOCKS: OrganType.SPOT_TRADING,
        AssetClass.FUTURES: OrganType.ALGORITHMIC,  # Use algorithmic for futures
        AssetClass.OPTIONS: OrganType.ALGORITHMIC,  # Use algorithmic for options
        AssetClass.PREDICTION_MARKETS: OrganType.ALGORITHMIC,  # Use algorithmic for prediction markets
        AssetClass.REAL_ESTATE: OrganType.ALGORITHMIC,  # Use algorithmic for real estate
        AssetClass.UNKNOWN: OrganType.SPOT_TRADING,  # Default
    }
    
    # Mapping from asset classes to execution venues
    ASSET_TO_VENUE = {
        AssetClass.CRYPTO: ExecutionVenue.COINBASE,
        AssetClass.STOCKS: ExecutionVenue.ALPACA,
        AssetClass.FUTURES: ExecutionVenue.ALPACA,
        AssetClass.OPTIONS: ExecutionVenue.ALPACA,
        AssetClass.PREDICTION_MARKETS: ExecutionVenue.KALSHI,
        AssetClass.REAL_ESTATE: ExecutionVenue.SIMULATED,
        AssetClass.UNKNOWN: ExecutionVenue.SIMULATED,
    }
    
    # Default organ IDs by type
    DEFAULT_ORGAN_IDS = {
        OrganType.SPOT_TRADING: "spot:001",
        OrganType.ALGORITHMIC: "algo:001",  # Use algo for complex strategies
        OrganType.ARBITRAGE: "arb:001",
        OrganType.SCALPING: "scalp:001",
        OrganType.HEDGING: "hedge:001",
    }
    
    def __init__(self):
        """Initialize the execution mapper."""
        self._organ_registry = {}  # Would be populated from KashClawRegistry
    
    def map_decision_to_trade(
        self,
        decision: AgentDecisionSummary,
        available_organs: Optional[Dict[str, OrganType]] = None
    ) -> ExecutionMappingResult:
        """
        Map an AgentDecisionSummary to trade parameters.
        
        Args:
            decision: Agent decision summary
            available_organs: Dictionary of available organ IDs to their types
            
        Returns:
            ExecutionMappingResult with trade parameters or error
        """
        try:
            # Validate decision
            validation_result = self._validate_decision(decision)
            if not validation_result.success:
                return validation_result
            
            # Determine asset class
            asset_class = self._determine_asset_class(decision.instrument)
            
            # Determine organ type
            organ_type = self._determine_organ_type(asset_class)
            
            # Select organ ID
            organ_id = self._select_organ_id(organ_type, available_organs)
            if not organ_id:
                return ExecutionMappingResult(
                    success=False,
                    error_message=f"No available organ for type {organ_type.value}"
                )
            
            # Generate trade parameters
            trade_params = self._generate_trade_params(decision, asset_class, organ_type)
            
            # Add warnings if any
            warnings = []
            if asset_class == AssetClass.UNKNOWN:
                warnings.append(f"Unknown asset class for instrument: {decision.instrument}")
            
            if decision.confidence and decision.confidence < 0.3:
                warnings.append(f"Low confidence score: {decision.confidence}")
            
            return ExecutionMappingResult(
                success=True,
                trade_params=trade_params,
                organ_id=organ_id,
                organ_type=organ_type,
                warnings=warnings
            )
            
        except Exception as e:
            return ExecutionMappingResult(
                success=False,
                error_message=f"Mapping failed: {str(e)}"
            )
    
    def _validate_decision(self, decision: AgentDecisionSummary) -> ExecutionMappingResult:
        """
        Validate an AgentDecisionSummary.
        
        Args:
            decision: Agent decision summary
            
        Returns:
            ExecutionMappingResult indicating validation status
        """
        # Check required fields
        if not decision.agent_name:
            return ExecutionMappingResult(
                success=False,
                error_message="Missing agent_name"
            )
        
        if not decision.instrument:
            return ExecutionMappingResult(
                success=False,
                error_message="Missing instrument"
            )
        
        if not decision.side:
            return ExecutionMappingResult(
                success=False,
                error_message="Missing side"
            )
        
        if decision.quantity <= 0:
            return ExecutionMappingResult(
                success=False,
                error_message=f"Invalid quantity: {decision.quantity}"
            )
        
        if not decision.units:
            return ExecutionMappingResult(
                success=False,
                error_message="Missing units"
            )
        
        # Check confidence if provided
        if decision.confidence is not None:
            if not 0 <= decision.confidence <= 1:
                return ExecutionMappingResult(
                    success=False,
                    error_message=f"Confidence out of range: {decision.confidence}"
                )
        
        return ExecutionMappingResult(success=True)
    
    def _determine_asset_class(self, instrument: str) -> AssetClass:
        """
        Determine asset class from instrument.
        
        Args:
            instrument: Trading instrument
            
        Returns:
            AssetClass enum
        """
        import re
        
        instrument_upper = instrument.upper()
        
        # Check patterns
        for pattern, asset_class in self.ASSET_CLASS_PATTERNS.items():
            if re.match(pattern, instrument_upper):
                return asset_class
        
        # Check for common patterns
        if "-" in instrument and ("USD" in instrument_upper or "USDC" in instrument_upper):
            # Format like BTC-USD, ETH-USDC
            return AssetClass.CRYPTO
        
        if "/" in instrument and ("USD" in instrument_upper or "USDC" in instrument_upper):
            # Format like BTC/USD, ETH/USDC
            return AssetClass.CRYPTO
        
        # Default to unknown
        return AssetClass.UNKNOWN
    
    def _determine_organ_type(self, asset_class: AssetClass) -> OrganType:
        """
        Determine organ type from asset class.
        
        Args:
            asset_class: Asset class
            
        Returns:
            OrganType enum
        """
        return self.ASSET_TO_ORGAN_TYPE.get(asset_class, OrganType.SPOT_TRADING)
    
    def _select_organ_id(
        self,
        organ_type: OrganType,
        available_organs: Optional[Dict[str, OrganType]] = None
    ) -> Optional[str]:
        """
        Select organ ID for the given organ type.
        
        Args:
            organ_type: Organ type
            available_organs: Available organs dictionary
            
        Returns:
            Organ ID or None if not available
        """
        if available_organs:
            # Find first organ of the correct type
            for organ_id, org_type in available_organs.items():
                if org_type == organ_type:
                    return organ_id
        
        # Use default organ ID
        return self.DEFAULT_ORGAN_IDS.get(organ_type)
    
    def _generate_trade_params(
        self,
        decision: AgentDecisionSummary,
        asset_class: AssetClass,
        organ_type: OrganType
    ) -> Dict[str, Any]:
        """
        Generate trade parameters from decision.
        
        Args:
            decision: Agent decision summary
            asset_class: Asset class
            organ_type: Organ type
            
        Returns:
            Dictionary of trade parameters
        """
        # Normalize asset pair
        asset_pair = self._normalize_asset_pair(decision.instrument, asset_class)
        
        # Map side
        side = self._map_side(decision.side)
        
        # Generate base parameters
        params = {
            "organ_id": "",  # Will be filled by caller
            "asset_pair": asset_pair,
            "side": side,
            "quantity": decision.quantity,
            "units": decision.units,
            "source_agent": decision.agent_name,
            "decision_timestamp": decision.timestamp,
            "confidence": decision.confidence,
            "rationale": decision.rationale,
        }
        
        # Add asset class specific parameters
        if asset_class == AssetClass.CRYPTO:
            params.update(self._generate_crypto_params(decision))
        elif asset_class == AssetClass.STOCKS:
            params.update(self._generate_stock_params(decision))
        elif asset_class == AssetClass.PREDICTION_MARKETS:
            params.update(self._generate_prediction_market_params(decision))
        
        # Add volatility posture if available
        if decision.volatility_posture:
            params["volatility_posture"] = decision.volatility_posture
        
        # Add TimesFM usage flag
        if decision.timesfm_used:
            params["timesfm_used"] = True
        
        # Add horizon if available
        if decision.horizon_days:
            params["horizon_days"] = decision.horizon_days
        
        return params
    
    def _normalize_asset_pair(self, instrument: str, asset_class: AssetClass) -> str:
        """
        Normalize instrument to asset pair format.
        
        Args:
            instrument: Original instrument
            asset_class: Asset class
            
        Returns:
            Normalized asset pair
        """
        if asset_class == AssetClass.CRYPTO:
            # Convert BTC-USD to BTC/USDC
            if "-" in instrument:
                base, quote = instrument.split("-", 1)
                # Use USDC as default quote for crypto
                if quote.upper() in ["USD", "USDT", "USDC"]:
                    quote = "USDC"
                return f"{base}/{quote}"
            # Already in BTC/USD format
            return instrument
        
        elif asset_class == AssetClass.STOCKS:
            # Stocks are typically just tickers
            return instrument
        
        elif asset_class == AssetClass.PREDICTION_MARKETS:
            # Prediction markets keep their format
            return instrument
        
        # Default: return as-is
        return instrument
    
    def _map_side(self, side: Side) -> str:
        """
        Map Side enum to trade side string.
        
        Args:
            side: Side enum
            
        Returns:
            Trade side string ("BUY" or "SELL")
        """
        if side == Side.BUY:
            return "BUY"
        elif side == Side.SELL:
            return "SELL"
        else:
            # Default to BUY for unknown
            return "BUY"
    
    def _generate_crypto_params(self, decision: AgentDecisionSummary) -> Dict[str, Any]:
        """Generate crypto-specific parameters."""
        return {
            "slippage_tolerance": 0.01,  # 1% default for crypto
            "venue": self.ASSET_TO_VENUE[AssetClass.CRYPTO].value,
            "order_type": "market",  # Default to market for crypto
            "time_in_force": "gtc",  # Good till cancelled
        }
    
    def _generate_stock_params(self, decision: AgentDecisionSummary) -> Dict[str, Any]:
        """Generate stock-specific parameters."""
        return {
            "slippage_tolerance": 0.005,  # 0.5% default for stocks
            "venue": self.ASSET_TO_VENUE[AssetClass.STOCKS].value,
            "order_type": "market",
            "time_in_force": "day",  # Day order for stocks
            "notional": decision.quantity * 100,  # Example: assume $100/share
        }
    
    def _generate_prediction_market_params(self, decision: AgentDecisionSummary) -> Dict[str, Any]:
        """Generate prediction market parameters."""
        return {
            "slippage_tolerance": 0.02,  # 2% default for prediction markets
            "venue": self.ASSET_TO_VENUE[AssetClass.PREDICTION_MARKETS].value,
            "order_type": "limit",  # Usually limit for prediction markets
            "time_in_force": "gtc",
            "max_position_size": 100,  # Default limit
        }
    
    def get_execution_summary(
        self,
        decision: AgentDecisionSummary,
        mapping_result: ExecutionMappingResult
    ) -> Dict[str, Any]:
        """
        Generate execution summary for logging and monitoring.
        
        Args:
            decision: Original decision
            mapping_result: Mapping result
            
        Returns:
            Execution summary dictionary
        """
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": decision.agent_name,
            "instrument": decision.instrument,
            "original_side": decision.side.value if decision.side else None,
            "original_quantity": decision.quantity,
            "original_units": decision.units,
            "mapping_success": mapping_result.success,
        }
        
        if mapping_result.success:
            summary.update({
                "mapped_organ_id": mapping_result.organ_id,
                "mapped_organ_type": mapping_result.organ_type.value if mapping_result.organ_type else None,
                "mapped_asset_pair": mapping_result.trade_params.get("asset_pair"),
                "mapped_side": mapping_result.trade_params.get("side"),
                "warnings": mapping_result.warnings,
            })
        else:
            summary.update({
                "mapping_error": mapping_result.error_message,
            })
        
        # Add confidence and rationale if available
        if decision.confidence:
            summary["confidence"] = decision.confidence
        
        if decision.rationale:
            summary["rationale_preview"] = decision.rationale[:100] + "..." if len(decision.rationale) > 100 else decision.rationale
        
        if decision.volatility_posture:
            summary["volatility_posture"] = decision.volatility_posture
        
        if decision.timesfm_used:
            summary["timesfm_used"] = True
        
        return summary


# Module-level singleton
_EXECUTION_MAPPER = None

def get_execution_mapper() -> KashClawExecutionMapper:
    """
    Get the singleton execution mapper instance.
    
    Returns:
        KashClawExecutionMapper instance
    """
    global _EXECUTION_MAPPER
    if _EXECUTION_MAPPER is None:
        _EXECUTION_MAPPER = KashClawExecutionMapper()
    return _EXECUTION_MAPPER


def map_decision_to_trade(
    decision: AgentDecisionSummary,
    available_organs: Optional[Dict[str, OrganType]] = None
) -> ExecutionMappingResult:
    """
    Convenience function to map decision to trade.
    
    Args:
        decision: Agent decision summary
        available_organs: Available organs dictionary
        
    Returns:
        ExecutionMappingResult
    """
    mapper = get_execution_mapper()
    return mapper.map_decision_to_trade(decision, available_organs)


__all__ = [
    "KashClawExecutionMapper",
    "ExecutionMappingResult",
    "AssetClass",
    "ExecutionVenue",
    "get_execution_mapper",
    "map_decision_to_trade",
]