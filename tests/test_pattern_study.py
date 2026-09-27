from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from xau_detective.market import Candle
from xau_detective.pattern_study import build_pattern_dataset, study_patterns


def candle(i: int, open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        Decimal(open_),
        Decimal(high),
        Decimal(low),
        Decimal(close),
    )


def test_pattern_study_uses_only_complete_forward_horizons():
    candles = (
        candle(0, "100", "101", "99", "99"),
        candle(1, "99", "100", "98", "98"),
        candle(2, "98", "102", "97", "101"),
        candle(3, "101", "103", "100", "102"),
        candle(4, "102", "104", "101", "103"),
        candle(5, "103", "105", "102", "104"),
        candle(6, "104", "106", "103", "105"),
    )

    results = study_patterns(candles, horizon=2)

    assert results
    assert all(item.observations > 0 for item in results)
    assert all(item.sample_horizon == 2 for item in results)
    assert all(Decimal("0") <= item.directional_win_rate <= Decimal("1") for item in results)


def test_pattern_dataset_is_timeframe_aware_and_excludes_incomplete_horizons():
    candles = (
        candle(0, "100", "101", "99", "99"),
        candle(1, "99", "100", "98", "98"),
        candle(2, "98", "102", "97", "101"),
        candle(3, "101", "103", "100", "102"),
        candle(4, "102", "104", "101", "103"),
        candle(5, "103", "105", "102", "104"),
        candle(6, "104", "106", "103", "105"),
    )

    rows = build_pattern_dataset({"M5": candles, "M15": candles}, horizons=(1, 3))

    assert rows
    assert {row.timeframe for row in rows} == {"M5", "M15"}
    assert all(row.horizon in {1, 3} for row in rows)
    assert all(row.timestamp == candles[row.index].timestamp for row in rows)


def test_pattern_study_rejects_invalid_horizon():
    with pytest.raises(ValueError, match="horizon"):
        study_patterns((), horizon=0)
