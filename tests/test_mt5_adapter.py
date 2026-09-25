from decimal import Decimal
from types import SimpleNamespace
from datetime import timezone


from xau_detective.mt5_adapter import (
    account_snapshot_from_mt5,
    broker_spec_from_mt5,
    candle_from_mt5,
)


def test_mt5_rate_mapping():
    rate = {
        "time": 1767225600,
        "open": 4000.0,
        "high": 4010.0,
        "low": 3995.0,
        "close": 4005.0,
        "tick_volume": 123,
    }
    candle = candle_from_mt5(rate)
    assert candle.timestamp.tzinfo == timezone.utc
    assert candle.close == Decimal("4005.0")
    assert candle.volume == Decimal(123)


def test_mt5_symbol_mapping():
    info = SimpleNamespace(
        name="XAUUSD",
        trade_contract_size=100,
        volume_min=0.01,
        volume_max=100,
        volume_step=0.01,
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        point=0.01,
        trade_stops_level=50,
    )
    spec = broker_spec_from_mt5(info)
    assert spec.symbol == "XAUUSD"
    assert spec.min_stop_distance == Decimal("0.50")


def test_mt5_account_mapping():
    info = SimpleNamespace(balance=20, equity=19.5, margin_free=18)
    account = account_snapshot_from_mt5(info)
    assert account.balance == Decimal(20)
    assert account.free_margin == Decimal(18)
