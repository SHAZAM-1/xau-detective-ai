from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.zones import analyze_zones


def _candle(i: int, low: str, high: str, close: str) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


def test_zones_cluster_repeated_swing_levels() -> None:
    candles = (
        _candle(0, "99", "101", "100"),
        _candle(1, "95", "102", "97"),
        _candle(2, "98", "105", "102"),
        _candle(3, "95", "103", "98"),
        _candle(4, "98", "105", "103"),
        _candle(5, "99", "104", "104"),
        _candle(6, "100", "106", "105"),
    )
    result = analyze_zones(tuple(candles), tolerance_fraction=Decimal("0.02"))
    assert result.support
    assert result.resistance
    assert result.support[0].kind == "SUPPORT"
    assert result.resistance[0].kind == "RESISTANCE"
    assert result.support[0].touches >= 2


def test_zones_fail_closed_on_flat_data() -> None:
    candles = tuple(_candle(i, "100", "100", "100") for i in range(10))
    result = analyze_zones(candles)
    assert result.support == ()
    assert result.resistance == ()
