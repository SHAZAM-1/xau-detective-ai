from decimal import Decimal
from datetime import UTC, datetime, timedelta

from xau_detective.market import Candle
from xau_detective.method_analysis import analyze_methods


def _candle(i: int, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        open=value,
        high=value + Decimal("1"),
        low=value - Decimal("1"),
        close=value,
        volume=Decimal("1"),
    )


def test_method_analysis_is_research_only_and_detects_conflict() -> None:
    candles = tuple(_candle(i, str(100 + i)) for i in range(22))
    result = analyze_methods(candles)
    assert result.signals
    assert any(signal.method == "MOMENTUM" for signal in result.signals)
    assert result.contradictions == ("METHOD_DIRECTION_CONFLICT",)
