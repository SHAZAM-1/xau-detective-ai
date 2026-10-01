from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.mean_reversion import analyze_mean_reversion


def _candle(i: int, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        open=value,
        high=value + Decimal("1"),
        low=value - Decimal("1"),
        close=value,
    )


def test_mean_reversion_detects_downside_stretch() -> None:
    closes = [str(100 + (i % 2)) for i in range(20)] + ["100", "90"]
    result = analyze_mean_reversion(tuple(_candle(i, value) for i, value in enumerate(closes)))
    assert result is not None
    assert result.direction == "BUY"
    assert result.z_score < 0
    assert "MEAN_REVERSION_STRETCH" in result.evidence


def test_mean_reversion_detects_upside_stretch() -> None:
    closes = [str(100 + (i % 2)) for i in range(20)] + ["100", "110"]
    result = analyze_mean_reversion(tuple(_candle(i, value) for i, value in enumerate(closes)))
    assert result is not None
    assert result.direction == "SELL"
    assert result.z_score > 0


def test_mean_reversion_fails_closed_on_flat_data() -> None:
    candles = tuple(_candle(i, "100") for i in range(25))
    assert analyze_mean_reversion(candles) is None
