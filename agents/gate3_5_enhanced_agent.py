#!/usr/bin/env python3
"""
Gate 3.5 Enhanced Multi-Market Agent
Intermediate scaling with $0.50-$5.00 position sizes
Enhanced multi-market capabilities and monitoring
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp
import numpy as np
from scipy import stats

# SIMP imports
from simp.server.broker import SimpBroker
from simp.models.canonical_intent import CanonicalIntent
from simp.compat.financial_ops import validate_financial_op, record_would_spend, execute_approved_payment, build_financial_ops_card

# Trading imports
from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity
from simp.organs.quantumarb.exchange_connector import ExchangeConnector, StubExchangeConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Gate35Config:
    """Gate 3.5 configuration"""
    mode: str
    exchange: str
    symbols: List[str]
    position_sizing: Dict
    execution: Dict
    monitoring: Dict
    enhanced_features: Dict
    risk_management: Dict
    reporting: Dict
    integration: Dict
    advanced: Dict


@dataclass
class EnhancedPosition:
    """Enhanced position tracking with multi-market context"""
    symbol: str
    entry_price: Decimal
    entry_time: datetime
    position_size: Decimal
    notional_value: Decimal
    current_price: Decimal
    pnl_percent: Decimal
    pnl_usd: Decimal
    duration_minutes: float
    market_context: Dict  # Cross-symbol correlations, volatility, etc.
    tags: List[str]  # e.g., ["volatility_adjusted", "multi_market", "time_optimized"]


@dataclass
class MultiMarketAnalysis:
    """Multi-market analysis results"""
    timestamp: datetime
    symbols: List[str]
    correlations: Dict[str, Dict[str, float]]  # symbol -> symbol -> correlation
    volatility_scores: Dict[str, float]  # symbol -> volatility score (0-1)
    liquidity_scores: Dict[str, float]  # symbol -> liquidity score (0-1)
    opportunity_scores: Dict[str, float]  # symbol -> opportunity score (0-1)
    recommended_allocations: Dict[str, float]  # symbol -> allocation percentage


class Gate35EnhancedAgent:
    """Gate 3.5 Enhanced Multi-Market Agent"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.agent_id = f"gate3_5_enhanced_{int(time.time())}"
        
        # Initialize components
        self.exchange = self._init_exchange()
        self.arb_detector = ArbDetector()
        self.broker = None
        self.financial_ops = None
        
        # State tracking
        self.positions: Dict[str, EnhancedPosition] = {}
        self.trade_history: List[Dict] = []
        self.performance_metrics: Dict = {}
        self.multi_market_analysis: Optional[MultiMarketAnalysis] = None
        
        # Risk management
        self.daily_pnl = Decimal('0')
        self.consecutive_losses = 0
        self.hourly_trade_count = 0
        self.last_hour_reset = datetime.now()
        
        # Monitoring
        self.heartbeat_task = None
        self.health_check_task = None
        self.performance_report_task = None
        
        logger.info(f"Gate 3.5 Enhanced Agent initialized: {self.agent_id}")
        logger.info(f"Mode: {self.config.mode}")
        logger.info(f"Symbols: {self.config.symbols}")
        logger.info(f"Position range: ${self.config.position_sizing['min_notional']}-${self.config.position_sizing['max_notional']}")
    
    def _load_config(self) -> Gate35Config:
        """Load configuration from JSON file"""
        with open(self.config_path, 'r') as f:
            config_dict = json.load(f)
        return Gate35Config(**config_dict)
    
    def _init_exchange(self) -> ExchangeConnector:
        """Initialize exchange connector"""
        # For now, use stub connector
        # TODO: Integrate with real Coinbase connector
        return StubExchangeConnector()
    
    async def connect_to_broker(self):
        """Connect to SIMP broker"""
        if self.config.integration.get('simp_broker_enabled', False):
            broker_url = self.config.integration['simp_broker_url']
            try:
                # Initialize broker connection
                self.broker = SimpBroker()
                self.financial_ops = build_financial_ops_card()
                
                # Register with broker
                registration_intent = CanonicalIntent(
                    intent_type="agent_registration",
                    source_agent=self.agent_id,
                    target_agent="broker",
                    payload={
                        "agent_id": self.agent_id,
                        "capabilities": ["enhanced_trading", "multi_market_analysis", "risk_management"],
                        "endpoint": "(file-based)",
                        "status": "active"
                    }
                )
                
                logger.info(f"Connected to SIMP broker at {broker_url}")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to broker: {e}")
                return False
        return True
    
    async def run_multi_market_analysis(self) -> MultiMarketAnalysis:
        """Perform enhanced multi-market analysis"""
        logger.info("Running multi-market analysis...")
        
        # Get market data for all symbols
        market_data = {}
        for symbol in self.config.symbols:
            try:
                # Get recent price history (simulated for now)
                prices = self._simulate_price_history(symbol, periods=100)
                returns = np.diff(prices) / prices[:-1]
                
                market_data[symbol] = {
                    'prices': prices,
                    'returns': returns,
                    'current_price': Decimal(str(prices[-1])),
                    'volatility': np.std(returns) * np.sqrt(252),  # Annualized
                    'volume': np.random.uniform(1000000, 10000000)  # Simulated volume
                }
            except Exception as e:
                logger.error(f"Error getting data for {symbol}: {e}")
                continue
        
        # Calculate correlations
        correlations = {}
        returns_matrix = {}
        
        for sym1 in market_data:
            correlations[sym1] = {}
            if 'returns' in market_data[sym1]:
                returns_matrix[sym1] = market_data[sym1]['returns']
        
        # Compute pairwise correlations
        for sym1 in returns_matrix:
            for sym2 in returns_matrix:
                if len(returns_matrix[sym1]) > 10 and len(returns_matrix[sym2]) > 10:
                    min_len = min(len(returns_matrix[sym1]), len(returns_matrix[sym2]))
                    corr = np.corrcoef(
                        returns_matrix[sym1][:min_len],
                        returns_matrix[sym2][:min_len]
                    )[0, 1]
                    correlations[sym1][sym2] = float(corr)
                else:
                    correlations[sym1][sym2] = 0.0
        
        # Calculate scores
        volatility_scores = {}
        liquidity_scores = {}
        opportunity_scores = {}
        
        for symbol in market_data:
            if symbol in market_data:
                # Volatility score (normalized 0-1, higher = more volatile)
                vol = market_data[symbol].get('volatility', 0.02)
                volatility_scores[symbol] = min(vol / 0.1, 1.0)  # Cap at 1.0
                
                # Liquidity score (normalized 0-1, higher = more liquid)
                volume = market_data[symbol].get('volume', 1000000)
                liquidity_scores[symbol] = min(volume / 5000000, 1.0)  # Cap at 1.0
                
                # Opportunity score (combination of factors)
                # Higher volatility + good liquidity = better opportunity
                opportunity_scores[symbol] = (
                    0.6 * volatility_scores[symbol] +
                    0.4 * liquidity_scores[symbol]
                )
        
        # Calculate recommended allocations
        total_opportunity = sum(opportunity_scores.values())
        recommended_allocations = {}
        
        if total_opportunity > 0:
            for symbol in opportunity_scores:
                recommended_allocations[symbol] = (
                    opportunity_scores[symbol] / total_opportunity * 100
                )
        else:
            # Equal allocation if no opportunity scores
            equal_pct = 100.0 / len(self.config.symbols)
            for symbol in self.config.symbols:
                recommended_allocations[symbol] = equal_pct
        
        analysis = MultiMarketAnalysis(
            timestamp=datetime.now(),
            symbols=self.config.symbols,
            correlations=correlations,
            volatility_scores=volatility_scores,
            liquidity_scores=liquidity_scores,
            opportunity_scores=opportunity_scores,
            recommended_allocations=recommended_allocations
        )
        
        self.multi_market_analysis = analysis
        logger.info(f"Multi-market analysis complete. Top opportunity: {max(opportunity_scores.items(), key=lambda x: x[1])}")
        
        return analysis
    
    def _simulate_price_history(self, symbol: str, periods: int = 100) -> np.ndarray:
        """Simulate price history for testing"""
        # Simple random walk with drift
        np.random.seed(hash(symbol) % 10000)
        base_price = {
            'SOL-USD': 150.0,
            'BTC-USD': 65000.0,
            'ETH-USD': 3500.0,
            'AVAX-USD': 40.0,
            'MATIC-USD': 0.80
        }.get(symbol, 100.0)
        
        returns = np.random.normal(0.0001, 0.02, periods)  # 2% daily volatility
        prices = base_price * np.exp(np.cumsum(returns))
        
        return prices
    
    async def analyze_arbitrage_opportunities(self) -> List[ArbOpportunity]:
        """Analyze arbitrage opportunities across markets"""
        opportunities = []
        
        # Get multi-market analysis if not available
        if self.multi_market_analysis is None:
            await self.run_multi_market_analysis()
        
        # Analyze each symbol
        for symbol in self.config.symbols:
            try:
                # Get current price
                current_price = Decimal(str(np.random.uniform(100, 200)))  # Simulated
                
                # Calculate fair value based on correlations
                fair_value = self._calculate_fair_value(symbol, current_price)
                
                # Check for mispricing
                if fair_value is not None:
                    mispricing_percent = ((current_price - fair_value) / fair_value * 100)
                    
                    if abs(mispricing_percent) > 0.5:  # 0.5% threshold
                        opportunity = ArbOpportunity(
                            symbol=symbol,
                            exchange=self.config.exchange,
                            current_price=current_price,
                            fair_price=fair_value,
                            mispricing_percent=Decimal(str(mispricing_percent)),
                            confidence_score=Decimal('0.7'),
                            timestamp=datetime.now(),
                            metadata={
                                'type': 'multi_market_mispricing',
                                'correlation_based': True,
                                'volatility_adjusted': True
                            }
                        )
                        opportunities.append(opportunity)
                        
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        # Sort by absolute mispricing
        opportunities.sort(key=lambda x: abs(x.mispricing_percent), reverse=True)
        
        logger.info(f"Found {len(opportunities)} arbitrage opportunities")
        return opportunities
    
    def _calculate_fair_value(self, symbol: str, current_price: Decimal) -> Optional[Decimal]:
        """Calculate fair value based on multi-market correlations"""
        if self.multi_market_analysis is None:
            return None
        
        # Get correlations with other symbols
        correlations = self.multi_market_analysis.correlations.get(symbol, {})
        
        if not correlations:
            return None
        
        # Calculate weighted average of correlated symbols
        total_weight = 0
        weighted_sum = Decimal('0')
        
        for other_symbol, corr in correlations.items():
            if other_symbol != symbol and abs(corr) > 0.3:  # Significant correlation
                # Get other symbol's price (simulated)
                other_price = Decimal(str(np.random.uniform(50, 300)))
                weight = abs(corr)
                
                weighted_sum += other_price * Decimal(str(weight))
                total_weight += weight
        
        if total_weight > 0:
            fair_value = weighted_sum / Decimal(str(total_weight))
            return fair_value
        
        return None
    
    async def execute_trade(self, opportunity: ArbOpportunity) -> bool:
        """Execute a trade with enhanced features"""
        # Check risk limits
        if not self._check_risk_limits():
            logger.warning("Risk limits exceeded, skipping trade")
            return False
        
        # Calculate position size with enhanced features
        position_size = self._calculate_enhanced_position_size(opportunity)
        
        if position_size <= Decimal('0'):
            logger.warning("Position size too small or zero")
            return False
        
        # Execute trade
        try:
            logger.info(f"Executing trade: {opportunity.symbol}, size: ${position_size}")
            
            # Simulate trade execution
            trade_result = {
                'symbol': opportunity.symbol,
                'side': 'buy' if opportunity.mispricing_percent < 0 else 'sell',
                'size': float(position_size),
                'price': float(opportunity.current_price),
                'timestamp': datetime.now().isoformat(),
                'opportunity_id': id(opportunity),
                'enhanced_features': self._get_active_enhanced_features()
            }
            
            # Record trade
            self.trade_history.append(trade_result)
            self.hourly_trade_count += 1
            
            # Update position tracking
            self._update_position(opportunity, position_size)
            
            # Send to broker if connected
            if self.broker is not None:
                await self._report_trade_to_broker(trade_result)
            
            logger.info(f"Trade executed successfully: {trade_result}")
            return True
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return False
    
    def _check_risk_limits(self) -> bool:
        """Check all risk management limits"""
        # Check daily loss limit
        daily_loss_limit = Decimal(str(
            self.config.risk_management['circuit_breakers']['max_daily_loss_percent']
        )) / Decimal('100')
        
        if self.daily_pnl < -daily_loss_limit:
            logger.error(f"Daily loss limit exceeded: {self.daily_pnl}")
            return False
        
        # Check consecutive losses
        max_losses = self.config.risk_management['circuit_breakers']['max_consecutive_losses']
        if self.consecutive_losses >= max_losses:
            logger.error(f"Max consecutive losses reached: {self.consecutive_losses}")
            return False
        
        # Check hourly trade limit
        if datetime.now() - self.last_hour_reset > timedelta(hours=1):
            self.hourly_trade_count = 0
            self.last_hour_reset = datetime.now()
        
        max_hourly = self.config.risk_management['circuit_breakers']['max_hourly_trades']
        if self.hourly_trade_count >= max_hourly:
            logger.error(f"Hourly trade limit reached: {self.hourly_trade_count}")
            return False
        
        # Check position limits
        if not self._check_position_limits():
            return False
        
        return True
    
    def _check_position_limits(self) -> bool:
        """Check position exposure limits"""
        total_exposure = sum(
            float(pos.notional_value) 
            for pos in self.positions.values()
        )
        
        max_total_percent = self.config.risk_management['position_limits']['max_total_exposure_percent']
        # For now, just check we're not exceeding concurrent positions
        max_concurrent = self.config.position_sizing['max_concurrent_positions']
        
        if len(self.positions) >= max_concurrent:
            logger.warning(f"Max concurrent positions reached: {len(self.positions)}")
            return False
        
        return True
    
    def _calculate_enhanced_position_size(self, opportunity: ArbOpportunity) -> Decimal:
        """Calculate position size with enhanced features"""
        base_size = Decimal(str(self.config.position_sizing['base_allocation_per_symbol']))
        
        # Apply volatility adjustment
        if self.config.enhanced_features.get('volatility_adjusted_sizing', False):
            if self.multi_market_analysis:
                vol_score = self.multi_market_analysis.volatility_scores.get(opportunity.symbol, 0.5)
                # Reduce size for high volatility
                vol_adjustment = Decimal('1.0') - Decimal(str(vol_score * 0.3))
                base_size *= vol_adjustment
        
        # Apply opportunity score adjustment
        if self.multi_market_analysis:
            opp_score = self.multi_market_analysis.opportunity_scores.get(opportunity.symbol, 0.5)
            opp_adjustment = Decimal('0.7') + Decimal(str(opp_score * 0.6))  # 0.7-1.3x
            base_size *= opp_adjustment
        
        # Apply mispricing adjustment
        mispricing_abs = abs(opportunity.mispricing_percent)
        mispricing_adjustment = Decimal('1.0') + Decimal(str(min(mispricing_abs / 2.0, 1.0)))  # Up to 2x
        base_size *= mispricing_adjustment
        
        # Apply time of day adjustment
        if self.config.enhanced_features.get('time_of_day_optimization', False):
            hour = datetime.now().hour
            # Reduce size during low liquidity hours (0-4 UTC)
            if hour < 4:
                base_size *= Decimal('0.7')
        
        # Ensure within min/max bounds
        min_size = Decimal(str(self.config.position_sizing['min_notional']))
        max_size = Decimal(str(self.config.position_sizing['max_notional']))
        
        base_size = max(min_size, min(max_size, base_size))
        
        return base_size
    
    def _get_active_enhanced_features(self) -> List[str]:
        """Get list of active enhanced features"""
        active_features = []
        for feature, enabled in self.config.enhanced_features.items():
            if enabled:
                active_features.append(feature)
        return active_features
    
    def _update_position(self, opportunity: ArbOpportunity, position_size: Decimal):
        """Update position tracking"""
        position = EnhancedPosition(
            symbol=opportunity.symbol,
            entry_price=opportunity.current_price,
            entry_time=datetime.now(),
            position_size=position_size,
            notional_value=position_size,
            current_price=opportunity.current_price,
            pnl_percent=Decimal('0'),
            pnl_usd=Decimal('0'),
            duration_minutes=0.0,
            market_context={
                'correlations': self.multi_market_analysis.correlations.get(opportunity.symbol, {}) if self.multi_market_analysis else {},
                'volatility_score': self.multi_market_analysis.volatility_scores.get(opportunity.symbol, 0.5) if self.multi_market_analysis else 0.5,
                'opportunity_score': self.multi_market_analysis.opportunity_scores.get(opportunity.symbol, 0.5) if self.multi_market_analysis else 0.5
            },
            tags=self._get_position_tags(opportunity)
        )
        
        self.positions[opportunity.symbol] = position
    
    def _get_position_tags(self, opportunity: ArbOpportunity) -> List[str]:
        """Get tags for position based on enhanced features"""
        tags = []
        
        if self.config.enhanced_features.get('multi_market_arbitrage', False):
            tags.append('multi_market')
        
        if self.config.enhanced_features.get('volatility_adjusted_sizing', False):
            tags.append('volatility_adjusted')
        
        if self.config.enhanced_features.get('time_of_day_optimization', False):
            tags.append('time_optimized')
        
        if opportunity.metadata.get('correlation_based', False):
            tags.append('correlation_based')
        
        return tags
    
    async def _report_trade_to_broker(self, trade_result: Dict):
        """Report trade to SIMP broker"""
        try:
            intent = CanonicalIntent(
                intent_type="trade_execution",
                source_agent=self.agent_id,
                target_agent="broker",
                payload={
                    "trade": trade_result,
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "gate": "3.5"
                }
            )
            # TODO: Send intent to broker
            logger.debug(f"Trade reported to broker: {trade_result['symbol']}")
        except Exception as e:
            logger.error(f"Failed to report trade to broker: {e}")
    
    async def monitor_positions(self):
        """Monitor open positions and update P&L"""
        while True:
            try:
                for symbol, position in list(self.positions.items()):
                    # Update current price (simulated)
                    new_price = Decimal(str(np.random.uniform(
                        float(position.entry_price) * 0.95,
                        float(position.entry_price) * 1.05
                    )))
                    
                    # Calculate P&L
                    pnl_percent = ((new_price - position.entry_price) / position.entry_price * 100)
                    pnl_usd = position.notional_value * pnl_percent / 100
                    
                    # Update position
                    position.current_price = new_price
                    position.pnl_percent = pnl_percent
                    position.pnl_usd = pnl_usd
                    position.duration_minutes = (
                        datetime.now() - position.entry_time
                    ).total_seconds() / 60
                    
                    # Check for exit conditions
                    if self._should_exit_position(position):
                        await self._exit_position(position)
                
                # Update daily P&L
                self.daily_pnl = sum(
                    float(pos.pnl_usd) for pos in self.positions.values()
                )
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(30)
    
    def _should_exit_position(self, position: EnhancedPosition) -> bool:
        """Determine if position should be exited"""
        # Check profit target (2%)
        if position.pnl_percent >= Decimal('2.0'):
            return True
        
        # Check stop loss (-1.5%)
        if position.pnl_percent <= Decimal('-1.5'):
            return True
        
        # Check max duration
        max_duration = self.config.monitoring['alert_thresholds']['max_position_duration_minutes']
        if position.duration_minutes >= max_duration:
            return True
        
        # Check if opportunity has reversed
        # (Simplified - in reality would check current mispricing)
        
        return False
    
    async def _exit_position(self, position: EnhancedPosition):
        """Exit a position"""
        try:
            logger.info(f"Exiting position: {position.symbol}, P&L: {position.pnl_percent:.2f}%")
            
            # Record exit
            exit_trade = {
                'symbol': position.symbol,
                'side': 'sell' if position.pnl_percent > 0 else 'buy',  # Opposite of entry
                'size': float(position.position_size),
                'price': float(position.current_price),
                'pnl_percent': float(position.pnl_percent),
                'pnl_usd': float(position.pnl_usd),
                'duration_minutes': position.duration_minutes,
                'timestamp': datetime.now().isoformat(),
                'exit_reason': self._get_exit_reason(position)
            }
            
            self.trade_history.append(exit_trade)
            
            # Update consecutive losses
            if position.pnl_percent < Decimal('0'):
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0
            
            # Remove position
            if position.symbol in self.positions:
                del self.positions[position.symbol]
            
            # Report to broker
            if self.broker is not None:
                await self._report_trade_to_broker(exit_trade)
            
        except Exception as e:
            logger.error(f"Error exiting position: {e}")
    
    def _get_exit_reason(self, position: EnhancedPosition) -> str:
        """Get reason for position exit"""
        if position.pnl_percent >= Decimal('2.0'):
            return "profit_target"
        elif position.pnl_percent <= Decimal('-1.5'):
            return "stop_loss"
        elif position.duration_minutes >= self.config.monitoring['alert_thresholds']['max_position_duration_minutes']:
            return "max_duration"
        else:
            return "other"
    
    async def start_monitoring_tasks(self):
        """Start all monitoring tasks"""
        # Heartbeat task
        self.heartbeat_task = asyncio.create_task(self._heartbeat_task())
        
        # Health check task
        self.health_check_task = asyncio.create_task(self._health_check_task())
        
        # Performance report task
        self.performance_report_task = asyncio.create_task(self._performance_report_task())
        
        # Position monitoring task
        self.position_monitor_task = asyncio.create_task(self.monitor_positions())
        
        logger.info("Monitoring tasks started")
    
    async def _heartbeat_task(self):
        """Send heartbeat to broker"""
        while True:
            try:
                if self.broker is not None:
                    # Send heartbeat intent
                    heartbeat = {
                        "agent_id": self.agent_id,
                        "timestamp": datetime.now().isoformat(),
                        "status": "active",
                        "positions_count": len(self.positions),
                        "daily_pnl": float(self.daily_pnl)
                    }
                    # TODO: Send to broker
                
                await asyncio.sleep(
                    self.config.monitoring['heartbeat_interval_seconds']
                )
            except Exception as e:
                logger.error(f"Heartbeat task error: {e}")
                await asyncio.sleep(60)
    
    async def _health_check_task(self):
        """Perform health checks"""
        while True:
            try:
                # Check system health
                health_status = {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "positions": len(self.positions),
                    "trade_count": len(self.trade_history),
                    "consecutive_losses": self.consecutive_losses,
                    "hourly_trades": self.hourly_trade_count,
                    "daily_pnl": float(self.daily_pnl),
                    "status": "healthy"
                }
                
                # Check alert thresholds
                self._check_alerts(health_status)
                
                await asyncio.sleep(
                    self.config.monitoring['health_check_interval_seconds']
                )
            except Exception as e:
                logger.error(f"Health check task error: {e}")
                await asyncio.sleep(120)
    
    def _check_alerts(self, health_status: Dict):
        """Check for alert conditions"""
        alerts = []
        
        # Check drawdown
        max_drawdown = self.config.monitoring['alert_thresholds']['max_drawdown_percent']
        if health_status['daily_pnl'] < -max_drawdown:
            alerts.append(f"Daily drawdown exceeded: {health_status['daily_pnl']:.2f}%")
        
        # Check success rate
        if len(self.trade_history) >= 10:
            winning_trades = sum(1 for t in self.trade_history if t.get('pnl_percent', 0) > 0)
            success_rate = winning_trades / len(self.trade_history) * 100
            min_success = self.config.monitoring['alert_thresholds']['min_success_rate_percent']
            
            if success_rate < min_success:
                alerts.append(f"Success rate low: {success_rate:.1f}%")
        
        if alerts:
            logger.warning(f"Alerts triggered: {alerts}")
            # TODO: Send alerts to dashboard/broker
    
    async def _performance_report_task(self):
        """Generate performance reports"""
        while True:
            try:
                report = self._generate_performance_report()
                logger.info(f"Performance report: {report}")
                
                # TODO: Send to dashboard
                
                await asyncio.sleep(
                    self.config.monitoring['performance_report_interval_minutes'] * 60
                )
            except Exception as e:
                logger.error(f"Performance report task error: {e}")
                await asyncio.sleep(300)
    
    def _generate_performance_report(self) -> Dict:
        """Generate performance metrics report"""
        if not self.trade_history:
            return {"message": "No trades yet"}
        
        # Calculate metrics
        winning_trades = [t for t in self.trade_history if t.get('pnl_percent', 0) > 0]
        losing_trades = [t for t in self.trade_history if t.get('pnl_percent', 0) < 0]
        
        total_trades = len(self.trade_history)
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        total_profit = sum(t.get('pnl_usd', 0) for t in winning_trades)
        total_loss = abs(sum(t.get('pnl_usd', 0) for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.get('pnl_percent', 0) for t in self.trade_history]
        if len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "gate": "3.5",
            "total_trades": total_trades,
            "win_rate_percent": win_rate,
            "total_pnl_usd": sum(t.get('pnl_usd', 0) for t in self.trade_history),
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "consecutive_losses": self.consecutive_losses,
            "open_positions": len(self.positions),
            "daily_pnl": float(self.daily_pnl),
            "enhanced_features_active": self._get_active_enhanced_features()
        }
        
        return report
    
    async def run(self):
        """Main agent loop"""
        logger.info("Starting Gate 3.5 Enhanced Agent...")
        
        # Connect to broker
        await self.connect_to_broker()
        
        # Start monitoring tasks
        await self.start_monitoring_tasks()
        
        # Main trading loop
        while True:
            try:
                # Run multi-market analysis
                analysis = await self.run_multi_market_analysis()
                
                # Find arbitrage opportunities
                opportunities = await self.analyze_arbitrage_opportunities()
                
                # Execute trades for top opportunities
                for opportunity in opportunities[:2]:  # Limit to top 2
                    if len(self.positions) < self.config.position_sizing['max_concurrent_positions']:
                        await self.execute_trade(opportunity)
                        await asyncio.sleep(2)  # Small delay between trades
                
                # Wait for next analysis cycle
                await asyncio.sleep(60)  # Analyze every minute
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(30)


async def main():
    """Main entry point"""
    config_path = "config/gate3_5_enhanced_multi_market.json"
    agent = Gate35EnhancedAgent(config_path)
    
    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as e:
        logger.error(f"Agent crashed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())