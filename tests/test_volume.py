from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.volume import analyze_volume


def _candle(i: int, volume: str, *, open_: str = "100", close: str = "101") -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        open=Decimal(open_),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal(volume),
    )


def test_volume_expansion_and_bullish_proxy() -> None:
    candles = tuple(_candle(i, "100") for i in range(20)) + (_candle(20, "200"),)
    result = analyze_volume(candles)
    assert result is not None
    assert result.state == "EXPANSION"
    assert result.relative_volume == Decimal("2")
    assert result.directional_pressure == "BULLISH_PROXY"
    assert "VOLUME_TYPE_UNSPECIFIED" in result.evidence


def test_volume_contraction_and_bearish_proxy() -> None:
    candles = tuple(_candle(i, "100") for i in range(20)) + (
        _candle(20, "50", open_="101", close="100"),
    )
    result = analyze_volume(candles, volume_kind="TICK")
    assert result is not None
    assert result.state == "CONTRACTION"
    assert result.relative_volume == Decimal("0.5")
    assert result.directional_pressure == "BEARISH_PROXY"
    assert "VOLUME_TYPE_TICK" in result.evidence


def test_volume_fails_closed_for_missing_or_invalid_volume() -> None:
    candles = tuple(_candle(i, "0") for i in range(21))
    assert analyze_volume(candles) is None
    assert analyze_volume(candles, volume_kind="ORDER_FLOW") is None
    assert analyze_volume(candles, lookback=0) is None