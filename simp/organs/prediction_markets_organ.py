"""
Prediction Markets Organ - Sports and political betting execution
=================================================================
Executes bets on sports and political prediction markets.

This organ:
1. Receives prediction market signals from BullBear
2. Executes bets via prediction market APIs (simulated in dry-run mode)
3. Manages stake sizing and risk for binary outcomes
4. Handles sports betting and political prediction markets

For production use, replace mock execution with real APIs:
- Sports: DraftKings, FanDuel, BetMGM
- Politics: Kalshi, Polymarket, PredictIt
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
import random
from enum import Enum

from simp.integrations.trading_organ import (
    TradingOrgan,
    OrganType,
    TradeExecution,
    OrganExecutionResult,
    ExecutionStatus
)


class MarketType(str, Enum):
    """Types of prediction markets."""
    SPORTS = "sports"
    POLITICS = "politics"
    ESPORTS = "esports"
    ENTERTAINMENT = "entertainment"
    FINANCE = "finance"


class BetType(str, Enum):
    """Types of bets."""
    MONEYLINE = "moneyline"  # Win/lose
    SPREAD = "spread"        # Point spread
    TOTAL = "total"          # Over/under
    PROP = "prop"            # Proposition bet
    FUTURE = "future"        # Future event


class PredictionMarketsOrgan(TradingOrgan):
    """
    Prediction markets organ for sports and political betting.
    
    Executes bets on prediction markets (simulated in dry-run mode).
    Handles moneyline, spread, total, and prop bets.
    """

    def __init__(
        self,
        organ_id: str = "prediction:001",
        initial_balance: float = 10000.0,
        dry_run: bool = True
    ):
        """
        Initialize prediction markets organ.
        
        Args:
            organ_id: Unique identifier
            initial_balance: Starting USD balance
            dry_run: If True, simulate execution without real bets
        """
        super().__init__(organ_id, OrganType.PREDICTION_MARKETS)
        self.balance = initial_balance
        self.dry_run = dry_run
        self.open_bets: Dict[str, Dict] = {}  # bet_id -> bet details
        self.is_operational = True
        self.last_execution_time: Optional[str] = None
        self.total_bets = 0
        self.total_stake = 0.0
        
        # Risk limits
        self.max_bet_size = 1000.0  # Max $ per bet
        self.max_daily_bets = 10
        self.daily_bet_count = 0
        self.max_exposure = 5000.0  # Max total exposure
        self.current_exposure = 0.0
        
        # Supported market types
        self.supported_markets = [m.value for m in MarketType]
        
        # Supported bet types
        self.supported_bet_types = [b.value for b in BetType]
        
        print(f"[PredictionMarketsOrgan] Initialized with balance=${initial_balance:,.2f}, dry_run={dry_run}")

    async def execute(
        self,
        params: Dict[str, Any],
        intent_id: str
    ) -> OrganExecutionResult:
        """
        Execute a prediction market bet.
        
        Parameters expected in params:
        - market_type: "sports", "politics", etc.
        - bet_type: "moneyline", "spread", "total", "prop"
        - event_id: Unique event identifier
        - selection: What to bet on (e.g., "Chiefs to win")
        - odds: Decimal odds (e.g., 1.9 for -110)
        - stake: Amount to bet in USD
        - league: For sports (e.g., "nfl", "nba")
        - jurisdiction: For politics (e.g., "us_presidential")
        - event_time: When the event occurs
        """
        try:
            # Validate parameters
            valid = await self.validate_params(params)
            if not valid:
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message="Invalid parameters"
                )
            
            # Check risk limits
            if not await self._check_risk_limits(params):
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message="Risk limit exceeded"
                )
            
            # Extract parameters
            market_type = params.get("market_type", "").lower()
            bet_type = params.get("bet_type", "moneyline").lower()
            event_id = params.get("event_id", "")
            selection = params.get("selection", "")
            odds = float(params.get("odds", 1.9))
            stake = float(params.get("stake", 0))
            
            # Additional parameters
            league = params.get("league", "")
            jurisdiction = params.get("jurisdiction", "")
            event_time = params.get("event_time")
            spread = params.get("spread")
            total = params.get("total")
            
            # Calculate potential payout
            potential_payout = stake * odds
            vig = stake * 0.05  # 5% vigorish (juice)
            net_stake = stake + vig
            
            # Check balance
            if self.balance < net_stake:
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message=f"Insufficient balance: ${self.balance:,.2f} < ${net_stake:,.2f}"
                )
            
            # Update balance and exposure
            self.balance -= net_stake
            self.current_exposure += stake
            
            # Simulate API call delay
            if not self.dry_run:
                await asyncio.sleep(0.3)  # Real API call
            else:
                await asyncio.sleep(0.05)  # Simulated
            
            # Generate bet ID
            bet_id = f"BET_{uuid.uuid4().hex[:8]}"
            
            # Create bet record
            bet_record = {
                "bet_id": bet_id,
                "market_type": market_type,
                "bet_type": bet_type,
                "event_id": event_id,
                "selection": selection,
                "odds": odds,
                "stake": stake,
                "vig": vig,
                "potential_payout": potential_payout,
                "event_time": event_time,
                "placed_time": datetime.utcnow().isoformat(),
                "status": "open",
                "intent_id": intent_id,
                "league": league,
                "jurisdiction": jurisdiction,
                "spread": spread,
                "total": total,
            }
            
            # Store open bet
            self.open_bets[bet_id] = bet_record
            
            # Create execution record (for trading organ interface)
            execution = TradeExecution(
                execution_id=bet_id,
                symbol=f"{market_type}:{event_id}",
                side="BUY",  # Always buying a bet
                quantity=stake,
                price=1.0,  # Not applicable for bets
                fee=vig,
                timestamp=datetime.utcnow().isoformat(),
                metadata={
                    "market_type": market_type,
                    "bet_type": bet_type,
                    "selection": selection,
                    "odds": odds,
                    "potential_payout": potential_payout,
                    "event_time": event_time,
                    "dry_run": self.dry_run,
                    "intent_id": intent_id,
                }
            )
            
            # Update stats
            self.total_bets += 1
            self.daily_bet_count += 1
            self.total_stake += stake
            self.last_execution_time = datetime.utcnow().isoformat()
            
            # Log execution
            action = "SIMULATED" if self.dry_run else "PLACED"
            print(f"[PredictionMarketsOrgan] {action} {market_type} bet: {selection} @ {odds:.2f} for ${stake:.2f}")
            
            return OrganExecutionResult(
                organ_id=self.organ_id,
                organ_type=self.organ_type,
                intent_id=intent_id,
                status=ExecutionStatus.COMPLETED,
                executions=[execution],
                total_pnl=0,  # P&L calculated when bet settles
                timestamp=datetime.utcnow().isoformat(),
                metadata={
                    "dry_run": self.dry_run,
                    "bet_id": bet_id,
                    "remaining_balance": self.balance,
                    "current_exposure": self.current_exposure,
                    "open_bets_count": len(self.open_bets),
                }
            )
            
        except Exception as e:
            print(f"[PredictionMarketsOrgan] Execution error: {e}")
            return OrganExecutionResult(
                organ_id=self.organ_id,
                organ_type=self.organ_type,
                intent_id=intent_id,
                status=ExecutionStatus.FAILED,
                executions=[],
                total_pnl=0,
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate prediction market parameters."""
        try:
            # Required fields
            market_type = params.get("market_type", "").lower()
            bet_type = params.get("bet_type", "").lower()
            selection = params.get("selection", "")
            odds = params.get("odds", 0)
            stake = params.get("stake", 0)
            
            if not market_type or market_type not in self.supported_markets:
                return False
            
            if not bet_type or bet_type not in self.supported_bet_types:
                return False
            
            if not selection:
                return False
            
            if not isinstance(odds, (int, float)) or odds <= 1.0:
                return False  # Must be positive odds (> 1.0)
            
            if not isinstance(stake, (int, float)) or stake <= 0:
                return False
            
            # Check event_id for tracking
            event_id = params.get("event_id", "")
            if not event_id:
                return False
            
            # Market-specific validation
            if market_type == "sports":
                league = params.get("league", "")
                if not league:
                    return False
            
            elif market_type == "politics":
                jurisdiction = params.get("jurisdiction", "")
                if not jurisdiction:
                    return False
            
            return True
            
        except Exception as e:
            print(f"[PredictionMarketsOrgan] Validation error: {e}")
            return False

    async def _check_risk_limits(self, params: Dict[str, Any]) -> bool:
        """Check risk management limits."""
        try:
            stake = float(params.get("stake", 0))
            odds = float(params.get("odds", 1.9))
            market_type = params.get("market_type", "").lower()
            
            # Check max bet size
            if stake > self.max_bet_size:
                print(f"[PredictionMarketsOrgan] Bet size ${stake:,.2f} > max ${self.max_bet_size:,.2f}")
                return False
            
            # Check daily bet limit
            if self.daily_bet_count >= self.max_daily_bets:
                print(f"[PredictionMarketsOrgan] Daily bet limit {self.max_daily_bets} reached")
                return False
            
            # Check total exposure
            potential_exposure = self.current_exposure + stake
            if potential_exposure > self.max_exposure:
                print(f"[PredictionMarketsOrgan] Would exceed max exposure: ${potential_exposure:,.2f} > ${self.max_exposure:,.2f}")
                return False
            
            # Market-specific risk checks
            if market_type == "politics":
                # Politics bets are more correlated - limit exposure
                politics_exposure = sum(
                    bet["stake"] for bet in self.open_bets.values()
                    if bet["market_type"] == "politics"
                )
                if politics_exposure + stake > self.max_exposure * 0.5:  # Max 50% to politics
                    print(f"[PredictionMarketsOrgan] Would exceed politics exposure limit")
                    return False
            
            # Kelly Criterion sanity check (simplified)
            # Don't bet more than 10% of bankroll on any single bet
            if stake > self.balance * 0.1:
                print(f"[PredictionMarketsOrgan] Bet exceeds 10% of bankroll")
                return False
            
            return True
            
        except Exception as e:
            print(f"[PredictionMarketsOrgan] Risk check error: {e}")
            return False

    async def settle_bet(self, bet_id: str, outcome: str, payout: Optional[float] = None) -> Dict[str, Any]:
        """
        Settle a bet (win/lose/push).
        
        Args:
            bet_id: ID of the bet to settle
            outcome: "win", "lose", "push" (refund), "cancelled"
            payout: Actual payout (if different from calculated)
            
        Returns:
            Settlement result
        """
        try:
            if bet_id not in self.open_bets:
                return {"success": False, "error": "Bet not found"}
            
            bet = self.open_bets[bet_id]
            stake = bet["stake"]
            odds = bet["odds"]
            vig = bet["vig"]
            
            # Calculate payout based on outcome
            if outcome == "win":
                if payout is None:
                    payout = stake * odds
                profit = payout - stake
                self.balance += payout
                result = "WON"
                
            elif outcome == "lose":
                payout = 0
                profit = -stake
                result = "LOST"
                
            elif outcome == "push":  # Refund
                payout = stake
                profit = -vig  # Lose only the vig
                self.balance += stake
                result = "PUSH"
                
            elif outcome == "cancelled":  # Full refund
                payout = stake + vig
                profit = 0
                self.balance += stake + vig
                result = "CANCELLED"
                
            else:
                return {"success": False, "error": f"Invalid outcome: {outcome}"}
            
            # Update exposure
            self.current_exposure -= stake
            
            # Update bet record
            bet["settled_time"] = datetime.utcnow().isoformat()
            bet["outcome"] = outcome
            bet["payout"] = payout
            bet["profit"] = profit
            bet["status"] = "settled"
            
            # Remove from open bets
            del self.open_bets[bet_id]
            
            print(f"[PredictionMarketsOrgan] Bet {bet_id} {result}: ${profit:+.2f}")
            
            return {
                "success": True,
                "bet_id": bet_id,
                "outcome": outcome,
                "stake": stake,
                "payout": payout,
                "profit": profit,
                "remaining_balance": self.balance,
                "current_exposure": self.current_exposure,
            }
            
        except Exception as e:
            print(f"[PredictionMarketsOrgan] Settlement error: {e}")
            return {"success": False, "error": str(e)}

    async def get_open_bets(self) -> List[Dict[str, Any]]:
        """Get list of open bets."""
        return list(self.open_bets.values())

    async def get_status(self) -> Dict[str, Any]:
        """Get organ status."""
        # Calculate estimated value of open bets
        estimated_value = 0
        for bet in self.open_bets.values():
            # Simple estimation: assume 50% win probability
            estimated_value += bet["stake"] * bet["odds"] * 0.5
        
        return {
            "organ_id": self.organ_id,
            "organ_type": self.organ_type.value,
            "balance": self.balance,
            "open_bets_count": len(self.open_bets),
            "current_exposure": self.current_exposure,
            "estimated_value": estimated_value,
            "total_bets": self.total_bets,
            "total_stake": self.total_stake,
            "daily_bet_count": self.daily_bet_count,
            "last_execution_time": self.last_execution_time,
            "is_operational": self.is_operational,
            "dry_run": self.dry_run,
            "max_bet_size": self.max_bet_size,
            "max_daily_bets": self.max_daily_bets,
            "max_exposure": self.max_exposure,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def reset_daily_counts(self):
        """Reset daily counters."""
        self.daily_bet_count = 0
        print(f"[PredictionMarketsOrgan] Daily counters reset")


# Factory function for creating prediction markets organ
def create_prediction_markets_organ(
    organ_id: str = "prediction:001",
    initial_balance: float = 10000.0,
    dry_run: bool = True
) -> PredictionMarketsOrgan:
    """Create and initialize a prediction markets organ."""
    organ = PredictionMarketsOrgan(
        organ_id=organ_id,
        initial_balance=initial_balance,
        dry_run=dry_run
    )
    return organ