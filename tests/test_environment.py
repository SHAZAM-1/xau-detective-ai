from types import SimpleNamespace

from xau_detective.environment import (
    AccountCapabilities,
    TradingEnvironment,
    can_execute_orders,
    environment_reason,
)
from xau_detective.mt5_adapter import account_capabilities_from_mt5


def capability(**overrides):
    values = dict(
        environment=TradingEnvironment.DEMO,
        connected=True,
        connection_healthy=True,
        trading_allowed=True,
        execution_enabled=True,
        symbol_available=True,
        symbol="XAUUSD",
    )
    values.update(overrides)
    return AccountCapabilities(**values)


def test_research_never_allows_orders():
    caps = capability(environment=TradingEnvironment.RESEARCH)
    assert not can_execute_orders(caps)
    assert environment_reason(caps) == "RESEARCH_MODE_NO_ORDERS"


def test_demo_requires_explicit_execution_enablement():
    caps = capability(execution_enabled=False)
    assert not can_execute_orders(caps)
    assert environment_reason(caps) == "DEMO_EXECUTION_NOT_ENABLED"


def test_demo_can_execute_only_when_all_gates_pass():
    assert can_execute_orders(capability())


def test_demo_rejects_unhealthy_or_disabled_connections():
    assert not can_execute_orders(capability(connection_healthy=False))
    assert environment_reason(capability(connection_healthy=False)) == "MT5_CONNECTION_UNHEALTHY"
    assert not can_execute_orders(capability(trading_allowed=False))
    assert environment_reason(capability(trading_allowed=False)) == "ACCOUNT_TRADING_DISABLED"
    assert not can_execute_orders(capability(symbol_available=False))
    assert environment_reason(capability(symbol_available=False)) == "SYMBOL_UNAVAILABLE"


def test_live_execution_is_locked_in_v1():
    caps = capability(environment=TradingEnvironment.LIVE)
    assert not can_execute_orders(caps)
    assert environment_reason(caps) == "LIVE_EXECUTION_LOCKED_V1"


def test_mt5_environment_is_explicit_not_inferred_from_balance():
    info = SimpleNamespace(
        balance=20.0,
        trade_allowed=True,
        server="DemoBroker-Server",
    )
    caps = account_capabilities_from_mt5(
        info,
        environment=TradingEnvironment.DEMO,
        connected=True,
        connection_healthy=True,
        execution_enabled=False,
    )
    assert caps.environment is TradingEnvironment.DEMO
    assert caps.server == "DemoBroker-Server"
    assert caps.trading_allowed
