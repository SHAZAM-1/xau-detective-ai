"""Demo-only order execution boundary with deterministic safety gates."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol

from .environment import (
    AccountCapabilities,
    TradingEnvironment,
    can_execute_orders,
    environment_reason,
)
from .models import Direction, RiskResult
from .trading_profile import TradingProfile


class TradeSource(str, Enum):
    BOT_SUGGESTION = "BOT_SUGGESTION"
    USER_DEFINED = "USER_DEFINED"


@dataclass(frozen=True)


class TradeIntent:
    symbol: str
    direction: Direction
    volume: Decimal
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    source: TradeSource
    idempotency_key: str
    risk: RiskResult


@dataclass(frozen=True)


class DemoOrderResult:
    submitted: bool
    reason: str
    order_id: str | None = None
    intent: TradeIntent | None = None


class MT5OrderGateway(Protocol):
    """Broker gateway used by the Demo executor; CI uses a fake implementation."""

    def send_order(self, intent: TradeIntent) -> str: ...


class DemoOrderExecutor:
    """Stateful Demo-only executor with an in-memory duplicate-order guard."""

    def __init__(self, gateway: MT5OrderGateway) -> None:
        self._gateway = gateway
        self._submitted_keys: set[str] = set()

    def execute(
        self,
        *,
        capabilities: AccountCapabilities,
        profile: TradingProfile,
        intent: TradeIntent,
    ) -> DemoOrderResult:
        profile.validate()
        if capabilities.environment is not TradingEnvironment.DEMO:
            return DemoOrderResult(False, environment_reason(capabilities), intent=intent)
        if not can_execute_orders(capabilities):
            return DemoOrderResult(False, environment_reason(capabilities), intent=intent)
        if not profile.auto_execution_enabled:
            return DemoOrderResult(False, "AUTO_EXECUTION_DISABLED", intent=intent)
        if not capabilities.symbol_available or intent.symbol != capabilities.symbol:
            return DemoOrderResult(False, "SYMBOL_UNAVAILABLE", intent=intent)
        if intent.direction is Direction.NO_TRADE:
            return DemoOrderResult(False, "NO_TRADE_DIRECTION", intent=intent)
        if not intent.risk.executable:
            return DemoOrderResult(False, "RISK_RESULT_NOT_EXECUTABLE", intent=intent)
        if intent.volume <= 0:
            return DemoOrderResult(False, "INVALID_VOLUME", intent=intent)
        if intent.idempotency_key in self._submitted_keys:
            return DemoOrderResult(False, "DUPLICATE_ORDER", intent=intent)

        order_id = self._gateway.send_order(intent)
        self._submitted_keys.add(intent.idempotency_key)
        return DemoOrderResult(True, "DEMO_ORDER_SUBMITTED", order_id=order_id, intent=intent)


def build_user_defined_intent(
    *,
    symbol: str,
    direction: Direction,
    volume: Decimal,
    entry: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    risk: RiskResult,
    idempotency_key: str,
    profile: TradingProfile,
) -> TradeIntent:
    """Build a user-defined trade without requiring bot suggestions."""
    profile.validate()
    if profile.bot_suggestions_enabled:
        raise ValueError("USER_DEFINED_INTENT_REQUIRES_SUGGESTIONS_OFF")
    return TradeIntent(
        symbol=symbol,
        direction=direction,
        volume=volume,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        source=TradeSource.USER_DEFINED,
        idempotency_key=idempotency_key,
        risk=risk,
    )
