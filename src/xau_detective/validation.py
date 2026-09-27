"""Leakage-safe out-of-sample and walk-forward validation for research datasets.

This module evaluates already-built point-in-time-safe observations. It never
selects patterns using the test period and never shuffles time-series rows.
Results are descriptive validation statistics, not trade signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import mean

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


def _metrics(rows: tuple[PatternDatasetRow, ...] | list[PatternDatasetRow]) -> ValidationMetrics:
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


def _ordered(rows: tuple[PatternDatasetRow, ...], *, group_by_horizon: bool) -> tuple[PatternDatasetRow, ...]:
    if group_by_horizon:
        return tuple(sorted(rows, key=lambda r: (r.timestamp, r.horizon, r.timeframe, r.pattern, r.index)))
    return tuple(sorted(rows, key=lambda r: (r.timestamp, r.timeframe, r.pattern, r.index)))


def chronological_split(
    rows: tuple[PatternDatasetRow, ...],
    *,
    train_fraction: Decimal = Decimal("0.70"),
) -> tuple[tuple[PatternDatasetRow, ...], tuple[PatternDatasetRow, ...]]:
    """Split chronologically; the boundary is never shuffled."""
    if not rows:
        return (), ()
    if not Decimal(0) < train_fraction < Decimal(1):
        raise ValueError("train_fraction must be between 0 and 1")

    ordered = _ordered(rows, group_by_horizon=False)
    split = int(Decimal(len(ordered)) * train_fraction)
    split = max(1, min(split, len(ordered) - 1))
    return ordered[:split], ordered[split:]


def evaluate_out_of_sample(
    rows: tuple[PatternDatasetRow, ...],
    *,
    train_fraction: Decimal = Decimal("0.70"),
) -> OutOfSampleResult:
    """Evaluate a fixed research set with a chronological train/test split."""
    train, test = chronological_split(rows, train_fraction=train_fraction)
    ordered = train + test
    return OutOfSampleResult(
        train=_metrics(train),
        test=_metrics(test),
        train_end_index=len(train) - 1,
        test_start_index=len(train),
        test_end_index=len(ordered) - 1,
    )


def walk_forward(
    rows: tuple[PatternDatasetRow, ...],
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    min_train_observations: int = 1,
) -> tuple[WalkForwardFold, ...]:
    """Run rolling chronological train/test folds.

    No observation from a fold's test window is available to that fold's
    training window. The function intentionally does not optimize parameters;
    it only measures stability across time.
    """
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    if min_train_observations <= 0:
        raise ValueError("min_train_observations must be positive")
    step = test_size if step_size is None else step_size
    if step <= 0:
        raise ValueError("step_size must be positive")

    ordered = _ordered(rows, group_by_horizon=False)
    folds: list[WalkForwardFold] = []
    start = 0
    fold_number = 1

    while start + train_size + test_size <= len(ordered):
        train = ordered[start : start + train_size]
        test_start = start + train_size
        test = ordered[test_start : test_start + test_size]
        if len(train) >= min_train_observations:
            folds.append(
                WalkForwardFold(
                    fold=fold_number,
                    train_start_index=start,
                    train_end_index=test_start - 1,
                    test_start_index=test_start,
                    test_end_index=test_start + test_size - 1,
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

    # The caller's folds do not expose original rows, so aggregate weighted
    # metrics from fold summaries. MFE/MAE and expectancy are observation-weighted.
    total = sum(fold.test.observations for fold in folds)
    if total == 0:
        return _metrics(())

    wins = sum(fold.test.directional_wins for fold in folds)
    expectancy = sum(
        (fold.test.expectancy * Decimal(fold.test.observations) for fold in folds),
        Decimal(0),
    ) / Decimal(total)
    mfe = sum(
        (fold.test.average_mfe * Decimal(fold.test.observations) for fold in folds),
        Decimal(0),
    ) / Decimal(total)
    mae = sum(
        (fold.test.average_mae * Decimal(fold.test.observations) for fold in folds),
        Decimal(0),
    ) / Decimal(total)
    return ValidationMetrics(total, wins, Decimal(wins) / Decimal(total), expectancy, mfe, mae)
