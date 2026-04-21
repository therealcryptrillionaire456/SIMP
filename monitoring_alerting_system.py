#!/usr/bin/env python3.10
"""
Phase 3: Harden Monitoring and Alerting

You already have a dashboard; now treat it as production observability:

Ensure logs capture:
- each intent
- BRP decision  
- order sent
- fill
- P&L impact

Add alerts for:
- BRP blocks or repeated warnings
- order rejects
- deviation between expected and realized slippage beyond threshold

Confirm you can reconstruct any trade from logs + ledger.
"""

import json
import logging
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertType(Enum):
    BRP_BLOCK = "brp_block"
    BRP_WARNING = "brp_warning"
    ORDER_REJECT = "order_reject"
    SLIPPAGE_DEVIATION = "slippage_deviation"
    SYSTEM_ERROR = "system_error"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    EMERGENCY_STOP = "emergency_stop"
    AGENT_OFFLINE = "agent_offline"

@dataclass
class Alert:
    """Alert for monitoring system."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: str
    metadata: Dict[str, any]
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    
    def to_dict(self):
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by
        }

@dataclass
class TradeRecord:
    """Complete trade record for reconstruction."""
    trade_id: str
    intent_id: str
    timestamp: str
    symbol: str
    action: str  # buy, sell, arbitrage
    quantity: float
    price_expected: float
    price_actual: Optional[float] = None
    slippage_percent: Optional[float] = None
    fees: Optional[float] = None
    pnl: Optional[float] = None
    brp_decision: Optional[str] = None
    brp_threat_score: Optional[float] = None
    brp_reason: Optional[str] = None
    order_status: Optional[str] = None  # filled, rejected, partial, cancelled
    exchange: Optional[str] = None
    logs: List[str] = None
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []
    
    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "intent_id": self.intent_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "price_expected": self.price_expected,
            "price_actual": self.price_actual,
            "slippage_percent": self.slippage_percent,
            "fees": self.fees,
            "pnl": self.pnl,
            "brp_decision": self.brp_decision,
            "brp_threat_score": self.brp_threat_score,
            "brp_reason": self.brp_reason,
            "order_status": self.order_status,
            "exchange": self.exchange,
            "logs": self.logs
        }

class MonitoringSystem:
    """Production monitoring and alerting system."""
    
    def __init__(self, alert_thresholds: Optional[Dict] = None):
        self.alerts: List[Alert] = []
        self.trade_records: Dict[str, TradeRecord] = {}
        self.alert_thresholds = alert_thresholds or self._default_thresholds()
        self._lock = threading.Lock()
        self._alert_file = Path("data/monitoring_alerts.jsonl")
        self._trade_file = Path("data/trade_reconstruction.jsonl")
        
        # Ensure directories exist
        self._alert_file.parent.mkdir(parents=True, exist_ok=True)
        self._trade_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing alerts
        self._load_alerts()
        
        logger.info(f"Monitoring system initialized with {len(self.alerts)} existing alerts")
    
    def _default_thresholds(self) -> Dict:
        """Default alert thresholds."""
        return {
            "slippage_warning": 1.0,  # 1% slippage triggers warning
            "slippage_critical": 3.0,  # 3% slippage triggers critical
            "brp_warning_count": 3,    # 3 BRP warnings in 1 hour triggers alert
            "order_reject_rate": 0.1,  # 10% order reject rate triggers alert
            "agent_offline_minutes": 5,  # 5 minutes offline triggers alert
        }
    
    def _load_alerts(self):
        """Load existing alerts from file."""
        if not self._alert_file.exists():
            return
        
        try:
            with open(self._alert_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        alert = Alert(
                            alert_id=data["alert_id"],
                            alert_type=AlertType(data["alert_type"]),
                            severity=AlertSeverity(data["severity"]),
                            message=data["message"],
                            timestamp=data["timestamp"],
                            metadata=data["metadata"],
                            acknowledged=data.get("acknowledged", False),
                            acknowledged_at=data.get("acknowledged_at"),
                            acknowledged_by=data.get("acknowledged_by")
                        )
                        self.alerts.append(alert)
        except Exception as e:
            logger.error(f"Failed to load alerts: {e}")
    
    def _save_alert(self, alert: Alert):
        """Save alert to file."""
        try:
            with open(self._alert_file, 'a') as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
    
    def _save_trade_record(self, trade: TradeRecord):
        """Save trade record to file."""
        try:
            with open(self._trade_file, 'a') as f:
                f.write(json.dumps(trade.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to save trade record: {e}")
    
    def record_intent(self, intent_id: str, intent_data: Dict) -> str:
        """Record an intent and create trade record."""
        trade_id = f"trade_{intent_id}"
        
        with self._lock:
            trade = TradeRecord(
                trade_id=trade_id,
                intent_id=intent_id,
                timestamp=intent_data.get("timestamp", datetime.now().isoformat()),
                symbol=intent_data.get("payload", {}).get("symbol", "unknown"),
                action="arbitrage",  # Default for QuantumArb
                quantity=intent_data.get("payload", {}).get("volume", 0),
                price_expected=intent_data.get("payload", {}).get("price_a", 0),
                logs=[f"Intent received: {intent_id}"]
            )
            
            self.trade_records[trade_id] = trade
            self._save_trade_record(trade)
            
            logger.info(f"Recorded intent: {intent_id} -> {trade_id}")
            
        return trade_id
    
    def record_brp_decision(self, trade_id: str, brp_data: Dict):
        """Record BRP decision for a trade."""
        with self._lock:
            if trade_id not in self.trade_records:
                logger.warning(f"Trade {trade_id} not found for BRP decision")
                return
            
            trade = self.trade_records[trade_id]
            trade.brp_decision = brp_data.get("decision")
            trade.brp_threat_score = brp_data.get("threat_score")
            trade.brp_reason = brp_data.get("reason")
            trade.logs.append(f"BRP decision: {trade.brp_decision} (threat: {trade.brp_threat_score})")
            
            # Check for alerts
            if trade.brp_decision == "block":
                self._create_alert(
                    alert_type=AlertType.BRP_BLOCK,
                    severity=AlertSeverity.CRITICAL,
                    message=f"BRP blocked trade {trade_id} for {trade.symbol}",
                    metadata={
                        "trade_id": trade_id,
                        "symbol": trade.symbol,
                        "brp_decision": trade.brp_decision,
                        "brp_threat_score": trade.brp_threat_score,
                        "brp_reason": trade.brp_reason
                    }
                )
            elif trade.brp_decision == "warn":
                self._create_alert(
                    alert_type=AlertType.BRP_WARNING,
                    severity=AlertSeverity.WARNING,
                    message=f"BRP warned on trade {trade_id} for {trade.symbol}",
                    metadata={
                        "trade_id": trade_id,
                        "symbol": trade.symbol,
                        "brp_decision": trade.brp_decision,
                        "brp_threat_score": trade.brp_threat_score,
                        "brp_reason": trade.brp_reason
                    }
                )
            
            # Update trade record
            self._save_trade_record(trade)
    
    def record_order_execution(self, trade_id: str, order_data: Dict):
        """Record order execution details."""
        with self._lock:
            if trade_id not in self.trade_records:
                logger.warning(f"Trade {trade_id} not found for order execution")
                return
            
            trade = self.trade_records[trade_id]
            trade.price_actual = order_data.get("price_actual")
            trade.order_status = order_data.get("status")
            trade.exchange = order_data.get("exchange")
            trade.fees = order_data.get("fees", 0)
            
            # Calculate slippage
            if trade.price_expected and trade.price_actual:
                slippage = abs(trade.price_actual - trade.price_expected) / trade.price_expected * 100
                trade.slippage_percent = slippage
                
                # Check for slippage alerts
                if slippage >= self.alert_thresholds["slippage_critical"]:
                    self._create_alert(
                        alert_type=AlertType.SLIPPAGE_DEVIATION,
                        severity=AlertSeverity.CRITICAL,
                        message=f"Critical slippage on trade {trade_id}: {slippage:.2f}%",
                        metadata={
                            "trade_id": trade_id,
                            "symbol": trade.symbol,
                            "slippage_percent": slippage,
                            "price_expected": trade.price_expected,
                            "price_actual": trade.price_actual,
                            "threshold": self.alert_thresholds["slippage_critical"]
                        }
                    )
                elif slippage >= self.alert_thresholds["slippage_warning"]:
                    self._create_alert(
                        alert_type=AlertType.SLIPPAGE_DEVIATION,
                        severity=AlertSeverity.WARNING,
                        message=f"High slippage on trade {trade_id}: {slippage:.2f}%",
                        metadata={
                            "trade_id": trade_id,
                            "symbol": trade.symbol,
                            "slippage_percent": slippage,
                            "price_expected": trade.price_expected,
                            "price_actual": trade.price_actual,
                            "threshold": self.alert_thresholds["slippage_warning"]
                        }
                    )
            
            # Check for order rejects
            if trade.order_status == "rejected":
                self._create_alert(
                    alert_type=AlertType.ORDER_REJECT,
                    severity=AlertSeverity.WARNING,
                    message=f"Order rejected for trade {trade_id}",
                    metadata={
                        "trade_id": trade_id,
                        "symbol": trade.symbol,
                        "order_status": trade.order_status,
                        "exchange": trade.exchange
                    }
                )
            
            trade.logs.append(f"Order executed: status={trade.order_status}, price={trade.price_actual}")
            self._save_trade_record(trade)
    
    def record_pnl(self, trade_id: str, pnl_data: Dict):
        """Record P&L for a trade."""
        with self._lock:
            if trade_id not in self.trade_records:
                logger.warning(f"Trade {trade_id} not found for P&L")
                return
            
            trade = self.trade_records[trade_id]
            trade.pnl = pnl_data.get("pnl")
            trade.logs.append(f"P&L recorded: ${trade.pnl:.2f}")
            self._save_trade_record(trade)
    
    def _create_alert(self, alert_type: AlertType, severity: AlertSeverity, 
                     message: str, metadata: Dict) -> Alert:
        """Create and save an alert."""
        alert_id = f"alert_{int(time.time())}_{len(self.alerts)}"
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now().isoformat(),
            metadata=metadata
        )
        
        self.alerts.append(alert)
        self._save_alert(alert)
        
        # Log alert
        logger.warning(f"ALERT [{severity.value}] {alert_type.value}: {message}")
        
        # In production, would send to Slack/Email/PagerDuty here
        self._send_alert_notification(alert)
        
        return alert
    
    def _send_alert_notification(self, alert: Alert):
        """Send alert notification (stub for production integration)."""
        # In production, integrate with:
        # - Slack webhook
        # - Email (SMTP)
        # - PagerDuty
        # - SMS (Twilio)
        # - etc.
        
        # For now, just log
        logger.info(f"Would send alert notification: {alert.message}")
        
        # Example Slack integration (commented out):
        # if alert.severity in [AlertSeverity.WARNING, AlertSeverity.CRITICAL]:
        #     self._send_slack_alert(alert)
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "operator"):
        """Acknowledge an alert."""
        with self._lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_at = datetime.now().isoformat()
                    alert.acknowledged_by = acknowledged_by
                    self._save_alert(alert)
                    logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                    return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all unacknowledged alerts."""
        with self._lock:
            return [alert for alert in self.alerts if not alert.acknowledged]
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        with self._lock:
            return [
                alert for alert in self.alerts
                if datetime.fromisoformat(alert.timestamp.replace('Z', '+00:00')) > cutoff
            ]
    
    def get_trade_reconstruction(self, trade_id: str) -> Optional[TradeRecord]:
        """Get complete trade reconstruction."""
        with self._lock:
            return self.trade_records.get(trade_id)
    
    def search_trades(self, symbol: Optional[str] = None, 
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> List[TradeRecord]:
        """Search for trades by criteria."""
        results = []
        with self._lock:
            for trade in self.trade_records.values():
                # Filter by symbol
                if symbol and trade.symbol != symbol:
                    continue
                
                # Filter by time
                trade_time = datetime.fromisoformat(trade.timestamp.replace('Z', '+00:00'))
                if start_time:
                    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    if trade_time < start:
                        continue
                if end_time:
                    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    if trade_time > end:
                        continue
                
                results.append(trade)
        
        return sorted(results, key=lambda x: x.timestamp, reverse=True)
    
    def get_system_metrics(self) -> Dict:
        """Get system metrics for monitoring."""
        with self._lock:
            now = datetime.utcnow()
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)
            
            # Count alerts by severity
            alerts_by_severity = {
                "critical": 0,
                "warning": 0,
                "info": 0
            }
            
            for alert in self.alerts:
                alert_time = datetime.fromisoformat(alert.timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
                if alert_time > day_ago:
                    if alert.severity == AlertSeverity.CRITICAL:
                        alerts_by_severity["critical"] += 1
                    elif alert.severity == AlertSeverity.WARNING:
                        alerts_by_severity["warning"] += 1
                    else:
                        alerts_by_severity["info"] += 1
            
            # Count trades
            trades_hour = len([t for t in self.trade_records.values() 
                             if datetime.fromisoformat(t.timestamp.replace('Z', '+00:00')).replace(tzinfo=None) > hour_ago])
            trades_day = len([t for t in self.trade_records.values() 
                            if datetime.fromisoformat(t.timestamp.replace('Z', '+00:00')).replace(tzinfo=None) > day_ago])
            
            # Calculate success rate
            successful_trades = len([t for t in self.trade_records.values() 
                                   if t.order_status == "filled"])
            total_trades = len(self.trade_records)
            success_rate = successful_trades / max(total_trades, 1)
            
            # Calculate average slippage
            slippages = [t.slippage_percent for t in self.trade_records.values() 
                        if t.slippage_percent is not None]
            avg_slippage = sum(slippages) / max(len(slippages), 1) if slippages else 0
            
            return {
                "timestamp": now.isoformat(),
                "alerts": {
                    "total": len(self.alerts),
                    "active": len(self.get_active_alerts()),
                    "by_severity": alerts_by_severity
                },
                "trades": {
                    "total": total_trades,
                    "last_hour": trades_hour,
                    "last_day": trades_day,
                    "success_rate": success_rate,
                    "average_slippage_percent": avg_slippage
                },
                "system": {
                    "uptime_hours": 24,  # Would calculate actual uptime
                    "memory_usage_mb": 0,  # Would get from psutil
                    "cpu_percent": 0,  # Would get from psutil
                }
            }

class LogMonitor:
    """Monitor system logs for important events."""
    
    def __init__(self, monitoring_system: MonitoringSystem):
        self.monitoring = monitoring_system
        self.log_files = [
            "stress_test.log",
            "quantumarb_enhanced.log",
            "server.log",
            "monitoring.log"
        ]
        self._last_positions = {}
        
    def monitor_logs(self):
        """Monitor log files for important events."""
        for log_file in self.log_files:
            if os.path.exists(log_file):
                self._monitor_file(log_file)
    
    def _monitor_file(self, filepath: str):
        """Monitor a specific log file."""
        try:
            # Get current position
            current_pos = self._last_positions.get(filepath, 0)
            
            # Read new lines
            with open(filepath, 'r') as f:
                f.seek(current_pos)
                new_lines = f.readlines()
                self._last_positions[filepath] = f.tell()
            
            # Process new lines
            for line in new_lines:
                self._process_log_line(line, filepath)
                
        except Exception as e:
            logger.error(f"Failed to monitor log file {filepath}: {e}")
    
    def _process_log_line(self, line: str, source: str):
        """Process a log line for important events."""
        line_lower = line.lower()
        
        # Check for BRP events
        if "brp" in line_lower and ("block" in line_lower or "warn" in line_lower):
            # Extract trade ID if possible
            trade_id = None
            if "trade_" in line:
                for word in line.split():
                    if word.startswith("trade_"):
                        trade_id = word
                        break
            
            if "block" in line_lower:
                self.monitoring._create_alert(
                    alert_type=AlertType.BRP_BLOCK,
                    severity=AlertSeverity.CRITICAL,
                    message=f"BRP block detected in logs: {line.strip()}",
                    metadata={
                        "log_line": line.strip(),
                        "source": source,
                        "trade_id": trade_id
                    }
                )
            elif "warn" in line_lower:
                self.monitoring._create_alert(
                    alert_type=AlertType.BRP_WARNING,
                    severity=AlertSeverity.WARNING,
                    message=f"BRP warning detected in logs: {line.strip()}",
                    metadata={
                        "log_line": line.strip(),
                        "source": source,
                        "trade_id": trade_id
                    }
                )
        
        # Check for errors
        elif "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
            self.monitoring._create_alert(
                alert_type=AlertType.SYSTEM_ERROR,
                severity=AlertSeverity.WARNING,
                message=f"System error detected: {line.strip()[:100]}...",
                metadata={
                    "log_line": line.strip(),
                    "source": source
                }
            )
        
        # Check for emergency stop
        elif "emergency" in line_lower and "stop" in line_lower:
            self.monitoring._create_alert(
                alert_type=AlertType.EMERGENCY_STOP,
                severity=AlertSeverity.CRITICAL,
                message=f"Emergency stop triggered: {line.strip()}",
                metadata={
                    "log_line": line.strip(),
                    "source": source
                }
            )

def test_monitoring_system():
    """Test the monitoring and alerting system."""
    print("=" * 80)
    print("TESTING MONITORING AND ALERTING SYSTEM")
    print("=" * 80)
    
    # Initialize monitoring system
    monitoring = MonitoringSystem()
    
    # Test 1: Record an intent
    print("\nTest 1: Recording intent...")
    intent_data = {
        "intent_id": "test_intent_001",
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "symbol": "BTC-USD",
            "volume": 0.01,
            "price_a": 50000,
            "price_b": 49950
        }
    }
    trade_id = monitoring.record_intent("test_intent_001", intent_data)
    print(f"  Created trade record: {trade_id}")
    
    # Test 2: Record BRP decision
    print("\nTest 2: Recording BRP decision...")
    brp_data = {
        "decision": "allow",
        "threat_score": 0.1,
        "reason": "Low threat score"
    }
    monitoring.record_brp_decision(trade_id, brp_data)
    print(f"  Recorded BRP decision: {brp_data['decision']}")
    
    # Test 3: Record BRP block (should trigger alert)
    print("\nTest 3: Recording BRP block (should trigger alert)...")
    brp_block_data = {
        "decision": "block",
        "threat_score": 0.8,
        "reason": "High threat score - possible manipulation"
    }
    monitoring.record_brp_decision("trade_test_block", brp_block_data)
    print("  BRP block recorded - alert should be created")
    
    # Test 4: Record order execution with slippage
    print("\nTest 4: Recording order execution...")
    order_data = {
        "price_actual": 50050,  # 0.1% slippage
        "status": "filled",
        "exchange": "coinbase",
        "fees": 2.50
    }
    monitoring.record_order_execution(trade_id, order_data)
    print(f"  Order executed: {order_data['status']} at ${order_data['price_actual']}")
    
    # Test 5: Record P&L
    print("\nTest 5: Recording P&L...")
    pnl_data = {"pnl": 25.50}
    monitoring.record_pnl(trade_id, pnl_data)
    print(f"  P&L recorded: ${pnl_data['pnl']:.2f}")
    
    # Test 6: Get active alerts
    print("\nTest 6: Checking active alerts...")
    active_alerts = monitoring.get_active_alerts()
    print(f"  Active alerts: {len(active_alerts)}")
    for alert in active_alerts[:3]:  # Show first 3
        print(f"    - [{alert.severity.value}] {alert.alert_type.value}: {alert.message}")
    
    # Test 7: Get system metrics
    print("\nTest 7: Getting system metrics...")
    metrics = monitoring.get_system_metrics()
    print(f"  Total alerts: {metrics['alerts']['total']}")
    print(f"  Active alerts: {metrics['alerts']['active']}")
    print(f"  Total trades: {metrics['trades']['total']}")
    print(f"  Success rate: {metrics['trades']['success_rate']:.1%}")
    
    # Test 8: Trade reconstruction
    print("\nTest 8: Trade reconstruction...")
    trade_record = monitoring.get_trade_reconstruction(trade_id)
    if trade_record:
        print(f"  Trade {trade_id} reconstructed:")
        print(f"    Symbol: {trade_record.symbol}")
        print(f"    BRP decision: {trade_record.brp_decision}")
        print(f"    Order status: {trade_record.order_status}")
        print(f"    P&L: ${trade_record.pnl:.2f}")
        print(f"    Logs: {len(trade_record.logs)} entries")
    
    # Test 9: Acknowledge alert
    print("\nTest 9: Acknowledging alert...")
    if active_alerts:
        alert_id = active_alerts[0].alert_id
        success = monitoring.acknowledge_alert(alert_id, "test_operator")
        print(f"  Acknowledged alert {alert_id}: {success}")
    
    print("\n" + "=" * 80)
    print("✅ MONITORING SYSTEM TESTS COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Integrate monitoring with QuantumArb agent")
    print("2. Set up log monitoring for automatic alert detection")
    print("3. Configure alert notifications (Slack/Email)")
    print("4. Add dashboard integration for real-time monitoring")
    print("5. Implement alert escalation policies")

if __name__ == "__main__":
    test_monitoring_system()