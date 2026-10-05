"""Deterministic broker/execution validation before any MT5 order send."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .demo_execution import TradeIntent
from .environment import AccountCapabilities, TradingEnvironment
from .models import Direction


@dataclass(frozen=True)
class ExecutionGateResult:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class BrokerSymbolConstraints:
    """Pure broker symbol limits shared by live execution and backtesting."""

    point: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    trade_stops_level: Decimal = Decimal(0)
    trade_freeze_level: Decimal = Decimal(0)

    @property
    def minimum_stop_distance(self) -> Decimal:
        return max(self.trade_stops_level, self.trade_freeze_level) * self.point


def validate_broker_trade(
    *,
    direction: Direction,
    entry: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    volume: Decimal,
    constraints: BrokerSymbolConstraints,
) -> str | None:
    """Return a broker-constraint rejection reason, or None when valid."""
    if (
        constraints.point <= 0
        or constraints.volume_min <= 0
        or constraints.volume_max < constraints.volume_min
        or constraints.volume_step <= 0
        or constraints.trade_stops_level < 0
        or constraints.trade_freeze_level < 0
    ):
        return "INVALID_BROKER_SYMBOL_SPEC"

    if volume < constraints.volume_min:
        return "VOLUME_BELOW_BROKER_MIN"
    if volume > constraints.volume_max:
        return "VOLUME_ABOVE_BROKER_MAX"
    if (volume - constraints.volume_min) % constraints.volume_step != 0:
        return "VOLUME_NOT_ALIGNED_TO_STEP"

    min_distance = constraints.minimum_stop_distance
    if direction is Direction.BUY:
        if entry - stop_loss < min_distance:
            return "BUY_STOP_TOO_CLOSE"
        if take_profit - entry < min_distance:
            return "BUY_TP_TOO_CLOSE"
    elif direction is Direction.SELL:
        if stop_loss - entry < min_distance:
            return "SELL_STOP_TOO_CLOSE"
        if entry - take_profit < min_distance:
            return "SELL_TP_TOO_CLOSE"

    return None


class BrokerExecutionGate:
    """Validate broker/account/order invariants before reaching order_send."""

    def validate(
        self,
        *,
        mt5: Any,
        capabilities: AccountCapabilities,
        account_info: Any,
        symbol_info: Any,
        intent: TradeIntent,
        max_spread: Decimal | None = None,
        max_slippage: Decimal | None = None,
        estimated_slippage: Decimal = Decimal(0),
    ) -> ExecutionGateResult:
        if capabilities.environment is not TradingEnvironment.DEMO:
            return ExecutionGateResult(False, "LIVE_OR_NON_DEMO_ACCOUNT")
        if not capabilities.connected or not capabilities.connection_healthy:
            return ExecutionGateResult(False, "MT5_CONNECTION_UNHEALTHY")
        if not capabilities.trading_allowed:
            return ExecutionGateResult(False, "ACCOUNT_TRADING_DISABLED")
        if not capabilities.execution_enabled:
            return ExecutionGateResult(False, "DEMO_EXECUTION_NOT_ENABLED")
        if not capabilities.symbol_available:
            return ExecutionGateResult(False, "SYMBOL_UNAVAILABLE")
        if symbol_info is None:
            return ExecutionGateResult(False, "SYMBOL_INFO_UNAVAILABLE")
        if intent.symbol != capabilities.symbol:
            return ExecutionGateResult(False, "SYMBOL_MISMATCH")
        if intent.direction is Direction.NO_TRADE:
            return ExecutionGateResult(False, "NO_TRADE_DIRECTION")

        if getattr(symbol_info, "trade_mode", 0) == 0:
            return ExecutionGateResult(False, "SYMBOL_TRADING_DISABLED")

        order_mode = getattr(symbol_info, "order_mode", None)
        market_flag = getattr(mt5, "SYMBOL_ORDER_MARKET", 1)
        if order_mode is not None and not (int(order_mode) & int(market_flag)):
            return ExecutionGateResult(False, "MARKET_ORDERS_NOT_ALLOWED")

        constraints = BrokerSymbolConstraints(
            point=Decimal(str(getattr(symbol_info, "point", "0"))),
            volume_min=Decimal(str(getattr(symbol_info, "volume_min", "0"))),
            volume_max=Decimal(str(getattr(symbol_info, "volume_max", "0"))),
            volume_step=Decimal(str(getattr(symbol_info, "volume_step", "0"))),
            trade_stops_level=Decimal(
                str(getattr(symbol_info, "trade_stops_level", "0"))
            ),
            trade_freeze_level=Decimal(
                str(getattr(symbol_info, "trade_freeze_level", "0"))
            ),
        )
        volume_spec_reason = validate_broker_trade(
            direction=intent.direction,
            entry=intent.entry,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            volume=intent.volume,
            constraints=constraints,
        )
        if volume_spec_reason == "INVALID_BROKER_SYMBOL_SPEC":
            return ExecutionGateResult(False, volume_spec_reason)

        bid = Decimal(str(getattr(symbol_info, "bid", "0")))
        ask = Decimal(str(getattr(symbol_info, "ask", "0")))
        if bid <= 0 or ask <= 0 or ask < bid:
            return ExecutionGateResult(False, "INVALID_MARKET_PRICE")

        spread = ask - bid
        if max_spread is not None and spread > max_spread:
            return ExecutionGateResult(False, "SPREAD_LIMIT_EXCEEDED")
        if max_slippage is not None and estimated_slippage > max_slippage:
            return ExecutionGateResult(False, "SLIPPAGE_LIMIT_EXCEEDED")

        expected_entry = ask if intent.direction is Direction.BUY else bid
        price_tolerance = constraints.point * Decimal("2")
        if abs(intent.entry - expected_entry) > price_tolerance:
            return ExecutionGateResult(False, "STALE_OR_WRONG_SIDE_ENTRY")

        if intent.direction is Direction.BUY:
            if not (intent.stop_loss < intent.entry < intent.take_profit):
                return ExecutionGateResult(False, "INVALID_BUY_SL_TP")
        else:
            if not (intent.take_profit < intent.entry < intent.stop_loss):
                return ExecutionGateResult(False, "INVALID_SELL_SL_TP")

        if volume_spec_reason is not None:
            return ExecutionGateResult(False, volume_spec_reason)

        free_margin = Decimal(str(getattr(account_info, "margin_free", "0")))
        if free_margin <= 0:
            return ExecutionGateResult(False, "INSUFFICIENT_FREE_MARGIN")

        calc_margin = getattr(mt5, "order_calc_margin", None)
        if callable(calc_margin):
            order_type = (
                mt5.ORDER_TYPE_BUY
                if intent.direction is Direction.BUY
                else mt5.ORDER_TYPE_SELL
            )
            try:
                margin = calc_margin(
                    order_type,
                    intent.symbol,
                    float(intent.volume),
                    float(intent.entry),
                )
            except Exception:
                return ExecutionGateResult(False, "MARGIN_CALCULATION_FAILED")
            if margin is None:
                return ExecutionGateResult(False, "MARGIN_CALCULATION_FAILED")
            if Decimal(str(margin)) >= free_margin:
                return ExecutionGateResult(False, "INSUFFICIENT_FREE_MARGIN")

        return ExecutionGateResult(True, "OK")
