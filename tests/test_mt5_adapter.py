from decimal import Decimal
from types import SimpleNamespace

import pytest

from xau_detective.environment import TradingEnvironment
from xau_detective.mt5_adapter import (
    account_capabilities_from_mt5,
    execution_snapshot_from_mt5,
)


def test_execution_snapshot_from_mt5_maps_tick_and_margin():
    snapshot = execution_snapshot_from_mt5(
        SimpleNamespace(bid=3999.9, ask=4000.1),
        margin_per_lot=Decimal(1500),
        estimated_slippage=Decimal("0.03"),
    )
    assert snapshot.bid == Decimal("3999.9")
    assert snapshot.ask == Decimal("4000.1")
    assert snapshot.spread == Decimal("0.2")
    assert snapshot.margin_per_lot == Decimal(1500)
    assert snapshot.estimated_slippage == Decimal("0.03")


def test_account_capabilities_auto_detects_demo():
    account = SimpleNamespace(
        trade_mode=0,
        trade_allowed=True,
        server="Demo-Server",
    )
    capabilities = account_capabilities_from_mt5(
        account,
        connected=True,
        connection_healthy=True,
        execution_enabled=True,
    )
    assert capabilities.environment is TradingEnvironment.DEMO
    assert capabilities.server == "Demo-Server"


def test_account_capabilities_auto_detects_live():
    account = SimpleNamespace(
        trade_mode=2,
        trade_allowed=True,
        server="Live-Server",
    )
    capabilities = account_capabilities_from_mt5(
        account,
        connected=True,
        connection_healthy=True,
    )
    assert capabilities.environment is TradingEnvironment.LIVE


def test_account_capabilities_rejects_unknown_trade_mode():
    account = SimpleNamespace(trade_mode=99, trade_allowed=True)
    with pytest.raises(ValueError, match="UNSUPPORTED_MT5_ACCOUNT_TRADE_MODE"):
        account_capabilities_from_mt5(
            account,
            connected=True,
            connection_healthy=True,
        )


def test_account_capabilities_allows_explicit_override_for_tests():
    account = SimpleNamespace(trade_mode=0, trade_allowed=True)
    capabilities = account_capabilities_from_mt5(
        account,
        connected=True,
        connection_healthy=True,
        environment=TradingEnvironment.LIVE,
    )
    assert capabilities.environment is TradingEnvironment.LIVE
