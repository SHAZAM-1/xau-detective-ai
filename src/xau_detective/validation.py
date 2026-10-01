"""Leakage-safe out-of-sample and walk-forward validation for research datasets.

This module evaluates already-built point-in-time-safe observations. It never
shuffles time-series rows and can purge training observations whose forward
outcome horizon would cross into the corresponding test window.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .pattern_study import PatternDatasetRow


@dataclass(frozen=True)
class ValidationMetrics:
    observations: int
    directional_wins: int
    directional_win_rate: Decimal
    expectancy: Decimal
    average_mfe: Decimal
    average_mae: Decimal


@dataclass(frozen=True)
class OutOfSampleResult:
    train: ValidationMetrics
    test: ValidationMetrics
    train_end_index: int
    test_start_index: int
    test_end_index: int


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_start_index: int
    train_end_index: int
    test_start_index: int
    test_end_index: int
    train: ValidationMetrics
    test: ValidationMetrics


def _metrics(
    rows: tuple[PatternDatasetRow, ...] | list[PatternDatasetRow],
) -> ValidationMetrics:
    if not rows:
        return ValidationMetrics(0, 0, Decimal(0), Decimal(0), Decimal(0), Decimal(0))

    wins = 0
    directional_values: list[Decimal] = []
    for row in rows:
        value = row.forward_return
        if row.direction == "BEARISH":
            value = -value
        directional_values.append(value)
        if value > 0:
            wins += 1

    count = Decimal(len(rows))
    return ValidationMetrics(
        observations=len(rows),
        directional_wins=wins,
        directional_win_rate=Decimal(wins) / count,
        expectancy=sum(directional_values, Decimal(0)) / count,
        average_mfe=sum((row.mfe for row in rows), Decimal(0)) / count,
        average_mae=sum((row.mae for row in rows), Decimal(0)) / count,
    )


def _ordered(rows: tuple[PatternDatasetRow, ...]) -> tuple[PatternDatasetRow, ...]:
    return tuple(
        sorted(rows, key=lambda r: (r.timestamp, r.timeframe, r.pattern, r.index, r.horizon))
    )


def _boundary_index(
    rows: tuple[PatternDatasetRow, ...],
    target: int,
) -> int:
    """Move a row-count target to the next complete source-candle boundary."""
    if target <= 0:
        return 0
    if target >= len(rows):
        return len(rows)

    boundary_timestamp = rows[target].timestamp
    boundary_timeframe = rows[target].timeframe
    boundary_source_index = rows[target].index

    while target > 0:
        previous = rows[target - 1]
        if (
            previous.timestamp != boundary_timestamp
            or previous.timeframe != boundary_timeframe
            or previous.index != boundary_source_index
        ):
            break
        target -= 1

    return target


def _purge_training_rows(
    rows: tuple[PatternDatasetRow, ...],
    *,
    test_start_source_index: int,
    purge_horizon: int,
) -> tuple[PatternDatasetRow, ...]:
    """Exclude training labels whose forward horizon reaches the test window."""
    if purge_horizon < 0:
        raise ValueError("purge_horizon must be non-negative")
    if purge_horizon == 0:
        return rows

    return tuple(
        row
        for row in rows
        if row.index + max(row.horizon, purge_horizon) < test_start_source_index
    )


def chronological_split(
    rows: tuple[PatternDatasetRow, ...],
    *,
    train_fraction: Decimal = Decimal("0.70"),
    purge_horizon: int = 0,
) -> tuple[tuple[PatternDatasetRow, ...], tuple[PatternDatasetRow, ...]]:
    """Split chronologically with an optional forward-label purge.

    purge_horizon is expressed in source bars and should be at least the
    largest label horizon when the dataset contains multiple horizons.
    """
    if not rows:
        return (), ()
    if not Decimal(0) < train_fraction < Decimal(1):
        raise ValueError("train_fraction must be between 0 and 1")
    if purge_horizon < 0:
        raise ValueError("purge_horizon must be non-negative")

    ordered = _ordered(rows)
    split = int(Decimal(len(ordered)) * train_fraction)
    split = max(1, min(split, len(ordered) - 1))
    split = _boundary_index(ordered, split)

    if split <= 0:
        raise ValueError("train/test split has no complete source-candle boundary")

    train = ordered[:split]
    test = ordered[split:]
    train = _purge_training_rows(
        train,
        test_start_source_index=test[0].index,
        purge_horizon=purge_horizon,
    )
    if not train:
        raise ValueError("purging removed all training observations")
    return train, test


def evaluate_out_of_sample(
    rows: tuple[PatternDatasetRow, ...],
    *,
    train_fraction: Decimal = Decimal("0.70"),
    purge_horizon: int = 0,
) -> OutOfSampleResult:
    """Evaluate a fixed research set with a chronological train/test split."""
    train, test = chronological_split(
        rows,
        train_fraction=train_fraction,
        purge_horizon=purge_horizon,
    )
    ordered = _ordered(rows)
    test_start = next(
        index for index, row in enumerate(ordered) if row == test[0]
    )
    test_end = len(ordered) - 1
    train_end = test_start - 1
    return OutOfSampleResult(
        train=_metrics(train),
        test=_metrics(test),
        train_end_index=train_end,
        test_start_index=test_start,
        test_end_index=test_end,
    )


def walk_forward(
    rows: tuple[PatternDatasetRow, ...],
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    min_train_observations: int = 1,
    purge_horizon: int = 0,
) -> tuple[WalkForwardFold, ...]:
    """Run rolling chronological train/test folds with optional label purging.

    No observation from a fold's test window is available to that fold's
    training labels. The function intentionally does not optimize parameters;
    it only measures stability across time.
    """
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    if min_train_observations <= 0:
        raise ValueError("min_train_observations must be positive")
    if purge_horizon < 0:
        raise ValueError("purge_horizon must be non-negative")

    step = test_size if step_size is None else step_size
    if step <= 0:
        raise ValueError("step_size must be positive")

    ordered = _ordered(rows)
    folds: list[WalkForwardFold] = []
    start = 0
    fold_number = 1

    while start + train_size + test_size <= len(ordered):
        test_start = _boundary_index(ordered, start + train_size)
        if test_start <= start or test_start >= len(ordered):
            break

        test_end = min(test_start + test_size, len(ordered))
        train = ordered[start:test_start]
        test = ordered[test_start:test_end]
        if not test:
            break

        if folds and test_start <= folds[-1].test_end_index:
            start += step
            continue

        train = _purge_training_rows(
            train,
            test_start_source_index=test[0].index,
            purge_horizon=purge_horizon,
        )
        if len(train) >= min_train_observations:
            folds.append(
                WalkForwardFold(
                    fold=fold_number,
                    train_start_index=start,
                    train_end_index=test_start - 1,
                    test_start_index=test_start,
                    test_end_index=test_end - 1,
                    train=_metrics(train),
                    test=_metrics(test),
                )
            )
            fold_number += 1

        start += step

    return tuple(folds)


def aggregate_test_metrics(folds: tuple[WalkForwardFold, ...]) -> ValidationMetrics:
    """Aggregate test observations across folds without double-counting rows.

    Intended for non-overlapping test windows. Raises if test windows overlap.
    """
    if not folds:
        return _metrics(())
    for previous, current in zip(folds, folds[1:]):
        if current.test_start_index <= previous.test_end_index:
            raise ValueError("aggregate_test_metrics requires non-overlapping test windows")

    total = sum(fold.test.observations for fold in folds)
    if total == 0:
        return _metrics(())

    wins = sum(fold.test.directional_wins for fold in folds)
    expectancy = sum(
        (
            fold.test.expectancy * Decimal(fold.test.observations)
            for fold in folds
        ),
        Decimal(0),
    ) / Decimal(total)
    mfe = sum(
        (
            fold.test.average_mfe * Decimal(fold.test.observations)
            for fold in folds
        ),
        Decimal(0),
    ) / Decimal(total)
    mae = sum(
        (
            fold.test.average_mae * Decimal(fold.test.observations)
            for fold in folds
        ),
        Decimal(0),
    ) / Decimal(total)
    return ValidationMetrics(
        total,
        wins,
        Decimal(wins) / Decimal(total),
        expectancy,
        mfe,
        mae,
    )
