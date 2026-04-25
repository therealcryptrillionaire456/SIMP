#!/usr/bin/env python3
"""
Gate 4 Scaled Microscopic Agent - Part 3: Main Agent & Integration
Main entry point with SIMP broker integration and dashboard telemetry
"""

import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

# SIMP imports
from simp.server.broker import SimpBroker
from simp.models.canonical_intent import CanonicalIntent
# FinancialOps import removed as it doesn't exist in the module
from simp.organs.quantumarb.arb_detector import ArbDetector, ArbOpportunity
from simp.organs.quantumarb.exchange_connector import ExchangeConnector, StubExchangeConnector

# Import from previous parts
from agents.gate4_scaled_agent_part1 import (
    TradingStrategy, OrderType, Gate4Config, ScaledPosition, 
    MarketMicrostructure, RiskMetrics, Gate4ScaledAgent
)
from agents.gate4_scaled_agent_part2a import (
    TradeExecution, PositionState, PerformanceMetrics, TradeEngine
)
from gate4_scaled_agent_part2b import (
    OrderReconciliation, RiskExposure, ComplianceRecord, OrderManager
)

logger = logging.getLogger(__name__)


@dataclass
class TelemetryData:
    """Telemetry data for dashboard"""
    timestamp: datetime
    agent_id: str
    status: str
    positions: Dict[str, Dict[str, Any]]
    performance: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    order_stats: Dict[str, Any]
    system_health: Dict[str, Any]
    alerts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Alert:
    """Alert for monitoring"""
    alert_id: str
    timestamp: datetime
    severity: str  # "info", "warning", "error", "critical"
    category: str  # "risk", "performance", "system", "compliance"
    message: str
    symbol: Optional[str] = None
    action_required: bool = False
    acknowledged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class Gate4ScaledMicroscopicAgent:
    """
    Main Gate 4 Scaled Microscopic Agent
    Full production agent with $1-$10 position sizes
    """
    
    def __init__(self, config_path: str = "config/gate4_scaled_microscopic.json"):
        # Initialize base agent
        self.base_agent = Gate4ScaledAgent(config_path)
        self.config = self.base_agent.config
        
        # Initialize components
        self.trade_engine = TradeEngine(self.base_agent)
        self.order_manager = OrderManager(self.trade_engine)
        
        # Telemetry and monitoring
        self.telemetry_history: List[TelemetryData] = []
        self.alerts: List[Alert] = []
        self._telemetry_interval = 30  # seconds
        self._health_check_interval = 60  # seconds
        
        # Trading state
        self.is_running = False
        self.trading_enabled = True
        self.last_heartbeat = datetime.now()
        
        # Background tasks
        self._telemetry_task = None
        self._trading_task = None
        self._health_task = None
        
        # Signal handling
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        logger.info("Gate4ScaledMicroscopicAgent initialized")
    
    async def start(self):
        """Start the agent"""
        logger.info("Starting Gate 4 Scaled Microscopic Agent")
        
        # Connect to SIMP broker
        await self.base_agent.connect_to_broker()
        
        # Initialize ML features
        # Note: This is async but we're not in async context here
        # We'll initialize it when needed instead
        
        # Start order manager
        await self.order_manager.start()
        
        # Start background tasks
        self.is_running = True
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        self._trading_task = asyncio.create_task(self._trading_loop())
        self._health_task = asyncio.create_task(self._health_check_loop())
        
        # Register with broker
        await self._register_with_broker()
        
        logger.info("Gate 4 agent started successfully")
    
    async def stop(self):
        """Stop the agent gracefully"""
        logger.info("Stopping Gate 4 agent")
        
        self.is_running = False
        self.trading_enabled = False
        
        # Stop background tasks
        if self._telemetry_task:
            self._telemetry_task.cancel()
        if self._trading_task:
            self._trading_task.cancel()
        if self._health_task:
            self._health_task.cancel()
        
        # Stop order manager
        await self.order_manager.stop()
        
        # Close all positions
        await self.trade_engine.close_all_positions()
        
        # Send shutdown notification
        await self._send_shutdown_notification()
        
        logger.info("Gate 4 agent stopped")
    
    async def _register_with_broker(self):
        """Register agent with SIMP broker"""
        try:
            if self.base_agent.broker:
                # Create agent registration intent
                intent = CanonicalIntent(
                    intent_type="agent_registration",
                    source_agent="gate4_scaled",
                    target_agent="broker",
                    params={
                        "agent_id": "gate4_scaled",
                        "agent_type": "trading",
                        "capabilities": [
                            "scaled_microscopic_trading",
                            "risk_managed_execution",
                            "compliance_monitoring",
                            "performance_reporting"
                        ],
                        "status": "active",
                        "config": {
                            "mode": self.config.mode,
                            "exchange": self.config.exchange,
                            "position_sizing": self.config.position_sizing,
                            "symbols": self.config.symbols[:5]  # First 5 symbols
                        }
                    }
                )
                await self.base_agent.broker.route_intent(intent)
                logger.info("Registered with SIMP broker")
        except Exception as e:
            logger.error(f"Failed to register with broker: {e}")
    
    async def _telemetry_loop(self):
        """Background telemetry loop"""
        while self.is_running:
            try:
                await asyncio.sleep(self._telemetry_interval)
                await self._collect_telemetry()
                await self._send_telemetry_to_dashboard()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry loop: {e}")
                await asyncio.sleep(5)  # Wait before retry
    
    async def _collect_telemetry(self):
        """Collect telemetry data"""
        try:
            # Get current positions
            positions = self.trade_engine.get_current_positions()
            position_data = {}
            for symbol, position in positions.items():
                position_data[symbol] = {
                    "quantity": float(position.quantity),
                    "avg_entry_price": float(position.avg_entry_price),
                    "current_price": float(position.current_price),
                    "notional_value": float(position.notional_value),
                    "unrealized_pnl": float(position.unrealized_pnl),
                    "unrealized_pnl_percent": float(position.unrealized_pnl_percent),
                    "realized_pnl": float(position.realized_pnl),
                    "duration_minutes": position.duration_minutes
                }
            
            # Get performance summary
            performance = self.trade_engine.get_performance_summary()
            
            # Get order statistics
            order_stats = self.order_manager.get_order_statistics()
            
            # Get risk metrics
            risk_metrics = await self._calculate_risk_metrics()
            
            # Get system health
            system_health = self._get_system_health()
            
            # Get active alerts
            active_alerts = [
                {
                    "alert_id": alert.alert_id,
                    "timestamp": alert.timestamp.isoformat(),
                    "severity": alert.severity,
                    "category": alert.category,
                    "message": alert.message,
                    "symbol": alert.symbol,
                    "action_required": alert.action_required
                }
                for alert in self.alerts[-10:]  # Last 10 alerts
            ]
            
            # Create telemetry record
            telemetry = TelemetryData(
                timestamp=datetime.now(),
                agent_id="gate4_scaled",
                status="active" if self.trading_enabled else "paused",
                positions=position_data,
                performance=performance,
                risk_metrics=risk_metrics,
                order_stats=order_stats,
                system_health=system_health,
                alerts=active_alerts
            )
            
            self.telemetry_history.append(telemetry)
            
            # Keep only last 1000 records
            if len(self.telemetry_history) > 1000:
                self.telemetry_history = self.telemetry_history[-1000:]
            
            logger.debug("Telemetry collected")
            
        except Exception as e:
            logger.error(f"Error collecting telemetry: {e}")
    
    async def _calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive risk metrics"""
        try:
            # Calculate Value at Risk
            var_results = await self.order_manager._calculate_value_at_risk()
            
            # Calculate portfolio VaR
            portfolio_var = np.mean(list(var_results.values())) if var_results else 0
            
            # Calculate concentration risk
            positions = self.trade_engine.get_current_positions()
            if positions:
                position_values = [float(p.notional_value) for p in positions.values()]
                total_value = sum(position_values)
                
                # Herfindahl-Hirschman Index for concentration
                if total_value > 0:
                    hhi = sum((v / total_value) ** 2 for v in position_values) * 10000
                else:
                    hhi = 0
                
                # Largest position concentration
                if position_values:
                    max_position = max(position_values)
                    max_concentration = (max_position / total_value * 100) if total_value > 0 else 0
                else:
                    max_concentration = 0
            else:
                hhi = 0
                max_concentration = 0
                total_value = 0
            
            # Calculate liquidity risk (simplified)
            liquidity_risk = 0.0  # Would require market depth data
            
            # Calculate volatility risk
            volatility_risk = portfolio_var  # Use VaR as proxy
            
            return {
                "portfolio_var_percent": float(portfolio_var),
                "concentration_hhi": float(hhi),
                "max_position_concentration_percent": float(max_concentration),
                "liquidity_risk_score": float(liquidity_risk),
                "volatility_risk_score": float(volatility_risk),
                "total_exposure_usd": float(total_value),
                "position_count": len(positions)
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            # Check circuit breaker state
            circuit_state = self.base_agent._check_circuit_breakers()
            
            # Check memory usage (simplified)
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # Check disk space
            disk = psutil.disk_usage(".")
            disk_free_gb = disk.free / 1024 / 1024 / 1024
            
            # Check network connectivity (simplified)
            network_ok = True
            
            # Check exchange connectivity
            exchange_ok = self.base_agent.exchange is not None
            
            # Check broker connectivity
            broker_ok = self.base_agent.broker is not None
            
            return {
                "circuit_breaker_state": circuit_state,
                "memory_usage_mb": float(memory_mb),
                "disk_free_gb": float(disk_free_gb),
                "network_connectivity": network_ok,
                "exchange_connectivity": exchange_ok,
                "broker_connectivity": broker_ok,
                "trading_enabled": self.trading_enabled,
                "uptime_seconds": (datetime.now() - self.last_heartbeat).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {}
    
    async def _send_telemetry_to_dashboard(self):
        """Send telemetry to SIMP dashboard"""
        try:
            if not self.telemetry_history:
                return
            
            latest = self.telemetry_history[-1]
            
            if self.base_agent.broker:
                intent = CanonicalIntent(
                    intent_type="telemetry_update",
                    source_agent="gate4_scaled",
                    target_agent="dashboard",
                    params={
                        "agent_id": latest.agent_id,
                        "timestamp": latest.timestamp.isoformat(),
                        "status": latest.status,
                        "positions": latest.positions,
                        "performance": latest.performance,
                        "risk_metrics": latest.risk_metrics,
                        "order_stats": latest.order_stats,
                        "system_health": latest.system_health,
                        "alerts": latest.alerts
                    }
                )
                await self.base_agent.broker.route_intent(intent)
                
        except Exception as e:
            logger.error(f"Failed to send telemetry to dashboard: {e}")
    
    async def _trading_loop(self):
        """Main trading loop"""
        logger.info("Starting trading loop")
        
        # Initial delay to allow system to stabilize
        await asyncio.sleep(10)
        
        while self.is_running and self.trading_enabled:
            try:
                # Check if trading should be paused
                if not self._should_trade():
                    await asyncio.sleep(30)
                    continue
                
                # Analyze each symbol
                for symbol in self.config.symbols:
                    if not self.trading_enabled:
                        break
                    
                    try:
                        # Analyze market microstructure
                        microstructure = await self.base_agent.analyze_market_microstructure(symbol)
                        
                        # Generate trading signal
                        signal = await self._generate_trading_signal(symbol, microstructure)
                        
                        if signal and signal["action"] != "hold":
                            # Execute trade
                            trade = await self.order_manager.place_order(
                                symbol=symbol,
                                side=signal["action"],
                                quantity=Decimal(str(signal["quantity"])),
                                order_type=OrderType.MARKET,
                                strategy=signal.get("strategy", TradingStrategy.MEAN_REVERSION)
                            )
                            
                            if trade:
                                logger.info(f"Executed {signal['action']} for {symbol}: {trade.quantity}")
                        
                        # Small delay between symbols
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        await asyncio.sleep(5)
                
                # Wait before next cycle
                cycle_delay = self._get_cycle_delay()
                await asyncio.sleep(cycle_delay)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    def _should_trade(self) -> bool:
        """Check if trading should proceed"""
        # Check circuit breakers
        circuit_state = self.base_agent._check_circuit_breakers()
        if circuit_state != "normal":
            logger.warning(f"Trading paused: circuit breaker in {circuit_state} state")
            return False
        
        # Check market hours (always open for crypto)
        # For traditional markets, would check exchange hours
        
        # Check system health
        health = self._get_system_health()
        if not health.get("exchange_connectivity", False):
            logger.warning("Trading paused: exchange connectivity issue")
            return False
        
        return True
    
    async def _generate_trading_signal(
        self,
        symbol: str,
        microstructure: MarketMicrostructure
    ) -> Optional[Dict[str, Any]]:
        """Generate trading signal based on market analysis"""
        try:
            # Get current position
            positions = self.trade_engine.get_current_positions()
            has_position = symbol in positions
            
            # Analyze market conditions
            signal_strength = 0
            action = "hold"
            quantity = 0
            
            # Mean reversion strategy
            if microstructure.price_deviation < -0.02:  # 2% below mean
                signal_strength += 2
                if not has_position:
                    action = "buy"
            
            elif microstructure.price_deviation > 0.02:  # 2% above mean
                signal_strength += 2
                if has_position:
                    action = "sell"
            
            # Momentum strategy
            if microstructure.momentum_5m > 0.01:  # 1% momentum
                signal_strength += 1
                if not has_position:
                    action = "buy"
            
            elif microstructure.momentum_5m < -0.01:  # -1% momentum
                signal_strength += 1
                if has_position:
                    action = "sell"
            
            # Volatility strategy
            if microstructure.volatility_30m > 0.03:  # High volatility
                # Reduce position size in high volatility
                size_multiplier = 0.5
            else:
                size_multiplier = 1.0
            
            # Liquidity consideration
            if microstructure.liquidity_score < 0.5:  # Low liquidity
                # Avoid trading in illiquid conditions
                signal_strength -= 1
            
            # Generate signal if strong enough
            if signal_strength >= 2 and action != "hold":
                # Calculate position size
                base_size = Decimal("0.001")  # Base size
                adjusted_size = base_size * Decimal(str(size_multiplier))
                
                # Get current price for notional calculation
                ticker = await self.base_agent.exchange.get_ticker(symbol)
                current_price = Decimal(str(ticker.get('last', 0)))
                
                if current_price > Decimal("0"):
                    notional = adjusted_size * current_price
                    
                    # Ensure within $1-$10 range
                    min_notional = Decimal(str(self.config.position_sizing['min_notional']))
                    max_notional = Decimal(str(self.config.position_sizing['max_notional']))
                    
                    if notional < min_notional:
                        adjusted_size = min_notional / current_price
                    elif notional > max_notional:
                        adjusted_size = max_notional / current_price
                
                return {
                    "action": action,
                    "quantity": float(adjusted_size),
                    "symbol": symbol,
                    "signal_strength": signal_strength,
                    "strategy": TradingStrategy.MEAN_REVERSION if abs(microstructure.price_deviation) > 0.02 else TradingStrategy.MOMENTUM,
                    "reason": f"Signal strength: {signal_strength}, Deviation: {microstructure.price_deviation:.3f}, Momentum: {microstructure.momentum_5m:.3f}"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating trading signal for {symbol}: {e}")
            return None
    
    def _get_cycle_delay(self) -> int:
        """Get delay between trading cycles"""
        # Adjust based on market conditions
        positions = self.trade_engine.get_current_positions()
        
        if len(positions) >= self.config.position_sizing['max_concurrent_positions']:
            # Slow down if at position limit
            return 120  # 2 minutes
        
        # Normal delay
        return 60  # 1 minute
    
    async def _health_check_loop(self):
        """Background health check loop"""
        while self.is_running:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_check()
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _perform_health_check(self):
        """Perform comprehensive health check"""
        try:
            # Check exchange connectivity
            exchange_ok = await self._check_exchange_connectivity()
            
            # Check broker connectivity
            broker_ok = await self._check_broker_connectivity()
            
            # Check disk space
            disk_ok = await self._check_disk_space()
            
            # Check memory usage
            memory_ok = await self._check_memory_usage()
            
            # Generate alerts for issues
            if not exchange_ok:
                await self._create_alert(
                    severity="error",
                    category="system",
                    message="Exchange connectivity issue",
                    action_required=True
                )
            
            if not broker_ok:
                await self._create_alert(
                    severity="warning",
                    category="system",
                    message="Broker connectivity issue",
                    action_required=False
                )
            
            if not disk_ok:
                await self._create_alert(
                    severity="error",
                    category="system",
                    message="Low disk space",
                    action_required=True
                )
            
            if not memory_ok:
                await self._create_alert(
                    severity="warning",
                    category="system",
                    message="High memory usage",
                    action_required=False
                )
            
            logger.debug("Health check completed")
            
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
    
    async def _check_exchange_connectivity(self) -> bool:
        """Check exchange connectivity"""
        try:
            # Try to get ticker for first symbol
            if self.config.symbols:
                ticker = await self.base_agent.exchange.get_ticker(self.config.symbols[0])
                return ticker is not None
        except:
            pass
        return False
    
    async def _check_broker_connectivity(self) -> bool:
        """Check broker connectivity"""
        return self.base_agent.broker is not None
    
    async def _check_disk_space(self) -> bool:
        """Check disk space"""
        try:
            import psutil
            disk = psutil.disk_usage(".")
            return disk.percent < 90  # Less than 90% used
        except:
            return True
    
    async def _check_memory_usage(self) -> bool:
        """Check memory usage"""
        try:
            import psutil
            process = psutil.Process()
            memory_percent = process.memory_percent()
            return memory_percent < 80  # Less than 80% of system memory
        except:
            return True
    
    async def _send_heartbeat(self):
        """Send heartbeat to SIMP broker"""
        try:
            if self.base_agent.broker:
                intent = CanonicalIntent(
                    intent_type="heartbeat",
                    source_agent="gate4_scaled",
                    target_agent="broker",
                    params={
                        "agent_id": "gate4_scaled",
                        "timestamp": datetime.now().isoformat(),
                        "status": "active" if self.trading_enabled else "paused",
                        "positions_count": len(self.trade_engine.get_current_positions()),
                        "performance": self.trade_engine.get_performance_summary()
                    }
                )
                await self.base_agent.broker.route_intent(intent)
                
                self.last_heartbeat = datetime.now()
                
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    async def _create_alert(
        self,
        severity: str,
        category: str,
        message: str,
        action_required: bool = False,
        symbol: Optional[str] = None
    ):
        """Create and store alert"""
        alert = Alert(
            alert_id=f"alert_{int(time.time())}_{category}",
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            message=message,
            symbol=symbol,
            action_required=action_required
        )
        
        self.alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        # Send alert to broker
        await self._send_alert_to_broker(alert)
        
        logger.info(f"Alert created: {severity} - {message}")
    
    async def _send_alert_to_broker(self, alert: Alert):
        """Send alert to SIMP broker"""
        try:
            if self.base_agent.broker:
                intent = CanonicalIntent(
                    intent_type="alert",
                    source_agent="gate4_scaled",
                    target_agent="auto",
                    params={
                        "alert_id": alert.alert_id,
                        "timestamp": alert.timestamp.isoformat(),
                        "severity": alert.severity,
                        "category": alert.category,
                        "message": alert.message,
                        "symbol": alert.symbol,
                        "action_required": alert.action_required
                    }
                )
                await self.base_agent.broker.route_intent(intent)
        except Exception as e:
            logger.error(f"Failed to send alert to broker: {e}")
    
    async def _send_shutdown_notification(self):
        """Send shutdown notification to SIMP broker"""
        try:
            if self.base_agent.broker:
                intent = CanonicalIntent(
                    intent_type="agent_shutdown",
                    source_agent="gate4_scaled",
                    target_agent="broker",
                    params={
                        "agent_id": "gate4_scaled",
                        "timestamp": datetime.now().isoformat(),
                        "reason": "normal_shutdown",
                        "final_stats": {
                            "total_trades": len(self.trade_engine.trade_history),
                            "current_positions": len(self.trade_engine.get_current_positions()),
                            "performance": self.trade_engine.get_performance_summary()
                        }
                    }
                )
                await self.base_agent.broker.route_intent(intent)
        except Exception as e:
            logger.error(f"Failed to send shutdown notification: {e}")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received shutdown signal {signum}")
        asyncio.create_task(self.stop())
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "agent_id": "gate4_scaled",
            "status": "active" if self.trading_enabled else "paused",
            "running": self.is_running,
            "config_mode": self.config.mode,
            "exchange": self.config.exchange,
            "symbols_count": len(self.config.symbols),
            "positions_count": len(self.trade_engine.get_current_positions()),
            "total_trades": len(self.trade_engine.trade_history),
            "alerts_count": len(self.alerts),
            "last_heartbeat": self.last_heartbeat.isoformat()
        }


async def main():
    """Main entry point for Gate 4 agent"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/gate4_agent.log'),
            logging.StreamHandler()
        ]
    )
    
    logger.info("=" * 60)
    logger.info("Gate 4 Scaled Microscopic Agent Starting")
    logger.info("=" * 60)
    
    # Create agent
    agent = Gate4ScaledMicroscopicAgent()
    
    try:
        # Start agent
        await agent.start()
        
        # Keep running until stopped
        while agent.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Agent error: {e}")
    finally:
        # Stop agent gracefully
        await agent.stop()
    
    logger.info("=" * 60)
    logger.info("Gate 4 Scaled Microscopic Agent Stopped")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())