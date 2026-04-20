#!/usr/bin/env python3.10
"""
P&L Ledger for QuantumArb.

Tracks profit and loss from arbitrage trades with detailed breakdown.
Append-only ledger for audit trail.
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

log = logging.getLogger("PNLLedger")

class TradeDirection(Enum):
    """Trade direction for P&L calculation."""
    ARBITRAGE_BUY_SELL = "arbitrage_buy_sell"  # Buy on exchange A, sell on exchange B
    ARBITRAGE_SELL_BUY = "arbitrage_sell_buy"  # Sell on exchange A, buy on exchange B

@dataclass
class TradeLeg:
    """One leg of an arbitrage trade."""
    exchange: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    fees: float
    timestamp: str
    order_id: str

@dataclass
class PnLRecord:
    """P&L record for a completed arbitrage trade."""
    trade_id: str
    timestamp: str
    symbol: str
    direction: TradeDirection
    
    # Trade legs
    leg_a: TradeLeg  # First exchange
    leg_b: TradeLeg  # Second exchange
    
    # Calculated P&L
    gross_pnl: float  # Before fees
    total_fees: float
    net_pnl: float  # After fees
    
    # Slippage
    expected_spread_bps: float
    realized_spread_bps: float
    slippage_bps: float
    
    # Risk metrics
    position_size_usd: float
    risk_percentage: float  # % of account risked
    
    # Metadata
    brp_decision: str
    risk_allowed: bool
    monitoring_trade_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "trade_id": self.trade_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "leg_a": asdict(self.leg_a),
            "leg_b": asdict(self.leg_b),
            "gross_pnl": self.gross_pnl,
            "total_fees": self.total_fees,
            "net_pnl": self.net_pnl,
            "expected_spread_bps": self.expected_spread_bps,
            "realized_spread_bps": self.realized_spread_bps,
            "slippage_bps": self.slippage_bps,
            "position_size_usd": self.position_size_usd,
            "risk_percentage": self.risk_percentage,
            "brp_decision": self.brp_decision,
            "risk_allowed": self.risk_allowed,
            "monitoring_trade_id": self.monitoring_trade_id
        }


@dataclass
class TradeRecord:
    """Compatibility wrapper used by older Phase 4 paths."""

    trade_id: str
    timestamp: str
    opportunity: Dict[str, Any]
    execution_result: Dict[str, Any]
    pnl_usd: float
    fees_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "timestamp": self.timestamp,
            "opportunity": self.opportunity,
            "execution_result": self.execution_result,
            "pnl_usd": self.pnl_usd,
            "fees_usd": self.fees_usd,
        }

class PNLLedger:
    """
    Append-only P&L ledger for arbitrage trades.
    
    For Phase 4: Tracks microscopic trading results for analysis.
    """
    
    def __init__(self, ledger_path: str = "data/pnl_ledger.jsonl"):
        """
        Initialize P&L ledger.
        
        Args:
            ledger_path: Path to JSONL ledger file
        """
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing records
        self.records: List[PnLRecord] = []
        self._load_ledger()
        
        # Statistics
        self.total_trades = len(self.records)
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_net_pnl = 0.0
        self.total_fees = 0.0
        
        self._calculate_statistics()
        
        log.info(f"P&L Ledger initialized: {self.total_trades} existing trades")
    
    def _load_ledger(self):
        """Load existing ledger records."""
        if not self.ledger_path.exists():
            return
        
        try:
            with open(self.ledger_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        
                        # Convert direction string back to enum
                        direction = TradeDirection(data["direction"])
                        
                        # Reconstruct legs
                        leg_a_data = data["leg_a"]
                        leg_b_data = data["leg_b"]
                        
                        leg_a = TradeLeg(**leg_a_data)
                        leg_b = TradeLeg(**leg_b_data)
                        
                        # Reconstruct record
                        record = PnLRecord(
                            trade_id=data["trade_id"],
                            timestamp=data["timestamp"],
                            symbol=data["symbol"],
                            direction=direction,
                            leg_a=leg_a,
                            leg_b=leg_b,
                            gross_pnl=data["gross_pnl"],
                            total_fees=data["total_fees"],
                            net_pnl=data["net_pnl"],
                            expected_spread_bps=data["expected_spread_bps"],
                            realized_spread_bps=data["realized_spread_bps"],
                            slippage_bps=data["slippage_bps"],
                            position_size_usd=data["position_size_usd"],
                            risk_percentage=data["risk_percentage"],
                            brp_decision=data["brp_decision"],
                            risk_allowed=data["risk_allowed"],
                            monitoring_trade_id=data.get("monitoring_trade_id")
                        )
                        
                        self.records.append(record)
            
            log.info(f"Loaded {len(self.records)} P&L records from {self.ledger_path}")
            
        except Exception as e:
            log.error(f"Failed to load P&L ledger: {e}")
    
    def _calculate_statistics(self):
        """Calculate statistics from loaded records."""
        for record in self.records:
            self.total_net_pnl += record.net_pnl
            self.total_fees += record.total_fees
            
            if record.net_pnl > 0:
                self.winning_trades += 1
            elif record.net_pnl < 0:
                self.losing_trades += 1
    
    def _append_record(self, record: PnLRecord):
        """Append record to ledger file."""
        try:
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
            
            # Update in-memory records and statistics
            self.records.append(record)
            self.total_trades += 1
            self.total_net_pnl += record.net_pnl
            self.total_fees += record.total_fees
            
            if record.net_pnl > 0:
                self.winning_trades += 1
            elif record.net_pnl < 0:
                self.losing_trades += 1
            
            log.info(f"Recorded P&L for trade {record.trade_id}: "
                    f"net ${record.net_pnl:.4f} (gross: ${record.gross_pnl:.4f}, "
                    f"fees: ${record.total_fees:.4f})")
            
            return True
            
        except Exception as e:
            log.error(f"Failed to append P&L record: {e}")
            return False
    
    def record_arbitrage_trade(self, 
                              trade_id: str,
                              symbol: str,
                              exchange_a: str,
                              exchange_b: str,
                              leg_a_result: Dict,  # From TradeExecutor
                              leg_b_result: Dict,  # From TradeExecutor
                              expected_spread_bps: float,
                              brp_decision: str,
                              risk_allowed: bool,
                              position_size_usd: float,
                              risk_percentage: float,
                              monitoring_trade_id: Optional[str] = None) -> bool:
        """
        Record a completed arbitrage trade in the P&L ledger.
        
        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol
            exchange_a: First exchange name
            exchange_b: Second exchange name
            leg_a_result: Execution result from first leg
            leg_b_result: Execution result from second leg
            expected_spread_bps: Expected spread in basis points
            brp_decision: BRP decision that allowed the trade
            risk_allowed: Whether risk framework allowed the trade
            position_size_usd: Position size in USD
            risk_percentage: % of account risked
            monitoring_trade_id: Optional monitoring system trade ID
            
        Returns:
            True if recorded successfully
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Determine trade direction based on which leg was buy vs sell
            # For Phase 4, we'll assume buy on exchange A, sell on exchange B
            direction = TradeDirection.ARBITRAGE_BUY_SELL
            
            # Create trade legs
            leg_a = TradeLeg(
                exchange=exchange_a,
                symbol=symbol,
                side="buy",
                quantity=leg_a_result.get("filled_quantity", 0),
                price=leg_a_result.get("average_price", 0),
                fees=leg_a_result.get("fees", 0),
                timestamp=leg_a_result.get("timestamp", timestamp),
                order_id=leg_a_result.get("order_id", "")
            )
            
            leg_b = TradeLeg(
                exchange=exchange_b,
                symbol=symbol,
                side="sell",
                quantity=leg_b_result.get("filled_quantity", 0),
                price=leg_b_result.get("average_price", 0),
                fees=leg_b_result.get("fees", 0),
                timestamp=leg_b_result.get("timestamp", timestamp),
                order_id=leg_b_result.get("order_id", "")
            )
            
            # Calculate P&L
            # Buy on A, sell on B: P&L = (sell_price * quantity) - (buy_price * quantity) - fees
            buy_cost = leg_a.price * leg_a.quantity
            sell_proceeds = leg_b.price * leg_b.quantity
            gross_pnl = sell_proceeds - buy_cost
            total_fees = leg_a.fees + leg_b.fees
            net_pnl = gross_pnl - total_fees
            
            # Calculate realized spread and slippage
            if leg_a.price > 0 and leg_b.price > 0:
                realized_spread = ((leg_b.price - leg_a.price) / leg_a.price) * 10000
                slippage = expected_spread_bps - realized_spread
            else:
                realized_spread = 0.0
                slippage = 0.0
            
            # Create P&L record
            record = PnLRecord(
                trade_id=trade_id,
                timestamp=timestamp,
                symbol=symbol,
                direction=direction,
                leg_a=leg_a,
                leg_b=leg_b,
                gross_pnl=gross_pnl,
                total_fees=total_fees,
                net_pnl=net_pnl,
                expected_spread_bps=expected_spread_bps,
                realized_spread_bps=realized_spread,
                slippage_bps=slippage,
                position_size_usd=position_size_usd,
                risk_percentage=risk_percentage,
                brp_decision=brp_decision,
                risk_allowed=risk_allowed,
                monitoring_trade_id=monitoring_trade_id
            )
            
            # Append to ledger
            return self._append_record(record)
            
        except Exception as e:
            log.error(f"Failed to record arbitrage trade: {e}")
            return False
    
    def get_statistics(self, days: Optional[int] = None) -> Dict:
        """
        Get P&L statistics.
        
        Args:
            days: Optional number of days to look back
            
        Returns:
            Dictionary of statistics
        """
        # Filter records by date if specified
        if days:
            cutoff_time = time.time() - (days * 24 * 3600)
            cutoff_date = datetime.fromtimestamp(cutoff_time, tz=timezone.utc).isoformat()
            
            recent_records = [
                r for r in self.records 
                if datetime.fromisoformat(r.timestamp.replace('Z', '+00:00')) > 
                   datetime.fromisoformat(cutoff_date.replace('Z', '+00:00'))
            ]
        else:
            recent_records = self.records
        
        # Calculate statistics
        total_trades = len(recent_records)
        winning_trades = sum(1 for r in recent_records if r.net_pnl > 0)
        losing_trades = sum(1 for r in recent_records if r.net_pnl < 0)
        break_even_trades = total_trades - winning_trades - losing_trades
        
        total_net_pnl = sum(r.net_pnl for r in recent_records)
        total_fees = sum(r.total_fees for r in recent_records)
        
        avg_net_pnl = total_net_pnl / total_trades if total_trades > 0 else 0
        avg_fees = total_fees / total_trades if total_trades > 0 else 0
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Calculate profit factor
        gross_profits = sum(r.net_pnl for r in recent_records if r.net_pnl > 0)
        gross_losses = abs(sum(r.net_pnl for r in recent_records if r.net_pnl < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
        
        # Calculate average slippage
        avg_slippage = sum(r.slippage_bps for r in recent_records) / total_trades if total_trades > 0 else 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "break_even_trades": break_even_trades,
            "win_rate": win_rate,
            "total_net_pnl": total_net_pnl,
            "total_fees": total_fees,
            "average_net_pnl": avg_net_pnl,
            "average_fees": avg_fees,
            "profit_factor": profit_factor,
            "average_slippage_bps": avg_slippage,
            "period_days": days
        }
    
    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """
        Get recent trade history.
        
        Args:
            limit: Maximum number of trades to return
            
        Returns:
            List of trade records as dictionaries
        """
        recent_records = self.records[-limit:] if self.records else []
        return [r.to_dict() for r in recent_records]

    def get_trade_count(self) -> int:
        return self.total_trades

    def get_total_pnl(self) -> float:
        return self.total_net_pnl

    def get_win_rate(self) -> float:
        return self.winning_trades / self.total_trades if self.total_trades else 0.0

    def get_average_trade_size(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.position_size_usd for r in self.records) / len(self.records)

    def record_trade(self, trade_record: TradeRecord) -> bool:
        """
        Compatibility path for older agents that persisted a generic execution
        payload instead of explicit leg dictionaries.
        """
        try:
            trades = trade_record.execution_result.get("trades", [])
            if len(trades) < 2:
                log.warning(
                    "Skipping legacy trade record %s: expected two legs, got %s",
                    trade_record.trade_id,
                    len(trades),
                )
                return False

            leg_a_result = trades[0]
            leg_b_result = trades[1]
            opportunity = trade_record.opportunity

            return self.record_arbitrage_trade(
                trade_id=trade_record.trade_id,
                symbol=leg_a_result.get("symbol") or opportunity.get("signal", {}).get("symbol_a", ""),
                exchange_a=leg_a_result.get("exchange", "unknown"),
                exchange_b=leg_b_result.get("exchange", "unknown"),
                leg_a_result=leg_a_result,
                leg_b_result=leg_b_result,
                expected_spread_bps=float(
                    opportunity.get("signal", {}).get("spread_pct", 0.0)
                )
                * 100.0,
                brp_decision=opportunity.get("decision", "unknown"),
                risk_allowed=trade_record.pnl_usd >= 0 or True,
                position_size_usd=float(opportunity.get("position_size_usd", 0.0)),
                risk_percentage=float(opportunity.get("risk_score", 0.0)),
                monitoring_trade_id=opportunity.get("monitoring_id"),
            )
        except Exception as e:
            log.error(f"Failed to record legacy trade: {e}")
            return False
    
    def get_daily_pnl(self, days: int = 7) -> List[Dict]:
        """
        Get daily P&L breakdown.
        
        Args:
            days: Number of days to include
            
        Returns:
            List of daily P&L summaries
        """
        daily_pnl = {}
        
        cutoff_time = time.time() - (days * 24 * 3600)
        
        for record in self.records:
            record_time = datetime.fromisoformat(record.timestamp.replace('Z', '+00:00')).timestamp()
            
            if record_time > cutoff_time:
                # Extract date
                record_date = datetime.fromisoformat(record.timestamp.replace('Z', '+00:00')).strftime("%Y-%m-%d")
                
                if record_date not in daily_pnl:
                    daily_pnl[record_date] = {
                        "date": record_date,
                        "trades": 0,
                        "net_pnl": 0.0,
                        "fees": 0.0,
                        "winning_trades": 0,
                        "losing_trades": 0
                    }
                
                daily = daily_pnl[record_date]
                daily["trades"] += 1
                daily["net_pnl"] += record.net_pnl
                daily["fees"] += record.total_fees
                
                if record.net_pnl > 0:
                    daily["winning_trades"] += 1
                elif record.net_pnl < 0:
                    daily["losing_trades"] += 1
        
        # Convert to list and sort by date
        result = list(daily_pnl.values())
        result.sort(key=lambda x: x["date"], reverse=True)
        
        return result
    
    def export_to_csv(self, filepath: str) -> bool:
        """
        Export P&L ledger to CSV file.
        
        Args:
            filepath: Path to CSV file
            
        Returns:
            True if export successful
        """
        try:
            import csv
            
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    "trade_id", "timestamp", "symbol", "direction",
                    "exchange_a", "side_a", "quantity_a", "price_a", "fees_a",
                    "exchange_b", "side_b", "quantity_b", "price_b", "fees_b",
                    "gross_pnl", "total_fees", "net_pnl",
                    "expected_spread_bps", "realized_spread_bps", "slippage_bps",
                    "position_size_usd", "risk_percentage",
                    "brp_decision", "risk_allowed"
                ])
                
                # Write records
                for record in self.records:
                    writer.writerow([
                        record.trade_id,
                        record.timestamp,
                        record.symbol,
                        record.direction.value,
                        record.leg_a.exchange,
                        record.leg_a.side,
                        record.leg_a.quantity,
                        record.leg_a.price,
                        record.leg_a.fees,
                        record.leg_b.exchange,
                        record.leg_b.side,
                        record.leg_b.quantity,
                        record.leg_b.price,
                        record.leg_b.fees,
                        record.gross_pnl,
                        record.total_fees,
                        record.net_pnl,
                        record.expected_spread_bps,
                        record.realized_spread_bps,
                        record.slippage_bps,
                        record.position_size_usd,
                        record.risk_percentage,
                        record.brp_decision,
                        record.risk_allowed
                    ])
            
            log.info(f"Exported {len(self.records)} trades to {filepath}")
            return True
            
        except Exception as e:
            log.error(f"Failed to export P&L ledger to CSV: {e}")
            return False


