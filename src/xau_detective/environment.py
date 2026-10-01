"""Trading environment and execution capability policy.

The environment is explicit by design: a small balance must never be used to
infer whether an MT5 account is demo or live.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TradingEnvironment(str, Enum):
    RESEARCH = "RESEARCH"
    DEMO = "DEMO"
    LIVE = "LIVE"


@dataclass(frozen=True)
class AccountCapabilities:
    environment: TradingEnvironment
    connected: bool
    connection_healthy: bool
    trading_allowed: bool
    execution_enabled: bool
    symbol_available: bool
    symbol: str
    server: str | None = None


def can_execute_orders(capabilities: AccountCapabilities) -> bool:
    """Return whether the current V1 policy permits order execution.

    Research never executes. Demo execution requires explicit opt-in and all
    connectivity/trading gates. Live execution remains locked in V1 even if
    connected, because live deployment requires the separate validation gate.
    """
    if capabilities.environment is TradingEnvironment.RESEARCH:
        return False
    if capabilities.environment is TradingEnvironment.LIVE:
        return False
    return (
        capabilities.connected
        and capabilities.connection_healthy
        and capabilities.trading_allowed
        and capabilities.execution_enabled
        and capabilities.symbol_available
    )


def environment_reason(capabilities: AccountCapabilities) -> str:
    """Return a stable reason for the current execution policy decision."""
    if capabilities.environment is TradingEnvironment.RESEARCH:
        return "RESEARCH_MODE_NO_ORDERS"
    if capabilities.environment is TradingEnvironment.LIVE:
        return "LIVE_EXECUTION_LOCKED_V1"
    if not capabilities.connected:
        return "MT5_NOT_CONNECTED"
    if not capabilities.connection_healthy:
        return "MT5_CONNECTION_UNHEALTHY"
    if not capabilities.trading_allowed:
        return "ACCOUNT_TRADING_DISABLED"
    if not capabilities.symbol_available:
        return "SYMBOL_UNAVAILABLE"
    if not capabilities.execution_enabled:
        return "DEMO_EXECUTION_NOT_ENABLED"
    return "OK"
