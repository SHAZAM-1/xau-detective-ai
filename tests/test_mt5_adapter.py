from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from xau_detective.environment import TradingEnvironment
from xau_detective.mt5_adapter import (
    account_capabilities_from_mt5,
    candle_from_mt5,
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


def test_candle_from_mt5_normalizes_aware_datetime_to_utc():
    timestamp = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
    candle = candle_from_mt5(
        SimpleNamespace(
            time=timestamp,
            open=3900,
            high=3910,
            low=3890,
            close=3905,
            tick_volume=10,
        )
    )
    assert candle.timestamp == timestamp


def test_candle_from_mt5_assumes_naive_datetime_is_utc():
    timestamp = datetime(2026, 9, 27, 18, 0)
    candle = candle_from_mt5(
        SimpleNamespace(
            time=timestamp,
            open=3900,
            high=3910,
            low=3890,
            close=3905,
            tick_volume=10,
        )
    )
    assert candle.timestamp == timestamp.replace(tzinfo=UTC)


def test_candle_from_mt5_rejects_invalid_timestamp_type():
    with pytest.raises(TypeError, match="timestamp must be numeric or datetime"):
        candle_from_mt5(
            SimpleNamespace(
                time="2026-09-27T18:00:00Z",
                open=3900,
                high=3910,
                low=3890,
                close=3905,
            )
        )



def test_candle_from_mt5_supports_structured_field_access():
    class NumpyVoidLike:
        def __init__(self):
            self.values = {
                "time": 1767225600,
                "open": 4000,
                "high": 4010,
                "low": 3990,
                "close": 4005,
                "tick_volume": 10,
            }

        def __getitem__(self, name):
            return self.values[name]

    candle = candle_from_mt5(NumpyVoidLike())
    assert candle.close == Decimal(4005)
    assert candle.volume == Decimal(10)


def test_candle_from_mt5_accepts_numeric_timestamp_like_numpy():
    class NumericLike:
        def __float__(self):
            return 1767225600.0

    candle = candle_from_mt5(
        SimpleNamespace(
            time=NumericLike(),
            open=4000,
            high=4010,
            low=3990,
            close=4005,
        )
    )
    assert candle.timestamp == datetime.fromtimestamp(1767225600, tz=UTC)
