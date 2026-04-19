#!/usr/bin/env python3.10
"""
Phase 2: Tighten Risk and Sizing Rules

Before touching real capital, make your risk framework explicit:
- Decide max risk per trade (e.g., 0.5–1% of account; 2% is a common upper bound)
- Set daily loss halt (e.g., 2–3% total drawdown triggers hard stop)
- Define maximum gross exposure and per-asset caps
- Re-run sandbox with these exact limits enforced to ensure the code matches the risk spec
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import yaml

class RiskLevel(Enum):
    CONSERVATIVE = "conservative"  # For first real-money experiments
    MODERATE = "moderate"          # For proven strategies
    AGGRESSIVE = "aggressive"      # For maximum performance (higher risk)

class AssetClass(Enum):
    CRYPTO = "crypto"
    STOCKS = "stocks"
    FOREX = "forex"
    COMMODITIES = "commodities"
    REAL_ESTATE = "real_estate"
    PREDICTION_MARKETS = "prediction_markets"

@dataclass
class PositionLimit:
    """Per-asset position limits."""
    asset_symbol: str
    asset_class: AssetClass
    max_position_usd: float  # Maximum position size in USD
    max_position_percent: float  # Maximum as percentage of portfolio
    max_daily_trades: int  # Maximum number of trades per day
    min_holding_period_hours: float  # Minimum time between trades
    
    def to_dict(self):
        return {
            "asset_symbol": self.asset_symbol,
            "asset_class": self.asset_class.value,
            "max_position_usd": self.max_position_usd,
            "max_position_percent": self.max_position_percent,
            "max_daily_trades": self.max_daily_trades,
            "min_holding_period_hours": self.min_holding_period_hours
        }

@dataclass
class RiskParameters:
    """Core risk parameters for the trading system."""
    # Account parameters
    account_size_usd: float = 10000.0  # Default test account size
    risk_level: RiskLevel = RiskLevel.CONSERVATIVE
    
    # Per-trade risk limits
    max_risk_per_trade_percent: float = 1.0  # Maximum risk per trade as % of account
    max_risk_per_trade_usd: float = 100.0  # Maximum risk per trade in USD
    
    # Daily loss limits
    daily_loss_limit_percent: float = 2.0  # Daily loss limit as % of account
    daily_loss_limit_usd: float = 200.0  # Daily loss limit in USD
    daily_loss_hard_stop: bool = True  # Whether to halt trading after daily loss
    
    # Drawdown limits
    max_drawdown_percent: float = 10.0  # Maximum drawdown from peak
    max_drawdown_usd: float = 1000.0  # Maximum drawdown in USD
    
    # Position sizing
    max_gross_exposure_percent: float = 20.0  # Maximum gross exposure as % of account
    max_concurrent_positions: int = 5  # Maximum number of concurrent positions
    
    # Slippage and fees
    max_slippage_percent: float = 1.0  # Maximum acceptable slippage
    fee_buffer_percent: float = 0.5  # Additional buffer for fees
    
    # Time-based limits
    max_trades_per_day: int = 20
    max_trades_per_hour: int = 5
    trading_hours_start: str = "09:30"  # Market open (EST)
    trading_hours_end: str = "16:00"   # Market close (EST)
    
    # Emergency parameters
    emergency_stop_loss_percent: float = 5.0  # Emergency stop loss per position
    volatility_adjustment_factor: float = 1.5  # Adjust position size based on volatility
    
    def __post_init__(self):
        """Calculate derived values."""
        # Ensure USD values are calculated from percentages
        if self.max_risk_per_trade_usd is None:
            self.max_risk_per_trade_usd = self.account_size_usd * self.max_risk_per_trade_percent / 100
        
        if self.daily_loss_limit_usd is None:
            self.daily_loss_limit_usd = self.account_size_usd * self.daily_loss_limit_percent / 100
        
        if self.max_drawdown_usd is None:
            self.max_drawdown_usd = self.account_size_usd * self.max_drawdown_percent / 100

@dataclass
class AssetClassLimits:
    """Risk limits per asset class."""
    asset_class: AssetClass
    max_allocation_percent: float  # Maximum allocation as % of portfolio
    max_position_size_percent: float  # Maximum position size as % of allocation
    volatility_multiplier: float  # Adjust position size based on asset class volatility
    liquidity_threshold_usd: float  # Minimum liquidity for trading
    
    def to_dict(self):
        return {
            "asset_class": self.asset_class.value,
            "max_allocation_percent": self.max_allocation_percent,
            "max_position_size_percent": self.max_position_size_percent,
            "volatility_multiplier": self.volatility_multiplier,
            "liquidity_threshold_usd": self.liquidity_threshold_usd
        }

class RiskFramework:
    """Complete risk framework for the trading system."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.risk_params = RiskParameters()
        self.asset_class_limits: Dict[AssetClass, AssetClassLimits] = {}
        self.position_limits: Dict[str, PositionLimit] = {}
        self.current_exposure: Dict[str, float] = {}
        self.daily_pnl: float = 0.0
        self.max_daily_pnl: float = 0.0
        self.trades_today: int = 0
        self.emergency_stop_triggered: bool = False
        
        # Default asset class limits
        self._set_default_asset_class_limits()
        
        # Default position limits for major assets
        self._set_default_position_limits()
        
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
    
    def _set_default_asset_class_limits(self):
        """Set default limits for each asset class."""
        self.asset_class_limits = {
            AssetClass.CRYPTO: AssetClassLimits(
                asset_class=AssetClass.CRYPTO,
                max_allocation_percent=40.0,
                max_position_size_percent=25.0,
                volatility_multiplier=0.5,  # Reduce position size due to high volatility
                liquidity_threshold_usd=1000000.0
            ),
            AssetClass.STOCKS: AssetClassLimits(
                asset_class=AssetClass.STOCKS,
                max_allocation_percent=60.0,
                max_position_size_percent=33.0,
                volatility_multiplier=1.0,
                liquidity_threshold_usd=500000.0
            ),
            AssetClass.FOREX: AssetClassLimits(
                asset_class=AssetClass.FOREX,
                max_allocation_percent=30.0,
                max_position_size_percent=50.0,
                volatility_multiplier=0.8,
                liquidity_threshold_usd=2000000.0
            ),
            AssetClass.COMMODITIES: AssetClassLimits(
                asset_class=AssetClass.COMMODITIES,
                max_allocation_percent=20.0,
                max_position_size_percent=40.0,
                volatility_multiplier=0.7,
                liquidity_threshold_usd=1000000.0
            ),
            AssetClass.REAL_ESTATE: AssetClassLimits(
                asset_class=AssetClass.REAL_ESTATE,
                max_allocation_percent=25.0,
                max_position_size_percent=20.0,
                volatility_multiplier=0.3,  # Very low due to illiquidity
                liquidity_threshold_usd=50000.0
            ),
            AssetClass.PREDICTION_MARKETS: AssetClassLimits(
                asset_class=AssetClass.PREDICTION_MARKETS,
                max_allocation_percent=10.0,
                max_position_size_percent=50.0,
                volatility_multiplier=0.4,
                liquidity_threshold_usd=10000.0
            )
        }
    
    def _set_default_position_limits(self):
        """Set default position limits for major assets."""
        # Crypto
        self.position_limits["BTC-USD"] = PositionLimit(
            asset_symbol="BTC-USD",
            asset_class=AssetClass.CRYPTO,
            max_position_usd=2000.0,
            max_position_percent=20.0,
            max_daily_trades=3,
            min_holding_period_hours=1.0
        )
        
        self.position_limits["ETH-USD"] = PositionLimit(
            asset_symbol="ETH-USD",
            asset_class=AssetClass.CRYPTO,
            max_position_usd=1500.0,
            max_position_percent=15.0,
            max_daily_trades=4,
            min_holding_period_hours=0.5
        )
        
        # Stocks
        self.position_limits["SPY"] = PositionLimit(
            asset_symbol="SPY",
            asset_class=AssetClass.STOCKS,
            max_position_usd=3000.0,
            max_position_percent=30.0,
            max_daily_trades=2,
            min_holding_period_hours=2.0
        )
        
        self.position_limits["AAPL"] = PositionLimit(
            asset_symbol="AAPL",
            asset_class=AssetClass.STOCKS,
            max_position_usd=2000.0,
            max_position_percent=20.0,
            max_daily_trades=3,
            min_holding_period_hours=1.0
        )
    
    def set_risk_level(self, level: RiskLevel):
        """Adjust risk parameters based on risk level."""
        self.risk_params.risk_level = level
        
        if level == RiskLevel.CONSERVATIVE:
            self.risk_params.max_risk_per_trade_percent = 0.5
            self.risk_params.daily_loss_limit_percent = 1.5
            self.risk_params.max_drawdown_percent = 5.0
            self.risk_params.max_gross_exposure_percent = 15.0
            self.risk_params.max_concurrent_positions = 3
            
        elif level == RiskLevel.MODERATE:
            self.risk_params.max_risk_per_trade_percent = 1.0
            self.risk_params.daily_loss_limit_percent = 2.5
            self.risk_params.max_drawdown_percent = 10.0
            self.risk_params.max_gross_exposure_percent = 25.0
            self.risk_params.max_concurrent_positions = 5
            
        elif level == RiskLevel.AGGRESSIVE:
            self.risk_params.max_risk_per_trade_percent = 2.0
            self.risk_params.daily_loss_limit_percent = 4.0
            self.risk_params.max_drawdown_percent = 15.0
            self.risk_params.max_gross_exposure_percent = 40.0
            self.risk_params.max_concurrent_positions = 8
        
        # Recalculate USD values
        self.risk_params.__post_init__()
    
    def check_trade_allowed(self, symbol: str, position_size_usd: float, 
                           asset_class: AssetClass) -> Tuple[bool, str]:
        """
        Check if a trade is allowed based on risk limits.
        Returns (allowed, reason)
        """
        reasons = []
        
        # 1. Check emergency stop
        if self.emergency_stop_triggered:
            return False, "Emergency stop triggered"
        
        # 2. Check daily loss limit
        if self.daily_pnl <= -self.risk_params.daily_loss_limit_usd:
            return False, f"Daily loss limit reached: {self.daily_pnl:.2f}"
        
        # 3. Check max trades per day
        if self.trades_today >= self.risk_params.max_trades_per_day:
            return False, f"Max trades per day reached: {self.trades_today}"
        
        # 4. Check position size vs max risk per trade
        max_risk = min(self.risk_params.max_risk_per_trade_usd, 
                      self.risk_params.max_risk_per_trade_percent * self.risk_params.account_size_usd / 100)
        
        if position_size_usd > max_risk:
            reasons.append(f"Position size {position_size_usd:.2f} > max risk per trade {max_risk:.2f}")
        
        # 5. Check asset class limits
        if asset_class in self.asset_class_limits:
            limits = self.asset_class_limits[asset_class]
            current_class_exposure = sum(
                size for sym, size in self.current_exposure.items()
                if self._get_asset_class(sym) == asset_class
            )
            
            max_class_exposure = self.risk_params.account_size_usd * limits.max_allocation_percent / 100
            if current_class_exposure + position_size_usd > max_class_exposure:
                reasons.append(f"Asset class {asset_class.value} allocation exceeded")
        
        # 6. Check gross exposure
        current_gross_exposure = sum(self.current_exposure.values())
        max_gross_exposure = self.risk_params.account_size_usd * self.risk_params.max_gross_exposure_percent / 100
        
        if current_gross_exposure + position_size_usd > max_gross_exposure:
            reasons.append(f"Gross exposure limit exceeded")
        
        # 7. Check concurrent positions
        if len(self.current_exposure) >= self.risk_params.max_concurrent_positions:
            reasons.append(f"Max concurrent positions reached: {len(self.current_exposure)}")
        
        # 8. Check specific position limits
        if symbol in self.position_limits:
            limit = self.position_limits[symbol]
            if position_size_usd > limit.max_position_usd:
                reasons.append(f"Symbol {symbol} position limit exceeded")
        
        if reasons:
            return False, "; ".join(reasons)
        
        return True, "Trade allowed"
    
    def calculate_position_size(self, symbol: str, stop_loss_percent: float, 
                              asset_class: AssetClass) -> float:
        """
        Calculate maximum position size based on risk parameters.
        Uses the risk-per-trade limit and stop loss to determine size.
        """
        # Base position size from risk per trade
        max_risk_amount = min(
            self.risk_params.max_risk_per_trade_usd,
            self.risk_params.account_size_usd * self.risk_params.max_risk_per_trade_percent / 100
        )
        
        # Adjust for stop loss
        if stop_loss_percent <= 0:
            stop_loss_percent = self.risk_params.emergency_stop_loss_percent
        
        position_size = max_risk_amount / (stop_loss_percent / 100)
        
        # Apply asset class volatility multiplier
        if asset_class in self.asset_class_limits:
            multiplier = self.asset_class_limits[asset_class].volatility_multiplier
            position_size *= multiplier
        
        # Apply individual symbol limits
        if symbol in self.position_limits:
            limit = self.position_limits[symbol]
            position_size = min(position_size, limit.max_position_usd)
        
        # Apply slippage and fee buffer
        position_size *= (1 - self.risk_params.fee_buffer_percent / 100)
        position_size *= (1 - self.risk_params.max_slippage_percent / 100)
        
        return round(position_size, 2)
    
    def record_trade(self, symbol: str, position_size_usd: float, pnl_usd: float):
        """Record a trade and update exposure and P&L."""
        self.trades_today += 1
        
        # Update exposure
        if position_size_usd > 0:
            self.current_exposure[symbol] = self.current_exposure.get(symbol, 0) + position_size_usd
        else:
            # Closing position
            if symbol in self.current_exposure:
                del self.current_exposure[symbol]
        
        # Update P&L
        self.daily_pnl += pnl_usd
        
        # Update max daily P&L (for drawdown calculation)
        if self.daily_pnl > self.max_daily_pnl:
            self.max_daily_pnl = self.daily_pnl
        
        # Check for emergency stop based on drawdown
        drawdown = self.max_daily_pnl - self.daily_pnl
        if drawdown >= self.risk_params.max_drawdown_usd:
            self.emergency_stop_triggered = True
    
    def reset_daily(self):
        """Reset daily counters (call at start of each trading day)."""
        self.daily_pnl = 0.0
        self.max_daily_pnl = 0.0
        self.trades_today = 0
        # Note: current_exposure is NOT reset as positions may carry over
    
    def _get_asset_class(self, symbol: str) -> Optional[AssetClass]:
        """Determine asset class from symbol."""
        # Simple heuristic - in production, use a proper mapping
        symbol_lower = symbol.lower()
        
        if any(crypto in symbol_lower for crypto in ['btc', 'eth', 'sol', 'ada', 'matic', 'avax', 'link']):
            return AssetClass.CRYPTO
        elif any(stock in symbol_lower for stock in ['spy', 'aapl', 'msft', 'googl', 'amzn']):
            return AssetClass.STOCKS
        elif any(forex in symbol_lower for forex in ['eur', 'gbp', 'jpy', 'aud', 'cad']):
            return AssetClass.FOREX
        
        return None
    
    def save_config(self, filepath: str):
        """Save risk framework configuration to file."""
        config = {
            "risk_parameters": asdict(self.risk_params),
            "asset_class_limits": {
                ac.value: limits.to_dict() 
                for ac, limits in self.asset_class_limits.items()
            },
            "position_limits": {
                sym: limit.to_dict() 
                for sym, limit in self.position_limits.items()
            },
            "metadata": {
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "account_size_usd": self.risk_params.account_size_usd,
                "risk_level": self.risk_params.risk_level.value
            }
        }
        
        # Convert enums to strings
        config["risk_parameters"]["risk_level"] = self.risk_params.risk_level.value
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load_config(self, filepath: str):
        """Load risk framework configuration from file."""
        with open(filepath, 'r') as f:
            config = json.load(f)
        
        # Load risk parameters
        risk_params_dict = config.get("risk_parameters", {})
        self.risk_params = RiskParameters(**risk_params_dict)
        
        # Load asset class limits
        asset_limits_dict = config.get("asset_class_limits", {})
        for ac_str, limits_dict in asset_limits_dict.items():
            try:
                asset_class = AssetClass(ac_str)
                limits = AssetClassLimits(
                    asset_class=asset_class,
                    max_allocation_percent=limits_dict["max_allocation_percent"],
                    max_position_size_percent=limits_dict["max_position_size_percent"],
                    volatility_multiplier=limits_dict["volatility_multiplier"],
                    liquidity_threshold_usd=limits_dict["liquidity_threshold_usd"]
                )
                self.asset_class_limits[asset_class] = limits
            except ValueError:
                print(f"Warning: Unknown asset class {ac_str}")
        
        # Load position limits
        position_limits_dict = config.get("position_limits", {})
        for symbol, limit_dict in position_limits_dict.items():
            try:
                asset_class = AssetClass(limit_dict["asset_class"])
                limit = PositionLimit(
                    asset_symbol=symbol,
                    asset_class=asset_class,
                    max_position_usd=limit_dict["max_position_usd"],
                    max_position_percent=limit_dict["max_position_percent"],
                    max_daily_trades=limit_dict["max_daily_trades"],
                    min_holding_period_hours=limit_dict["min_holding_period_hours"]
                )
                self.position_limits[symbol] = limit
            except KeyError as e:
                print(f"Warning: Missing field in position limit for {symbol}: {e}")