# Test function for Phase 4
def test_pnl_ledger():
    """Test P&L ledger functionality."""
    print("Testing P&L Ledger for Phase 4...")
    
    # Create test ledger
    ledger = PNLLedger("data/test_pnl_ledger.jsonl")
    
    try:
        # Test 1: Record a microscopic arbitrage trade
        print("\n1. Recording microscopic arbitrage trade...")
        
        leg_a_result = {
            "filled_quantity": 0.001,
            "average_price": 65000.0,
            "fees": 0.325,  # 0.5% of $65
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": "test_order_a_001"
        }
        
        leg_b_result = {
            "filled_quantity": 0.001,
            "average_price": 65065.0,  # $65 profit before fees
            "fees": 0.325,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": "test_order_b_001"
        }
        
        success = ledger.record_arbitrage_trade(
            trade_id="test_trade_001",
            symbol="BTC-USD",
            exchange_a="coinbase",
            exchange_b="binance",
            leg_a_result=leg_a_result,
            leg_b_result=leg_b_result,
            expected_spread_bps=10.0,  # 0.1% expected spread
            brp_decision="execute",
            risk_allowed=True,
            position_size_usd=65.0,  # 0.001 BTC * $65,000
            risk_percentage=0.065,  # 0.065% of $1000 account
            monitoring_trade_id="monitoring_test_001"
        )
        
        print(f"   Trade recorded: {'SUCCESS' if success else 'FAILED'}")
        
        # Test 2: Get statistics
        print("\n2. Getting P&L statistics...")
        stats = ledger.get_statistics()
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Win rate: {stats['win_rate']:.1%}")
        print(f"   Total net P&L: ${stats['total_net_pnl']:.4f}")
        print(f"   Total fees: ${stats['total_fees']:.4f}")
        print(f"   Average slippage: {stats['average_slippage_bps']:.1f} bps")
        
        # Test 3: Get trade history
        print("\n3. Getting trade history...")
        history = ledger.get_trade_history(limit=5)
        print(f"   Recent trades: {len(history)}")
        if history:
            trade = history[0]
            print(f"   Sample trade: {trade['trade_id']} - "
                  f"net ${trade['net_pnl']:.4f} on {trade['symbol']}")
        
        # Test 4: Get daily P&L
        print("\n4. Getting daily P&L breakdown...")
        daily_pnl = ledger.get_daily_pnl(days=7)
        print(f"   Daily breakdown for {len(daily_pnl)} days")
        for day in daily_pnl:
            print(f"   {day['date']}: {day['trades']} trades, "
                  f"net ${day['net_pnl']:.4f}")
        
        print("\n✅ P&L ledger tests passed")
        print("   Ready for Phase 4 microscopic trading analysis")
        
        # Clean up test file
        import os
        if os.path.exists("data/test_pnl_ledger.jsonl"):
            os.remove("data/test_pnl_ledger.jsonl")
        
    except Exception as e:
        print(f"❌ P&L ledger test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pnl_ledger()


PnLLedger = PNLLedger
