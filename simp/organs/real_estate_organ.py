"""
Real Estate Organ - Property investment and wholesaling
========================================================
Executes real estate transactions based on BullBear signals.

This organ:
1. Receives real estate signals from BullBear
2. Analyzes property investment opportunities
3. Executes real estate transactions (simulated in dry-run mode)
4. Manages property portfolio and cash flow

Transaction types:
- Wholesale: Assign purchase contracts
- Buy-hold: Purchase for rental income
- Fix-and-flip: Purchase, renovate, sell
- Options: Purchase options on properties

For production use, replace mock execution with real MLS access,
title companies, and real estate transaction workflows.
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


class PropertyType(str, Enum):
    """Types of real estate properties."""
    SINGLE_FAMILY = "single_family"
    MULTI_FAMILY = "multi_family"
    COMMERCIAL = "commercial"
    LAND = "land"
    MIXED_USE = "mixed_use"


class TransactionType(str, Enum):
    """Types of real estate transactions."""
    WHOLESALE = "wholesale"      # Assign contract
    BUY_HOLD = "buy_hold"        # Purchase for rental
    FLIP = "flip"                # Purchase, renovate, sell
    OPTION = "option"            # Purchase option
    JOINT_VENTURE = "joint_venture"  # Partnership


class RealEstateOrgan(TradingOrgan):
    """
    Real estate organ for property investment and wholesaling.
    
    Executes real estate transactions (simulated in dry-run mode).
    Analyzes deals, manages property portfolio, tracks cash flow.
    """

    def __init__(
        self,
        organ_id: str = "realestate:001",
        initial_balance: float = 100000.0,
        dry_run: bool = True
    ):
        """
        Initialize real estate organ.
        
        Args:
            organ_id: Unique identifier
            initial_balance: Starting USD balance
            dry_run: If True, simulate execution without real transactions
        """
        super().__init__(organ_id, OrganType.REAL_ESTATE)
        self.balance = initial_balance
        self.dry_run = dry_run
        self.properties: Dict[str, Dict] = {}  # property_id -> property details
        self.open_deals: Dict[str, Dict] = {}  # deal_id -> deal details
        self.is_operational = True
        self.last_execution_time: Optional[str] = None
        self.total_deals = 0
        self.total_investment = 0.0
        
        # Risk limits
        self.max_deal_size = 50000.0  # Max $ per deal
        self.max_monthly_deals = 5
        self.monthly_deal_count = 0
        self.max_portfolio_value = 500000.0
        self.current_portfolio_value = 0.0
        
        # Property analysis parameters
        self.min_cap_rate = 0.06  # Minimum 6% cap rate
        self.min_cash_on_cash = 0.08  # Minimum 8% cash on cash return
        self.max_repair_cost_pct = 0.30  # Max 30% of ARV for repairs
        
        # Market data (simulated)
        self.market_conditions = {
            "avg_cap_rate": 0.065,
            "avg_days_on_market": 45,
            "price_to_rent_ratio": 15,
            "closing_cost_pct": 0.03,  # 3% closing costs
        }
        
        print(f"[RealEstateOrgan] Initialized with balance=${initial_balance:,.2f}, dry_run={dry_run}")

    async def execute(
        self,
        params: Dict[str, Any],
        intent_id: str
    ) -> OrganExecutionResult:
        """
        Execute a real estate transaction.
        
        Parameters expected in params:
        - transaction_type: "wholesale", "buy_hold", "flip", "option"
        - property_type: "single_family", "multi_family", etc.
        - property_id: Unique property identifier
        - address: Property address
        - purchase_price: Purchase price
        - after_repair_value: Estimated value after repairs (ARV)
        - repair_cost: Estimated repair costs
        - rental_income: Monthly rental income (for buy-hold)
        - cash_needed: Total cash required for transaction
        - estimated_profit: Estimated profit
        - holding_period: Expected holding period in months
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
            
            # Analyze the deal
            analysis = await self._analyze_deal(params)
            if not analysis.get("viable", False):
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message=f"Deal not viable: {analysis.get('reason', 'Unknown')}"
                )
            
            # Check risk limits
            if not await self._check_risk_limits(params, analysis):
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
            transaction_type = params.get("transaction_type", "").lower()
            property_type = params.get("property_type", "").lower()
            property_id = params.get("property_id", "")
            address = params.get("address", "")
            purchase_price = float(params.get("purchase_price", 0))
            cash_needed = float(params.get("cash_needed", 0))
            
            # Check balance
            if self.balance < cash_needed:
                return OrganExecutionResult(
                    organ_id=self.organ_id,
                    organ_type=self.organ_type,
                    intent_id=intent_id,
                    status=ExecutionStatus.FAILED,
                    executions=[],
                    total_pnl=0,
                    timestamp=datetime.utcnow().isoformat(),
                    error_message=f"Insufficient balance: ${self.balance:,.2f} < ${cash_needed:,.2f}"
                )
            
            # Update balance
            self.balance -= cash_needed
            
            # Simulate transaction process
            if not self.dry_run:
                await asyncio.sleep(1.0)  # Real transaction takes time
            else:
                await asyncio.sleep(0.1)  # Simulated
            
            # Generate deal ID
            deal_id = f"RE_{uuid.uuid4().hex[:8]}"
            
            # Create deal record
            deal_record = {
                "deal_id": deal_id,
                "transaction_type": transaction_type,
                "property_type": property_type,
                "property_id": property_id,
                "address": address,
                "purchase_price": purchase_price,
                "cash_invested": cash_needed,
                "analysis": analysis,
                "status": "pending",  # pending, active, completed, cancelled
                "start_date": datetime.utcnow().isoformat(),
                "intent_id": intent_id,
                "estimated_profit": analysis.get("estimated_profit", 0),
                "estimated_roi": analysis.get("roi", 0),
            }
            
            # Add property-specific details
            if transaction_type == "buy_hold":
                deal_record["rental_income"] = params.get("rental_income")
                deal_record["holding_period"] = params.get("holding_period", 60)  # 5 years default
            
            elif transaction_type == "flip":
                deal_record["after_repair_value"] = params.get("after_repair_value")
                deal_record["repair_cost"] = params.get("repair_cost")
                deal_record["estimated_holding_months"] = params.get("holding_period", 6)
            
            elif transaction_type == "wholesale":
                deal_record["assignment_fee"] = analysis.get("estimated_profit", 0)
                deal_record["buyer_found"] = False
            
            elif transaction_type == "option":
                deal_record["option_fee"] = cash_needed
                deal_record["option_period"] = params.get("option_period", 6)  # 6 months
            
            # Store deal
            if transaction_type in ["buy_hold", "flip"]:
                # These become properties we own
                self.properties[property_id] = deal_record
            else:
                # These are deals in process
                self.open_deals[deal_id] = deal_record
            
            # Create execution record (for trading organ interface)
            execution = TradeExecution(
                execution_id=deal_id,
                symbol=f"{property_type}:{property_id}",
                side="BUY",  # Always buying property/rights
                quantity=1,  # Always 1 property
                price=purchase_price,
                fee=cash_needed - purchase_price if cash_needed > purchase_price else 0,
                timestamp=datetime.utcnow().isoformat(),
                metadata={
                    "transaction_type": transaction_type,
                    "property_type": property_type,
                    "address": address,
                    "cash_invested": cash_needed,
                    "estimated_profit": analysis.get("estimated_profit", 0),
                    "estimated_roi": analysis.get("roi", 0),
                    "dry_run": self.dry_run,
                    "intent_id": intent_id,
                }
            )
            
            # Update stats
            self.total_deals += 1
            self.monthly_deal_count += 1
            self.total_investment += cash_needed
            self.last_execution_time = datetime.utcnow().isoformat()
            
            # Update portfolio value
            if transaction_type in ["buy_hold", "flip"]:
                self.current_portfolio_value += purchase_price
            
            # Log execution
            action = "SIMULATED" if self.dry_run else "EXECUTED"
            print(f"[RealEstateOrgan] {action} {transaction_type}: {address} for ${purchase_price:,.0f}")
            
            return OrganExecutionResult(
                organ_id=self.organ_id,
                organ_type=self.organ_type,
                intent_id=intent_id,
                status=ExecutionStatus.COMPLETED,
                executions=[execution],
                total_pnl=0,  # P&L calculated when deal completes
                timestamp=datetime.utcnow().isoformat(),
                metadata={
                    "dry_run": self.dry_run,
                    "deal_id": deal_id,
                    "remaining_balance": self.balance,
                    "current_portfolio_value": self.current_portfolio_value,
                    "properties_count": len(self.properties),
                    "open_deals_count": len(self.open_deals),
                }
            )
            
        except Exception as e:
            print(f"[RealEstateOrgan] Execution error: {e}")
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
        """Validate real estate transaction parameters."""
        try:
            # Required fields
            transaction_type = params.get("transaction_type", "").lower()
            property_type = params.get("property_type", "").lower()
            property_id = params.get("property_id", "")
            address = params.get("address", "")
            purchase_price = params.get("purchase_price", 0)
            cash_needed = params.get("cash_needed", 0)
            
            if transaction_type not in [t.value for t in TransactionType]:
                return False
            
            if property_type not in [p.value for p in PropertyType]:
                return False
            
            if not property_id or not address:
                return False
            
            if not isinstance(purchase_price, (int, float)) or purchase_price <= 0:
                return False
            
            if not isinstance(cash_needed, (int, float)) or cash_needed <= 0:
                return False
            
            # Transaction-specific validation
            if transaction_type == "buy_hold":
                rental_income = params.get("rental_income")
                if not isinstance(rental_income, (int, float)) or rental_income <= 0:
                    return False
            
            elif transaction_type == "flip":
                after_repair_value = params.get("after_repair_value")
                repair_cost = params.get("repair_cost")
                if not isinstance(after_repair_value, (int, float)) or after_repair_value <= 0:
                    return False
                if not isinstance(repair_cost, (int, float)) or repair_cost < 0:
                    return False
            
            return True
            
        except Exception as e:
            print(f"[RealEstateOrgan] Validation error: {e}")
            return False

    async def _analyze_deal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze real estate deal for viability."""
        try:
            transaction_type = params.get("transaction_type", "").lower()
            purchase_price = float(params.get("purchase_price", 0))
            
            analysis = {
                "viable": False,
                "reason": "",
                "estimated_profit": 0,
                "roi": 0,
                "cash_on_cash": 0,
                "cap_rate": 0,
            }
            
            if transaction_type == "wholesale":
                # Wholesale: assign contract for fee
                assignment_fee = purchase_price * 0.05  # 5% typical wholesale fee
                cash_needed = purchase_price * 0.01  # 1% earnest money
                
                analysis.update({
                    "viable": assignment_fee > 5000,  # Min $5k fee
                    "reason": "Wholesale deal" if assignment_fee > 5000 else "Fee too small",
                    "estimated_profit": assignment_fee,
                    "roi": assignment_fee / cash_needed if cash_needed > 0 else 0,
                    "cash_needed": cash_needed,
                })
            
            elif transaction_type == "buy_hold":
                # Buy-hold: rental property
                rental_income = float(params.get("rental_income", 0))
                cash_needed = float(params.get("cash_needed", 0))
                
                # Calculate metrics
                annual_rent = rental_income * 12
                cap_rate = annual_rent / purchase_price if purchase_price > 0 else 0
                cash_on_cash = (annual_rent * 0.7) / cash_needed if cash_needed > 0 else 0  # 70% of rent is net
                
                analysis.update({
                    "viable": (cap_rate >= self.min_cap_rate and 
                              cash_on_cash >= self.min_cash_on_cash),
                    "reason": "Rental property" if cap_rate >= self.min_cap_rate else "Low returns",
                    "estimated_profit": annual_rent * 5,  # 5 years of rent
                    "roi": cash_on_cash,
                    "cash_on_cash": cash_on_cash,
                    "cap_rate": cap_rate,
                    "cash_needed": cash_needed,
                })
            
            elif transaction_type == "flip":
                # Fix and flip
                after_repair_value = float(params.get("after_repair_value", 0))
                repair_cost = float(params.get("repair_cost", 0))
                cash_needed = float(params.get("cash_needed", 0))
                
                # Calculate profit
                profit = after_repair_value - purchase_price - repair_cost
                profit_margin = profit / after_repair_value if after_repair_value > 0 else 0
                repair_pct = repair_cost / after_repair_value if after_repair_value > 0 else 0
                
                analysis.update({
                    "viable": (profit > 20000 and  # Min $20k profit
                              profit_margin > 0.15 and  # Min 15% margin
                              repair_pct <= self.max_repair_cost_pct),  # Max repair cost %
                    "reason": "Flip deal" if profit > 20000 else "Insufficient profit",
                    "estimated_profit": profit,
                    "roi": profit / cash_needed if cash_needed > 0 else 0,
                    "profit_margin": profit_margin,
                    "repair_pct": repair_pct,
                    "cash_needed": cash_needed,
                })
            
            elif transaction_type == "option":
                # Purchase option
                option_fee = float(params.get("cash_needed", 0))
                potential_profit = purchase_price * 0.3  # 30% of purchase price potential
                
                analysis.update({
                    "viable": potential_profit > option_fee * 3,  # 3x potential return
                    "reason": "Option deal" if potential_profit > option_fee * 3 else "Low potential",
                    "estimated_profit": potential_profit,
                    "roi": potential_profit / option_fee if option_fee > 0 else 0,
                    "cash_needed": option_fee,
                })
            
            return analysis
            
        except Exception as e:
            print(f"[RealEstateOrgan] Deal analysis error: {e}")
            return {"viable": False, "reason": f"Analysis error: {e}"}

    async def _check_risk_limits(self, params: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Check risk management limits."""
        try:
            transaction_type = params.get("transaction_type", "").lower()
            cash_needed = float(params.get("cash_needed", 0))
            
            # Check max deal size
            if cash_needed > self.max_deal_size:
                print(f"[RealEstateOrgan] Deal size ${cash_needed:,.2f} > max ${self.max_deal_size:,.2f}")
                return False
            
            # Check monthly deal limit
            if self.monthly_deal_count >= self.max_monthly_deals:
                print(f"[RealEstateOrgan] Monthly deal limit {self.max_monthly_deals} reached")
                return False
            
            # Check portfolio value limit
            if transaction_type in ["buy_hold", "flip"]:
                purchase_price = float(params.get("purchase_price", 0))
                if self.current_portfolio_value + purchase_price > self.max_portfolio_value:
                    print(f"[RealEstateOrgan] Would exceed portfolio limit")
                    return False
            
            # Don't invest more than 25% of balance in any single deal
            if cash_needed > self.balance * 0.25:
                print(f"[RealEstateOrgan] Deal exceeds 25% of balance")
                return False
            
            return True
            
        except Exception as e:
            print(f"[RealEstateOrgan] Risk check error: {e}")
            return False

    async def complete_deal(self, deal_id: str, outcome: str, actual_profit: Optional[float] = None) -> Dict[str, Any]:
        """
        Complete a real estate deal.
        
        Args:
            deal_id: ID of the deal to complete
            outcome: "sold", "rented", "assigned", "exercised", "expired", "cancelled"
            actual_profit: Actual profit (if different from estimated)
            
        Returns:
            Completion result
        """
        try:
            # Check if it's a property or open deal
            deal = None
            if deal_id in self.properties:
                deal = self.properties[deal_id]
                is_property = True
            elif deal_id in self.open_deals:
                deal = self.open_deals[deal_id]
                is_property = False
            else:
                return {"success": False, "error": "Deal not found"}
            
            transaction_type = deal.get("transaction_type", "")
            cash_invested = deal.get("cash_invested", 0)
            
            # Calculate profit based on outcome
            if outcome == "sold":  # Flip completed
                if actual_profit is None:
                    actual_profit = deal.get("estimated_profit", 0)
                self.balance += cash_invested + actual_profit
                profit = actual_profit
                result = "SOLD"
                
                # Update portfolio value
                purchase_price = deal.get("purchase_price", 0)
                self.current_portfolio_value -= purchase_price
                
            elif outcome == "rented":  # Buy-hold producing income
                monthly_income = deal.get("rental_income", 0)
                # For simulation, add 6 months of rent as profit
                profit = monthly_income * 6
                self.balance += profit
                result = "RENTED"
                
            elif outcome == "assigned":  # Wholesale assignment
                if actual_profit is None:
                    actual_profit = deal.get("estimated_profit", 0)
                self.balance += cash_invested + actual_profit
                profit = actual_profit
                result = "ASSIGNED"
                
            elif outcome == "exercised":  # Option exercised
                if actual_profit is None:
                    actual_profit = deal.get("estimated_profit", 0)
                self.balance += actual_profit
                profit = actual_profit - cash_invested
                result = "EXERCISED"
                
            elif outcome == "expired":  # Option expired
                profit = -cash_invested  # Lose option fee
                result = "EXPIRED"
                
            elif outcome == "cancelled":  # Deal cancelled
                self.balance += cash_invested  # Refund
                profit = 0
                result = "CANCELLED"
                
            else:
                return {"success": False, "error": f"Invalid outcome: {outcome}"}
            
            # Update deal record
            deal["completion_date"] = datetime.utcnow().isoformat()
            deal["outcome"] = outcome
            deal["actual_profit"] = profit
            deal["status"] = "completed"
            
            # Remove from active records
            if is_property:
                del self.properties[deal_id]
            else:
                del self.open_deals[deal_id]
            
            print(f"[RealEstateOrgan] Deal {deal_id} {result}: ${profit:+.2f}")
            
            return {
                "success": True,
                "deal_id": deal_id,
                "outcome": outcome,
                "cash_invested": cash_invested,
                "profit": profit,
                "remaining_balance": self.balance,
                "current_portfolio_value": self.current_portfolio_value,
                "properties_count": len(self.properties),
                "open_deals_count": len(self.open_deals),
            }
            
        except Exception as e:
            print(f"[RealEstateOrgan] Completion error: {e}")
            return {"success": False, "error": str(e)}

    async def get_properties(self) -> List[Dict[str, Any]]:
        """Get list of owned properties."""
        return list(self.properties.values())

    async def get_open_deals(self) -> List[Dict[str, Any]]:
        """Get list of open deals."""
        return list(self.open_deals.values())

    async def get_status(self) -> Dict[str, Any]:
        """Get organ status."""
        # Calculate estimated monthly income from properties
        monthly_income = 0
        for prop in self.properties.values():
            if prop.get("transaction_type") == "buy_hold":
                monthly_income += prop.get("rental_income", 0)
        
        return {
            "organ_id": self.organ_id,
            "organ_type": self.organ_type.value,
            "balance": self.balance,
            "properties_count": len(self.properties),
            "open_deals_count": len(self.open_deals),
            "current_portfolio_value": self.current_portfolio_value,
            "monthly_income": monthly_income,
            "total_deals": self.total_deals,
            "total_investment": self.total_investment,
            "monthly_deal_count": self.monthly_deal_count,
            "last_execution_time": self.last_execution_time,
            "is_operational": self.is_operational,
            "dry_run": self.dry_run,
            "max_deal_size": self.max_deal_size,
            "max_monthly_deals": self.max_monthly_deals,
            "max_portfolio_value": self.max_portfolio_value,
            "min_cap_rate": self.min_cap_rate,
            "min_cash_on_cash": self.min_cash_on_cash,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def reset_monthly_counts(self):
        """Reset monthly counters."""
        self.monthly_deal_count = 0
        print(f"[RealEstateOrgan] Monthly counters reset")


# Factory function for creating real estate organ
def create_real_estate_organ(
    organ_id: str = "realestate:001",
    initial_balance: float = 100000.0,
    dry_run: bool = True
) -> RealEstateOrgan:
    """Create and initialize a real estate organ."""
    organ = RealEstateOrgan(
        organ_id=organ_id,
        initial_balance=initial_balance,
        dry_run=dry_run
    )
    return organ