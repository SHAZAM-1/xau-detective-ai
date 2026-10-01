from datetime import datetime, timedelta, timezone
from decimal import Decimal

from xau_detective.pattern_study import PatternDatasetRow
from xau_detective.validation import (
    aggregate_test_metrics,
    chronological_split,
    evaluate_out_of_sample,
    walk_forward,
)


def _rows(count: int = 20) -> tuple[PatternDatasetRow, ...]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(
        PatternDatasetRow(
            timeframe="M5",
            pattern="Hammer",
            timestamp=start + timedelta(minutes=i),
            index=i,
            direction="BULLISH" if i % 2 == 0 else "BEARISH",
            confidence=Decimal("0.8"),
            horizon=1,
            forward_return=Decimal("0.01") if i % 3 else Decimal("-0.005"),
            mfe=Decimal("0.02"),
            mae=Decimal("0.005"),
        )
        for i in range(count)
    )


def test_chronological_split_never_shuffles():
    rows = _rows()
    train, test = chronological_split(rows, train_fraction=Decimal("0.7"))
    assert len(train) == 14
    assert len(test) == 6
    assert train[-1].timestamp < test[0].timestamp


def test_chronological_split_purges_forward_labels_crossing_test_boundary():
    rows = _rows(10)
    train, test = chronological_split(
        rows,
        train_fraction=Decimal("0.5"),
        purge_horizon=2,
    )
    assert [row.index for row in train] == [0, 1, 2]
    assert test[0].index == 5
    assert all(row.index + row.horizon < test[0].index for row in train)


def test_oos_has_disjoint_time_windows():
    result = evaluate_out_of_sample(_rows())
    assert result.train.observations == 14
    assert result.test.observations == 6
    assert result.train_end_index < result.test_start_index


def test_walk_forward_has_disjoint_train_and_test_windows():
    folds = walk_forward(_rows(), train_size=8, test_size=4, step_size=4)
    assert len(folds) == 3
    for fold in folds:
        assert fold.train_end_index < fold.test_start_index
        assert fold.test.observations == 4


def test_aggregate_requires_non_overlapping_test_windows():
    folds = walk_forward(_rows(), train_size=8, test_size=4, step_size=4)
    result = aggregate_test_metrics(folds)
    assert result.observations == 12
    assert Decimal(0) <= result.directional_win_rate <= Decimal(1)
