"""Deterministic broker/execution validation before any MT5 order send."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .demo_execution import TradeIntent
from .environment import AccountCapabilities, TradingEnvironment
from .models import Direction


@dataclass(frozen=True)
class ExecutionGateResult:
    allowed: bool
    reason: str


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

        # Validate every numeric value used by this gate before comparisons.
        # Decimal NaN/Infinity can otherwise raise during ordering checks or
        # evade ordinary range checks; malformed broker/account snapshots must
        # fail closed with a stable result rather than escaping the gate.
        numeric_inputs = [
            intent.volume,
            intent.entry,
            intent.stop_loss,
            intent.take_profit,
            estimated_slippage,
            getattr(symbol_info, "volume_min", "0"),
            getattr(symbol_info, "volume_max", "0"),
            getattr(symbol_info, "volume_step", "0"),
            getattr(symbol_info, "bid", "0"),
            getattr(symbol_info, "ask", "0"),
            getattr(symbol_info, "point", "0"),
            getattr(symbol_info, "trade_stops_level", "0"),
            getattr(symbol_info, "trade_freeze_level", "0"),
            getattr(account_info, "margin_free", "0"),
        ]
        if max_spread is not None:
            numeric_inputs.append(max_spread)
        if max_slippage is not None:
            numeric_inputs.append(max_slippage)
        try:
            normalized_inputs = [Decimal(str(value)) for value in numeric_inputs]
        except (InvalidOperation, TypeError, ValueError):
            return ExecutionGateResult(False, "INVALID_EXECUTION_NUMERIC_VALUE")
        if any(not value.is_finite() for value in normalized_inputs):
            return ExecutionGateResult(False, "INVALID_EXECUTION_NUMERIC_VALUE")

        if getattr(symbol_info, "trade_mode", 0) == 0:
            return ExecutionGateResult(False, "SYMBOL_TRADING_DISABLED")

        order_mode = getattr(symbol_info, "order_mode", None)
        market_flag = getattr(mt5, "SYMBOL_ORDER_MARKET", 1)
        if order_mode is not None and not (int(order_mode) & int(market_flag)):
            return ExecutionGateResult(False, "MARKET_ORDERS_NOT_ALLOWED")

        volume = intent.volume
        volume_min = Decimal(str(getattr(symbol_info, "volume_min", "0")))
        volume_max = Decimal(str(getattr(symbol_info, "volume_max", "0")))
        volume_step = Decimal(str(getattr(symbol_info, "volume_step", "0")))
        if volume <= 0 or volume_min <= 0 or volume_step <= 0:
            return ExecutionGateResult(False, "INVALID_BROKER_VOLUME_SPEC")
        if volume < volume_min:
            return ExecutionGateResult(False, "VOLUME_BELOW_BROKER_MIN")
        if volume > volume_max:
            return ExecutionGateResult(False, "VOLUME_ABOVE_BROKER_MAX")
        if (volume - volume_min) % volume_step != 0:
            return ExecutionGateResult(False, "VOLUME_NOT_ALIGNED_TO_STEP")

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
        point = Decimal(str(getattr(symbol_info, "point", "0")))
        if point <= 0:
            return ExecutionGateResult(False, "INVALID_SYMBOL_POINT")
        price_tolerance = point * Decimal("2")
        if abs(intent.entry - expected_entry) > price_tolerance:
            return ExecutionGateResult(False, "STALE_OR_WRONG_SIDE_ENTRY")

        if intent.direction is Direction.BUY:
            if not (intent.stop_loss < intent.entry < intent.take_profit):
                return ExecutionGateResult(False, "INVALID_BUY_SL_TP")
        else:
            if not (intent.take_profit < intent.entry < intent.stop_loss):
                return ExecutionGateResult(False, "INVALID_SELL_SL_TP")

        stops_level = Decimal(str(getattr(symbol_info, "trade_stops_level", "0")))
        freeze_level = Decimal(str(getattr(symbol_info, "trade_freeze_level", "0")))
        min_distance = max(stops_level, freeze_level) * point

        if intent.direction is Direction.BUY:
            if intent.entry - intent.stop_loss < min_distance:
                return ExecutionGateResult(False, "BUY_STOP_TOO_CLOSE")
            if intent.take_profit - intent.entry < min_distance:
                return ExecutionGateResult(False, "BUY_TP_TOO_CLOSE")
        else:
            if intent.stop_loss - intent.entry < min_distance:
                return ExecutionGateResult(False, "SELL_STOP_TOO_CLOSE")
            if intent.entry - intent.take_profit < min_distance:
                return ExecutionGateResult(False, "SELL_TP_TOO_CLOSE")

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
            try:
                normalized_margin = Decimal(str(margin))
            except (InvalidOperation, TypeError, ValueError):
                return ExecutionGateResult(False, "MARGIN_CALCULATION_FAILED")
            if not normalized_margin.is_finite() or normalized_margin < 0:
                return ExecutionGateResult(False, "MARGIN_CALCULATION_FAILED")
            if normalized_margin >= free_margin:
                return ExecutionGateResult(False, "INSUFFICIENT_FREE_MARGIN")

        return ExecutionGateResult(True, "OK")
