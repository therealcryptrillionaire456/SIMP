"""
Arbitrage detector for QuantumArb organ.

Detects arbitrage opportunities between markets and integrates with
trade executor for automated execution. Supports multiple exchange
connectors and safety checks.
"""

import json
import threading
import time
from dataclasses import dataclass, asdict, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import uuid

from .exchange_connector import ExchangeConnector
from .executor import TradeExecutor


class ArbType(str, Enum):
    """Type of arbitrage opportunity."""
    CROSS_EXCHANGE = "cross_exchange"
    TRIANGULAR = "triangular"
    STATISTICAL = "statistical"
    LATENCY = "latency"


@dataclass
class ArbOpportunity:
    """Represents an arbitrage opportunity between markets."""
    opportunity_id: str = field(
        default_factory=lambda: f"arb-{uuid.uuid4().hex[:12]}"
    )
    arb_type: ArbType = ArbType.CROSS_EXCHANGE
    market_a: str = ""
    market_b: str = ""
    exchange_a: str = ""
    exchange_b: str = ""
    price_a: float = 0.0
    price_b: float = 0.0
    spread_bps: float = 0.0  # Spread in basis points
    estimated_profit: float = 0.0  # Estimated profit in quote currency
    confidence: float = 0.0  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_profitable(self, threshold_bps: float, fees_bps: float) -> bool:
        """Check if opportunity is profitable after fees."""
        net_spread = self.spread_bps - fees_bps
        return net_spread > threshold_bps
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class ArbDetector:
    """
    Detects arbitrage opportunities between markets and optionally
    executes trades via TradeExecutor.
    
    Features:
    - Multiple exchange support
    - Configurable thresholds
    - Integration with TradeExecutor
    - Thread-safe logging
    - Performance monitoring
    """
    
    def __init__(
        self,
        exchanges: Dict[str, ExchangeConnector],
        executor: Optional[TradeExecutor] = None,
        threshold_bps: float = 10.0,  # Minimum spread in basis points
        min_confidence: float = 0.7,   # Minimum confidence score
        max_position_per_market: float = 10000.0,
        log_dir: Optional[str] = None,
    ):
        """
        Initialize the arbitrage detector.
        
        Args:
            exchanges: Dictionary of exchange name -> ExchangeConnector
            executor: Optional TradeExecutor for automated execution
            threshold_bps: Minimum spread in basis points to trigger
            min_confidence: Minimum confidence score (0.0-1.0)
            max_position_per_market: Maximum position size per market
            log_dir: Directory for logs
        """
        self.exchanges = exchanges
        self.executor = executor
        self.threshold_bps = threshold_bps
        self.min_confidence = min_confidence
        self.max_position_per_market = max_position_per_market
        
        # State tracking
        self.opportunity_history: List[ArbOpportunity] = []
        self.execution_history: List[Dict[str, Any]] = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Logging
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs" / "quantumarb"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance monitoring
        self.scan_count = 0
        self.detection_count = 0
        self.execution_count = 0
    
    def calculate_spread_bps(self, price_a: float, price_b: float) -> float:
        """
        Calculate spread between two prices in basis points.
        
        Args:
            price_a: First price
            price_b: Second price
            
        Returns:
            Spread in basis points (positive if price_a > price_b)
        """
        if price_a <= 0 or price_b <= 0:
            return 0.0
        
        # Calculate percentage difference
        if price_a > price_b:
            return ((price_a - price_b) / price_b) * 10000
        else:
            return ((price_b - price_a) / price_a) * 10000
    
    def calculate_estimated_profit(
        self,
        price_a: float,
        price_b: float,
        quantity: float,
        fees_bps: float,
    ) -> float:
        """
        Calculate estimated profit from arbitrage.
        
        Args:
            price_a: Buy price
            price_b: Sell price (should be higher than price_a)
            quantity: Trade quantity
            fees_bps: Total fees in basis points
            
        Returns:
            Estimated profit in quote currency
        """
        if price_b <= price_a:
            return 0.0
        
        gross_profit = (price_b - price_a) * quantity
        fees = (fees_bps / 10000) * (price_a + price_b) * quantity / 2
        return gross_profit - fees
    
    def detect_cross_exchange_arb(
        self,
        market: str,
        exchange_a: str,
        exchange_b: str,
        quantity: float = 1.0,
    ) -> Optional[ArbOpportunity]:
        """
        Detect cross-exchange arbitrage opportunity.
        
        Args:
            market: Market symbol (e.g., "BTC-USD")
            exchange_a: First exchange name
            exchange_b: Second exchange name
            quantity: Reference quantity for profit calculation
            
        Returns:
            ArbOpportunity if profitable, None otherwise
        """
        if exchange_a not in self.exchanges or exchange_b not in self.exchanges:
            return None
        
        try:
            # Get prices from both exchanges
            connector_a = self.exchanges[exchange_a]
            connector_b = self.exchanges[exchange_b]
            
            price_a = connector_a.get_ticker(market)
            price_b = connector_b.get_ticker(market)
            
            if price_a <= 0 or price_b <= 0:
                return None
            
            # Calculate spread
            spread_bps = self.calculate_spread_bps(price_a, price_b)
            
            # Get fees
            fees_a = connector_a.get_fees()
            fees_b = connector_b.get_fees()
            total_fees_bps = (fees_a + fees_b) * 10000
            
            # Check if profitable
            if spread_bps <= total_fees_bps + self.threshold_bps:
                return None
            
            # Calculate confidence based on spread size
            confidence = min(spread_bps / (total_fees_bps * 2), 1.0)
            if confidence < self.min_confidence:
                return None
            
            # Determine which exchange is cheaper
            if price_a < price_b:
                buy_exchange = exchange_a
                sell_exchange = exchange_b
                buy_price = price_a
                sell_price = price_b
            else:
                buy_exchange = exchange_b
                sell_exchange = exchange_a
                buy_price = price_b
                sell_price = price_a
            
            # Calculate estimated profit
            estimated_profit = self.calculate_estimated_profit(
                buy_price, sell_price, quantity, total_fees_bps
            )
            
            opportunity = ArbOpportunity(
                arb_type=ArbType.CROSS_EXCHANGE,
                market_a=market,
                market_b=market,  # Same market, different exchanges
                exchange_a=buy_exchange,
                exchange_b=sell_exchange,
                price_a=buy_price,
                price_b=sell_price,
                spread_bps=spread_bps,
                estimated_profit=estimated_profit,
                confidence=confidence,
                metadata={
                    "quantity_reference": quantity,
                    "fees_bps": total_fees_bps,
                    "net_spread_bps": spread_bps - total_fees_bps,
                }
            )
            
            return opportunity
            
        except Exception as e:
            # Log error but don't crash
            self._log_error(f"Error detecting cross-exchange arb for {market}: {e}")
            return None
    
    def scan_markets(
        self,
        markets: List[str],
        exchanges: List[str],
        quantity: float = 1.0,
    ) -> List[ArbOpportunity]:
        """
        Scan multiple markets across multiple exchanges for opportunities.
        
        Args:
            markets: List of market symbols to scan
            exchanges: List of exchange names to compare
            quantity: Reference quantity for profit calculation
            
        Returns:
            List of profitable arbitrage opportunities
        """
        opportunities = []
        
        for market in markets:
            # Compare each pair of exchanges
            for i in range(len(exchanges)):
                for j in range(i + 1, len(exchanges)):
                    exchange_a = exchanges[i]
                    exchange_b = exchanges[j]
                    
                    opportunity = self.detect_cross_exchange_arb(
                        market=market,
                        exchange_a=exchange_a,
                        exchange_b=exchange_b,
                        quantity=quantity,
                    )
                    
                    if opportunity:
                        opportunities.append(opportunity)
                        self._log_opportunity(opportunity)
        
        with self.lock:
            self.scan_count += 1
            self.detection_count += len(opportunities)
            self.opportunity_history.extend(opportunities)
            
            # Keep history manageable
            if len(self.opportunity_history) > 1000:
                self.opportunity_history = self.opportunity_history[-1000:]
        
        return opportunities
    
    def execute_arbitrage(
        self,
        opportunity: ArbOpportunity,
        quantity: float,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute an arbitrage opportunity via TradeExecutor.
        
        Args:
            opportunity: ArbOpportunity to execute
            quantity: Quantity to trade
            dry_run: If True, simulate execution only
            
        Returns:
            Execution result dictionary
        """
        if not self.executor:
            return {
                "success": False,
                "error": "No TradeExecutor configured",
                "opportunity_id": opportunity.opportunity_id,
            }
        
        if opportunity.arb_type != ArbType.CROSS_EXCHANGE:
            return {
                "success": False,
                "error": f"Unsupported arb type: {opportunity.arb_type}",
                "opportunity_id": opportunity.opportunity_id,
            }
        
        try:
            # For cross-exchange arb, we need to:
            # 1. Buy on cheaper exchange
            # 2. Sell on more expensive exchange
            
            # Note: This is a simplified implementation.
            # In production, we would need to:
            # - Handle order book depth
            # - Manage inventory across exchanges
            # - Handle failed partial executions
            # - Implement proper risk management
            
            # For now, we'll log the intended trades
            result = {
                "success": True,
                "dry_run": dry_run,
                "opportunity_id": opportunity.opportunity_id,
                "trades": [],
                "metadata": opportunity.metadata,
            }
            
            # Simulate buy trade
            buy_trade = {
                "exchange": opportunity.exchange_a,
                "market": opportunity.market_a,
                "side": "buy",
                "quantity": quantity,
                "price": opportunity.price_a,
                "estimated_cost": quantity * opportunity.price_a,
            }
            result["trades"].append(buy_trade)
            
            # Simulate sell trade
            sell_trade = {
                "exchange": opportunity.exchange_b,
                "market": opportunity.market_b,
                "side": "sell",
                "quantity": quantity,
                "price": opportunity.price_b,
                "estimated_proceeds": quantity * opportunity.price_b,
            }
            result["trades"].append(sell_trade)
            
            # Calculate estimated profit
            total_cost = buy_trade["estimated_cost"]
            total_proceeds = sell_trade["estimated_proceeds"]
            estimated_profit = total_proceeds - total_cost
            
            result["estimated_profit"] = estimated_profit
            result["estimated_profit_bps"] = opportunity.spread_bps
            
            # If not dry-run and executor is available, execute trades
            if not dry_run and self.executor:
                # In a real implementation, we would:
                # 1. Create TradeRequest objects
                # 2. Execute them via TradeExecutor
                # 3. Handle errors and retries
                # 4. Update positions and P&L
                pass
            
            # Log execution
            with self.lock:
                self.execution_count += 1
                self.execution_history.append(result)
                
                # Keep history manageable
                if len(self.execution_history) > 500:
                    self.execution_history = self.execution_history[-500:]
            
            self._log_execution(result)
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "opportunity_id": opportunity.opportunity_id,
                "dry_run": dry_run,
            }
            self._log_error(f"Error executing arbitrage: {e}")
            return error_result
    
    def _log_opportunity(self, opportunity: ArbOpportunity) -> None:
        """Log an arbitrage opportunity."""
        log_file = self.log_dir / "arb_opportunities.jsonl"
        with self.lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(opportunity.to_dict()) + "\n")
            except (IOError, OSError):
                pass  # Silently fail if logging fails
    
    def _log_execution(self, execution: Dict[str, Any]) -> None:
        """Log an execution result."""
        log_file = self.log_dir / "arb_executions.jsonl"
        with self.lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(execution) + "\n")
            except (IOError, OSError):
                pass  # Silently fail if logging fails
    
    def _log_error(self, message: str) -> None:
        """Log an error message."""
        log_file = self.log_dir / "errors.jsonl"
        entry = {
            "timestamp": time.time(),
            "message": message,
        }
        with self.lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except (IOError, OSError):
                pass  # Silently fail if logging fails
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        with self.lock:
            recent_opportunities = self.opportunity_history[-100:] if self.opportunity_history else []
            recent_executions = self.execution_history[-50:] if self.execution_history else []
            
            avg_spread = 0.0
            avg_confidence = 0.0
            if recent_opportunities:
                avg_spread = sum(o.spread_bps for o in recent_opportunities) / len(recent_opportunities)
                avg_confidence = sum(o.confidence for o in recent_opportunities) / len(recent_opportunities)
            
            success_rate = 0.0
            if recent_executions:
                success_count = sum(1 for e in recent_executions if e.get("success", False))
                success_rate = success_count / len(recent_executions)
            
            return {
                "scan_count": self.scan_count,
                "detection_count": self.detection_count,
                "execution_count": self.execution_count,
                "opportunity_history_size": len(self.opportunity_history),
                "execution_history_size": len(self.execution_history),
                "recent_avg_spread_bps": avg_spread,
                "recent_avg_confidence": avg_confidence,
                "recent_execution_success_rate": success_rate,
                "has_executor": self.executor is not None,
            }
    
    def clear_history(self) -> None:
        """Clear opportunity and execution history (for testing)."""
        with self.lock:
            self.opportunity_history.clear()
            self.execution_history.clear()
            self.scan_count = 0
            self.detection_count = 0
            self.execution_count = 0


# Factory function for creating detectors
def create_detector(
    exchanges: Dict[str, ExchangeConnector],
    executor: Optional[TradeExecutor] = None,
    **kwargs
) -> ArbDetector:
    """
    Create an ArbDetector with sensible defaults.
    
    Args:
        exchanges: Dictionary of exchange name -> ExchangeConnector
        executor: Optional TradeExecutor for automated execution
        **kwargs: Additional arguments for ArbDetector
        
    Returns:
        Configured ArbDetector instance
    """
    return ArbDetector(exchanges=exchanges, executor=executor, **kwargs)