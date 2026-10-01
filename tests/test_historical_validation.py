from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from xau_detective.historical_validation import (
    HistoricalValidationConfig,
    validate_historical_csv,
)
from xau_detective.timeframes import Timeframe


def _csv(path: Path, count: int = 20) -> None:
    rows = ["timestamp,open,high,low,close"]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(count):
        price = Decimal(4300 + i)
        rows.append(
            f"{(start + timedelta(hours=i)).isoformat()},"
            f"{price},{price + 10},{price - 10},{price + 5}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_validate_historical_csv_requires_usable_source_quality(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,open,high,low,close\n"
        "2026-01-01T01:00:00Z,4300,4310,4290,4305\n"
        "2026-01-01T00:00:00Z,4305,4320,4300,4315\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="historical dataset is not usable"):
        validate_historical_csv(
            path, symbol="XAUUSD", timeframe=Timeframe.H1, source="test"
        )


def test_validate_historical_csv_builds_oos_and_walk_forward_report(tmp_path: Path):
    path = tmp_path / "good.csv"
    _csv(path, count=40)

    report = validate_historical_csv(
        path,
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        source="test",
        config=HistoricalValidationConfig(
            train_fraction=Decimal("0.70"),
            walk_forward_train_size=10,
            walk_forward_test_size=5,
            walk_forward_step_size=5,
            horizons=(1, 3, 5),
        ),
    )

    assert report.dataset.quality.usable
    assert report.pattern_rows
    assert report.out_of_sample.train.observations > 0
    assert report.out_of_sample.test.observations > 0
    assert report.out_of_sample.train_end_index < report.out_of_sample.test_start_index
    assert report.walk_forward_folds
    assert report.walk_forward_test.observations > 0


def test_validate_historical_csv_rejects_too_few_research_rows(tmp_path: Path):
    path = tmp_path / "tiny.csv"
    _csv(path, count=2)

    with pytest.raises(ValueError, match="fewer than two"):
        validate_historical_csv(
            path,
            symbol="XAUUSD",
            timeframe=Timeframe.H1,
            source="test",
            config=HistoricalValidationConfig(horizons=(5,)),
        )