def create_default_configs():
    """Create default configuration files for different risk levels."""
    framework = RiskFramework()
    
    # Conservative config (for first real-money experiments)
    framework.set_risk_level(RiskLevel.CONSERVATIVE)
    framework.risk_params.account_size_usd = 1000.0  # Small account for testing
    framework.save_config("risk_config_conservative.json")
    print("Created: risk_config_conservative.json")
    
    # Moderate config (for proven strategies)
    framework.set_risk_level(RiskLevel.MODERATE)
    framework.risk_params.account_size_usd = 10000.0
    framework.save_config("risk_config_moderate.json")
    print("Created: risk_config_moderate.json")
    
    # Aggressive config (for maximum performance)
    framework.set_risk_level(RiskLevel.AGGRESSIVE)
    framework.risk_params.account_size_usd = 50000.0
    framework.save_config("risk_config_aggressive.json")
    print("Created: risk_config_aggressive.json")
    
    # Create a summary
    summary = {
        "conservative": {
            "max_risk_per_trade_percent": 0.5,
            "max_risk_per_trade_usd": 5.0,
            "daily_loss_limit_percent": 1.5,
            "daily_loss_limit_usd": 15.0,
            "max_drawdown_percent": 5.0,
            "max_drawdown_usd": 50.0,
            "recommended_for": "First real-money experiments, microscopic testing"
        },
        "moderate": {
            "max_risk_per_trade_percent": 1.0,
            "max_risk_per_trade_usd": 100.0,
            "daily_loss_limit_percent": 2.5,
            "daily_loss_limit_usd": 250.0,
            "max_drawdown_percent": 10.0,
            "max_drawdown_usd": 1000.0,
            "recommended_for": "Proven strategies, gradual scaling"
        },
        "aggressive": {
            "max_risk_per_trade_percent": 2.0,
            "max_risk_per_trade_usd": 1000.0,
            "daily_loss_limit_percent": 4.0,
            "daily_loss_limit_usd": 2000.0,
            "max_drawdown_percent": 15.0,
            "max_drawdown_usd": 7500.0,
            "recommended_for": "Maximum performance, higher risk tolerance"
        }
    }
    
    with open("risk_config_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("Created: risk_config_summary.json")
    print("\nRisk framework configuration complete!")
    print("\nNext steps:")
    print("1. Review the generated config files")
    print("2. Integrate risk checks into QuantumArb agent")
    print("3. Run sandbox tests with risk limits enforced")
    print("4. Adjust parameters based on test results")

if __name__ == "__main__":
    create_default_configs()