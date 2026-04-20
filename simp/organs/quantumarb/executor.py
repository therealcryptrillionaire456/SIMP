#!/usr/bin/env python3.10
"""
Trade Executor for QuantumArb.

Supports both single-leg execution and the Phase 4 cross-venue path while
keeping emergency-stop and live-trading gates explicit.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .exchange_connector import (
    ExchangeConnector,
    ExchangeError,
    InsufficientFundsError,
    Order,
    OrderRejectedError,
    OrderSide,
    OrderStatus,
    OrderType,
)

try:
    from monitoring_alerting_system import MonitoringSystem

    MONITORING_AVAILABLE = True
except ImportError:
    MonitoringSystem = Any  # type: ignore[assignment]
    MONITORING_AVAILABLE = False

log = logging.getLogger("TradeExecutor")


@dataclass
class ExecutionResult:
    """Result of a trade or arbitrage execution attempt."""

    success: bool
    order_id: Optional[str] = None
    filled_quantity: float = 0.0
    average_price: float = 0.0
    slippage_bps: float = 0.0
    fees: float = 0.0
    error_message: str = ""
    timestamp: str = ""
    trades: List[Dict[str, Any]] = field(default_factory=list)
    total_pnl_usd: float = 0.0
    total_fees_usd: float = 0.0
    actual_slippage_pct: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error(self) -> str:
        return self.error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "slippage_bps": self.slippage_bps,
            "fees": self.fees,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "trades": self.trades,
            "total_pnl_usd": self.total_pnl_usd,
            "total_fees_usd": self.total_fees_usd,
            "actual_slippage_pct": self.actual_slippage_pct,
            "metadata": self.metadata,
        }


class TradeExecutor:
    """Executes trades with safety checks and explicit live-trading gates."""

    def __init__(
        self,
        exchange_connector: Optional[ExchangeConnector] = None,
        exchange_connectors: Optional[Dict[str, ExchangeConnector]] = None,
        monitoring_system: Optional[Any] = None,
        max_position_size_usd: float = 100.0,
        max_slippage_bps: float = 20.0,
        emergency_stop: bool = False,
        allow_live_trading: bool = False,
        default_exchange_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        if exchange_connector is None and not exchange_connectors:
            raise ValueError("At least one exchange connector is required")

        self.exchange_connectors = dict(exchange_connectors or {})
        if exchange_connector is not None:
            connector_name = default_exchange_name or "default"
            self.exchange_connectors.setdefault(connector_name, exchange_connector)

        self.default_exchange_name = (
            default_exchange_name or next(iter(self.exchange_connectors.keys()))
        )
        self.exchange = self.exchange_connectors[self.default_exchange_name]

        self.monitoring = monitoring_system
        self.max_position_size_usd = max_position_size_usd
        self.max_slippage_bps = max_slippage_bps
        self.emergency_stop = emergency_stop
        self.allow_live_trading = allow_live_trading
        self.max_retries = 1
        self.retry_delay_seconds = 1.0

        if config:
            if (
                "max_position_size_usd" in config
                and max_position_size_usd == 100.0
            ):
                self.max_position_size_usd = config["max_position_size_usd"]
            if "max_slippage_bps" in config and max_slippage_bps == 20.0:
                self.max_slippage_bps = config["max_slippage_bps"]
            self.emergency_stop = config.get("emergency_stop", self.emergency_stop)
            self.allow_live_trading = config.get(
                "allow_live_trading", self.allow_live_trading
            )
            self.max_retries = int(config.get("max_retries", self.max_retries))
            self.retry_delay_seconds = float(
                config.get("retry_delay_seconds", self.retry_delay_seconds)
            )

        self.execution_count = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.total_slippage_bps = 0.0
        self.total_fees = 0.0
        self.active_orders: Dict[str, Order] = {}

        log.info(
            "TradeExecutor initialized (exchanges=%s, max position=$%.2f, max slippage=%.1f bps, live=%s)",
            ",".join(self.exchange_connectors.keys()),
            self.max_position_size_usd,
            self.max_slippage_bps,
            self.allow_live_trading,
        )

    def _get_connector(self, exchange_name: Optional[str] = None) -> Tuple[str, ExchangeConnector]:
        resolved_name = exchange_name or self.default_exchange_name
        if resolved_name not in self.exchange_connectors:
            raise ExchangeError(f"Unknown exchange connector: {resolved_name}")
        return resolved_name, self.exchange_connectors[resolved_name]

    def _check_connector_gate(
        self, connector: ExchangeConnector, exchange_name: str
    ) -> Optional[str]:
        if self.emergency_stop:
            return "Emergency stop active"
        if not getattr(connector, "sandbox", True) and not self.allow_live_trading:
            return (
                f"Live trading disabled for {exchange_name}; "
                "set allow_live_trading=true to enable non-sandbox execution"
            )
        return None

    def check_emergency_stop(self) -> bool:
        return self.emergency_stop

    def validate_position_size(
        self, symbol: str, quantity: float, exchange_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        if quantity <= 0:
            return False, "Quantity must be positive"

        try:
            _, connector = self._get_connector(exchange_name)
            ticker = connector.get_ticker(symbol)
            position_value_usd = quantity * ticker.last

            if position_value_usd > (self.max_position_size_usd + 1e-9):
                return (
                    False,
                    f"Position size ${position_value_usd:.2f} exceeds limit "
                    f"${self.max_position_size_usd:.2f}",
                )

            if quantity < 0.0001:
                return False, f"Quantity {quantity} below minimum trade size"

            return True, "Position size valid"
        except Exception as exc:
            return False, f"Failed to validate position size: {exc}"

    def estimate_execution_costs(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        exchange_name: Optional[str] = None,
    ) -> Tuple[float, float]:
        _, connector = self._get_connector(exchange_name)
        estimated_slippage = connector.estimate_slippage(symbol, side, quantity)
        ticker = connector.get_ticker(symbol)
        order_value = quantity * ticker.last

        fee_rate = 0.0
        try:
            fee_rate = float(connector.get_fees())
        except Exception:
            fee_rate = 0.0

        return estimated_slippage, order_value * fee_rate

    def check_slippage_limit(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        exchange_name: Optional[str] = None,
    ) -> Tuple[bool, str]:
        estimated_slippage, _ = self.estimate_execution_costs(
            symbol=symbol,
            side=side,
            quantity=quantity,
            exchange_name=exchange_name,
        )
        if estimated_slippage > self.max_slippage_bps:
            return (
                False,
                f"Estimated slippage {estimated_slippage:.1f} bps exceeds "
                f"limit {self.max_slippage_bps:.1f} bps",
            )
        return True, f"Estimated slippage {estimated_slippage:.1f} bps within limits"

    def _record_monitoring(
        self,
        trade_id: str,
        order: Order,
        exchange_name: str,
        fees: float,
    ) -> None:
        if not (MONITORING_AVAILABLE and self.monitoring):
            return

        try:
            self.monitoring.record_order_execution(
                trade_id,
                {
                    "price_actual": order.average_price or order.price or 0.0,
                    "status": order.status.value,
                    "exchange": exchange_name,
                    "fees": fees,
                },
            )
        except Exception as exc:
            log.warning("Failed to record execution in monitoring: %s", exc)

    def _order_to_trade(
        self,
        order: Order,
        exchange_name: str,
        fees: float,
        slippage_bps: float,
    ) -> Dict[str, Any]:
        return {
            "exchange": exchange_name,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_id": order.order_id,
            "filled_quantity": order.filled_quantity,
            "average_price": order.average_price or 0.0,
            "fees": fees,
            "slippage_bps": slippage_bps,
            "status": order.status.value,
            "timestamp": order.timestamp,
        }

    def execute_trade(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        trade_id: str = "",
        exchange_name: Optional[str] = None,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        skip_position_check: bool = False,
    ) -> ExecutionResult:
        timestamp = datetime.now(timezone.utc).isoformat()
        self.execution_count += 1

        if not trade_id:
            trade_id = f"trade_{int(time.time())}_{self.execution_count}"

        try:
            resolved_exchange, connector = self._get_connector(exchange_name)
        except Exception as exc:
            self.failed_executions += 1
            return ExecutionResult(
                success=False,
                error_message=str(exc),
                timestamp=timestamp,
            )

        gate_error = self._check_connector_gate(connector, resolved_exchange)
        if gate_error:
            self.failed_executions += 1
            return ExecutionResult(
                success=False,
                error_message=gate_error,
                timestamp=timestamp,
            )

        if not skip_position_check:
            is_valid, error_msg = self.validate_position_size(
                symbol=symbol,
                quantity=quantity,
                exchange_name=resolved_exchange,
            )
            if not is_valid:
                self.failed_executions += 1
                return ExecutionResult(
                    success=False,
                    error_message=error_msg,
                    timestamp=timestamp,
                )

        slippage_ok, slippage_msg = self.check_slippage_limit(
            symbol=symbol,
            side=side,
            quantity=quantity,
            exchange_name=resolved_exchange,
        )
        if not slippage_ok:
            self.failed_executions += 1
            return ExecutionResult(
                success=False,
                error_message=slippage_msg,
                timestamp=timestamp,
            )

        estimated_slippage, estimated_fees = self.estimate_execution_costs(
            symbol=symbol,
            side=side,
            quantity=quantity,
            exchange_name=resolved_exchange,
        )

        attempt = 0
        last_error = ""
        while attempt < self.max_retries:
            attempt += 1
            try:
                order = connector.place_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                )
                if order.status != OrderStatus.FILLED:
                    order = connector.get_order_status(order.order_id)

                if order.status != OrderStatus.FILLED:
                    raise OrderRejectedError(
                        f"Order {order.order_id} not filled: {order.status.value}"
                    )

                market_ticker = connector.get_ticker(symbol)
                expected_price = (
                    market_ticker.ask if side == OrderSide.BUY else market_ticker.bid
                )
                average_price = order.average_price or order.price or expected_price
                if expected_price > 0:
                    actual_slippage_bps = (
                        abs(average_price - expected_price) / expected_price
                    ) * 10000
                else:
                    actual_slippage_bps = estimated_slippage

                fees = estimated_fees
                self.successful_executions += 1
                self.total_slippage_bps += actual_slippage_bps
                self.total_fees += fees
                self.active_orders[order.order_id] = order
                self._record_monitoring(trade_id, order, resolved_exchange, fees)

                trade = self._order_to_trade(
                    order=order,
                    exchange_name=resolved_exchange,
                    fees=fees,
                    slippage_bps=actual_slippage_bps,
                )

                return ExecutionResult(
                    success=True,
                    order_id=order.order_id,
                    filled_quantity=order.filled_quantity,
                    average_price=average_price,
                    slippage_bps=actual_slippage_bps,
                    fees=fees,
                    timestamp=timestamp,
                    trades=[trade],
                    total_fees_usd=fees,
                    actual_slippage_pct=actual_slippage_bps / 100.0,
                    metadata={
                        "exchange": resolved_exchange,
                        "order_type": order_type.value,
                    },
                )
            except (InsufficientFundsError, OrderRejectedError, ExchangeError) as exc:
                last_error = str(exc)
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_delay_seconds)
            except Exception as exc:
                last_error = f"Unexpected error: {exc}"
                break

        self.failed_executions += 1
        return ExecutionResult(
            success=False,
            error_message=last_error or "Execution failed",
            timestamp=timestamp,
            metadata={"exchange": resolved_exchange},
        )

    def execute_investment(
        self,
        exchange_name: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        trade_id: str = "",
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
    ) -> ExecutionResult:
        return self.execute_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            trade_id=trade_id,
            exchange_name=exchange_name,
            order_type=order_type,
            price=price,
        )

    def execute_arbitrage(
        self,
        opportunity: Any,
        execution_plan: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        timestamp = datetime.now(timezone.utc).isoformat()
        opportunity_id = getattr(opportunity, "opportunity_id", "arb_execution")
        signal = getattr(opportunity, "signal", None)

        plan = execution_plan or getattr(opportunity, "execution_plan", None) or {}
        steps = plan.get("steps", [])

        if len(steps) < 2 and signal is None:
            return ExecutionResult(
                success=False,
                error_message="Arbitrage execution requires two execution steps",
                timestamp=timestamp,
            )

        position_size_usd = float(
            getattr(opportunity, "position_size_usd", 0.0) or plan.get("total_position_usd", 0.0)
        )
        if position_size_usd <= 0:
            return ExecutionResult(
                success=False,
                error_message="Arbitrage execution requires a positive USD position size",
                timestamp=timestamp,
            )

        if steps:
            buy_step = steps[0]
            sell_step = steps[1]
            buy_symbol = buy_step["symbol"]
            sell_symbol = sell_step["symbol"]
            buy_exchange = buy_step["venue"]
            sell_exchange = sell_step["venue"]
        else:
            buy_symbol = signal.symbol_a
            sell_symbol = signal.symbol_b
            buy_exchange = signal.venue_a
            sell_exchange = signal.venue_b

        _, buy_connector = self._get_connector(buy_exchange)
        buy_ticker = buy_connector.get_ticker(buy_symbol)
        buy_quantity = round(position_size_usd / max(buy_ticker.ask, 1e-9), 8)

        buy_result = self.execute_trade(
            symbol=buy_symbol,
            side=OrderSide.BUY,
            quantity=buy_quantity,
            trade_id=f"{opportunity_id}:buy",
            exchange_name=buy_exchange,
        )
        if not buy_result.success:
            return ExecutionResult(
                success=False,
                error_message=f"Buy leg failed: {buy_result.error_message}",
                timestamp=timestamp,
                trades=buy_result.trades,
                metadata={"opportunity_id": opportunity_id},
            )

        sell_quantity = buy_result.filled_quantity
        sell_result = self.execute_trade(
            symbol=sell_symbol,
            side=OrderSide.SELL,
            quantity=sell_quantity,
            trade_id=f"{opportunity_id}:sell",
            exchange_name=sell_exchange,
            skip_position_check=True,
        )
        if not sell_result.success:
            return ExecutionResult(
                success=False,
                error_message=f"Sell leg failed after buy fill: {sell_result.error_message}",
                timestamp=timestamp,
                trades=buy_result.trades + sell_result.trades,
                total_fees_usd=buy_result.total_fees_usd + sell_result.total_fees_usd,
                metadata={
                    "opportunity_id": opportunity_id,
                    "residual_exposure": {
                        "exchange": buy_exchange,
                        "symbol": buy_symbol,
                        "quantity": buy_result.filled_quantity,
                    },
                },
            )

        combined_trades = buy_result.trades + sell_result.trades
        buy_cost = buy_result.filled_quantity * buy_result.average_price
        sell_proceeds = sell_result.filled_quantity * sell_result.average_price
        total_fees = buy_result.total_fees_usd + sell_result.total_fees_usd
        total_pnl = sell_proceeds - buy_cost - total_fees
        slippage_pct = (
            (buy_result.slippage_bps + sell_result.slippage_bps) / 2.0
        ) / 100.0

        return ExecutionResult(
            success=True,
            order_id=f"{buy_result.order_id}|{sell_result.order_id}",
            filled_quantity=min(
                buy_result.filled_quantity, sell_result.filled_quantity
            ),
            average_price=(buy_result.average_price + sell_result.average_price) / 2.0,
            slippage_bps=(buy_result.slippage_bps + sell_result.slippage_bps) / 2.0,
            fees=total_fees,
            timestamp=timestamp,
            trades=combined_trades,
            total_pnl_usd=total_pnl,
            total_fees_usd=total_fees,
            actual_slippage_pct=slippage_pct,
            metadata={"opportunity_id": opportunity_id},
        )

    def cancel_all_orders(
        self, symbol: Optional[str] = None, exchange_name: Optional[str] = None
    ) -> int:
        cancelled = 0
        exchange_names = (
            [exchange_name] if exchange_name else list(self.exchange_connectors.keys())
        )
        for name in exchange_names:
            _, connector = self._get_connector(name)
            try:
                for order in connector.get_open_orders(symbol):
                    try:
                        if connector.cancel_order(order.order_id):
                            cancelled += 1
                            self.active_orders.pop(order.order_id, None)
                    except Exception as exc:
                        log.warning("Failed to cancel order %s on %s: %s", order.order_id, name, exc)
            except Exception as exc:
                log.warning("Failed to query open orders on %s: %s", name, exc)
        return cancelled

    def get_execution_stats(self) -> Dict[str, Any]:
        avg_slippage = (
            self.total_slippage_bps / self.successful_executions
            if self.successful_executions
            else 0.0
        )
        success_rate = (
            self.successful_executions / self.execution_count
            if self.execution_count
            else 0.0
        )
        return {
            "execution_count": self.execution_count,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": success_rate,
            "average_slippage_bps": avg_slippage,
            "total_fees_usd": self.total_fees,
            "active_orders": len(self.active_orders),
            "emergency_stop": self.emergency_stop,
            "allow_live_trading": self.allow_live_trading,
            "exchanges": sorted(self.exchange_connectors.keys()),
        }

    def set_emergency_stop(self, active: bool = True) -> None:
        self.emergency_stop = active
        if active:
            self.cancel_all_orders()


def test_trade_executor() -> None:
    """Basic smoke test for local manual runs."""
    from .exchange_connector import StubExchangeConnector

    exchange = StubExchangeConnector(sandbox=True)
    executor = TradeExecutor(
        exchange_connector=exchange,
        max_position_size_usd=50.0,
        max_slippage_bps=10.0,
        emergency_stop=False,
    )
    result = executor.execute_trade("BTC-USD", OrderSide.BUY, 0.0005)
    print(result.to_dict())


if __name__ == "__main__":
    test_trade_executor()
