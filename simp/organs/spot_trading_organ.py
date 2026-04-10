"""
Spot Trading Organ - Mock Implementation

This organ handles simple spot trading (immediate buy/sell at market prices).
It's a reference implementation showing how to create a KashClaw organ.

For production use, replace the mock execution with real exchange API calls.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import random

from simp.integrations.trading_organ import (
    TradingOrgan,
    OrganType,
    TradeExecution,
    OrganExecutionResult,
    ExecutionStatus
)


class SpotTradingOrgan(TradingOrgan):
    """
    Mock spot trading organ.

    Executes immediate buy/sell orders at market prices.
    In production, this would connect to exchange APIs (Solana, Ethereum, etc.)
    """

    def __init__(
        self,
        organ_id: str = "spot:001",
        initial_balance: float = 10000.0
    ):
        """
        Initialize spot trading organ.

        Args:
            organ_id: Unique identifier
            initial_balance: Starting USD balance for mock trading
        """
        super().__init__(organ_id, OrganType.SPOT_TRADING)
        self.balance = initial_balance
        self.positions: Dict[str, float] = {}  # asset -> quantity
        self.is_operational = True
        self.last_execution_time: Optional[str] = None
        self.total_trades = 0

    async def execute(
        self,
        params: Dict[str, Any],
        intent_id: str
    ) -> OrganExecutionResult:
        """
        Execute a spot trade.

        Parameters:
        - asset_pair: "SOL/USDC", "ETH/USD", etc.
        - side: "BUY" or "SELL"
        - quantity: Amount to trade
        - price: Current market price (for fee calculation)
        - slippage_tolerance: Max acceptable slippage (0.01 = 1%)
        """
        try:
            # Validate
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

            # Extract parameters
            asset_pair = params.get("asset_pair", "SOL/USDC")
            side = params.get("side", "BUY").upper()
            quantity = float(params.get("quantity", 0))
            price = float(params.get("price", 100))
            slippage_tolerance = float(params.get("slippage_tolerance", 0.01))

            # Simulate execution
            await asyncio.sleep(0.1)  # Simulate API call

            # Calculate slippage (random for demo)
            actual_slippage = random.uniform(0, slippage_tolerance)
            execution_price = price * (1 + actual_slippage)

            # Calculate amounts
            if side == "BUY":
                total_cost = quantity * execution_price
                fee = total_cost * 0.001  # 0.1% fee
                if self.balance < total_cost + fee:
                    return OrganExecutionResult(
                        organ_id=self.organ_id,
                        organ_type=self.organ_type,
                        intent_id=intent_id,
                        status=ExecutionStatus.FAILED,
                        executions=[],
                        total_pnl=0,
                        timestamp=datetime.utcnow().isoformat(),
                        error_message="Insufficient balance"
                    )

                # Execute buy
                self.balance -= (total_cost + fee)
                asset = asset_pair.split("/")[0]
                self.positions[asset] = self.positions.get(asset, 0) + quantity

            else:  # SELL
                asset = asset_pair.split("/")[0]
                if asset not in self.positions or self.positions[asset] < quantity:
                    return OrganExecutionResult(
                        organ_id=self.organ_id,
                        organ_type=self.organ_type,
                        intent_id=intent_id,
                        status=ExecutionStatus.FAILED,
                        executions=[],
                        total_pnl=0,
                        timestamp=datetime.utcnow().isoformat(),
                        error_message="Insufficient position"
                    )

                # Execute sell
                proceeds = quantity * execution_price
                fee = proceeds * 0.001  # 0.1% fee
                self.balance += (proceeds - fee)
                self.positions[asset] -= quantity

            # Create execution record
            trade_id = f"trade:{uuid.uuid4().hex[:8]}"
            execution = TradeExecution(
                trade_id=trade_id,
                organ_type=self.organ_type,
                asset_pair=asset_pair,
                side=side,
                quantity=quantity,
                price=execution_price,
                execution_time=datetime.utcnow().isoformat(),
                status=ExecutionStatus.COMPLETED,
                fee=fee if side == "BUY" else fee,
                slippage=actual_slippage * 100,  # Convert to percentage
                profit_loss=None,
                metadata={
                    "requested_price": price,
                    "execution_price": execution_price,
                    "remaining_balance": self.balance
                }
            )

            # Record execution
            await self.add_execution(execution)
            self.last_execution_time = datetime.utcnow().isoformat()
            self.total_trades += 1

            # Return result
            result = OrganExecutionResult(
                organ_id=self.organ_id,
                organ_type=self.organ_type,
                intent_id=intent_id,
                status=ExecutionStatus.COMPLETED,
                executions=[execution],
                total_pnl=0,  # Would be calculated from position changes
                timestamp=datetime.utcnow().isoformat()
            )

            return result

        except Exception as e:
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
        """Validate trade parameters"""
        required = ["asset_pair", "side", "quantity"]
        for key in required:
            if key not in params:
                return False

        # Validate asset pair format (should have base/quote format)
        asset_pair = str(params.get("asset_pair", ""))
        if "/" not in asset_pair:
            return False
        parts = asset_pair.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return False

        side = str(params.get("side", "")).upper()
        if side not in ["BUY", "SELL"]:
            return False

        try:
            quantity = float(params.get("quantity", 0))
            if quantity <= 0:
                return False
            price = float(params.get("price", 1))
            if price <= 0:
                return False
            
            # Validate slippage_tolerance if provided
            slippage_tolerance = params.get("slippage_tolerance")
            if slippage_tolerance is not None:
                slippage = float(slippage_tolerance)
                if slippage < 0:  # Negative slippage not allowed
                    return False
                # Very high slippage (>100%) might be questionable but allowed
        except (ValueError, TypeError):
            return False

        return True

    async def get_status(self) -> Dict[str, Any]:
        """Get organ status"""
        return {
            "is_operational": self.is_operational,
            "last_execution_time": self.last_execution_time,
            "total_trades": self.total_trades,
            "current_balance": self.balance,
            "positions": self.positions,
            "available_capital": self.balance
        }
