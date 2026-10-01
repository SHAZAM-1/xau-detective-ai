from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.pattern_context_study import build_context_dataset, study_pattern_context


def candle(i: int, open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        Decimal(open_),
        Decimal(high),
        Decimal(low),
        Decimal(close),
    )


def test_context_study_is_point_in_time_safe_and_stratified():
    candles = tuple(
        candle(i, str(100 + i), str(101 + i), str(99 + i), str(100 + i))
        for i in range(70)
    )
    rows = build_context_dataset({"M5": candles}, horizons=(1, 3))

    assert rows
    assert {row.timeframe for row in rows} == {"M5"}
    assert all(row.horizon in {1, 3} for row in rows)
    timestamps = {item.timestamp for item in candles}
    assert all(row.timestamp in timestamps for row in rows)

    studies = study_pattern_context({"M5": candles}, horizons=(1, 3))
    assert studies
    assert all(Decimal("0") <= item.directional_win_rate <= Decimal("1") for item in studies)
    assert all(item.observations >= 1 for item in studies)
