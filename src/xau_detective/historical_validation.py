"""Historical research validation orchestration.

This module wires together an already validated historical CSV, the
point-in-time-safe pattern dataset builder, and chronological OOS/walk-forward
descriptive metrics. It does not create trading signals or alter policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .historical_data import HistoricalDataset, load_historical_csv
from .pattern_study import PatternDatasetRow, build_pattern_dataset
from .timeframes import Timeframe
from .validation import (
    OutOfSampleResult,
    ValidationMetrics,
    WalkForwardFold,
    aggregate_test_metrics,
    evaluate_out_of_sample,
    walk_forward,
)


@dataclass(frozen=True)
class HistoricalValidationConfig:
    train_fraction: Decimal = Decimal("0.70")
    walk_forward_train_size: int = 100
    walk_forward_test_size: int = 25
    walk_forward_step_size: int = 25
    horizons: tuple[int, ...] = (1, 3, 5)


@dataclass(frozen=True)
class HistoricalValidationReport:
    dataset: HistoricalDataset
    pattern_rows: tuple[PatternDatasetRow, ...]
    out_of_sample: OutOfSampleResult
    walk_forward_folds: tuple[WalkForwardFold, ...]
    walk_forward_test: ValidationMetrics


def validate_historical_csv(
    path: str | Path,
    *,
    symbol: str,
    timeframe: Timeframe,
    source: str,
    config: HistoricalValidationConfig = HistoricalValidationConfig(),
    strict_interval: bool = True,
) -> HistoricalValidationReport:
    """Run descriptive historical validation only when source quality is usable."""
    if not config.horizons or any(horizon <= 0 for horizon in config.horizons):
        raise ValueError("horizons must contain only positive values")
    if config.walk_forward_train_size <= 0 or config.walk_forward_test_size <= 0:
        raise ValueError("walk-forward train/test sizes must be positive")
    if config.walk_forward_step_size <= 0:
        raise ValueError("walk-forward step size must be positive")

    dataset = load_historical_csv(
        path,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        strict_interval=strict_interval,
    )
    if not dataset.quality.usable:
        reasons = ", ".join(dataset.quality.reasons)
        raise ValueError(f"historical dataset is not usable: {reasons}")

    pattern_rows = build_pattern_dataset(
        {timeframe.value: dataset.candles},
        horizons=config.horizons,
    )
    if len(pattern_rows) < 2:
        raise ValueError("historical dataset produced fewer than two research observations")

    purge_horizon = max(config.horizons)
    out_of_sample = evaluate_out_of_sample(
        pattern_rows,
        train_fraction=config.train_fraction,
        purge_horizon=purge_horizon,
    )
    folds = walk_forward(
        pattern_rows,
        train_size=config.walk_forward_train_size,
        test_size=config.walk_forward_test_size,
        step_size=config.walk_forward_step_size,
        purge_horizon=purge_horizon,
    )
    walk_forward_test = (
        aggregate_test_metrics(folds)
        if folds
        else ValidationMetrics(0, 0, Decimal(0), Decimal(0), Decimal(0), Decimal(0))
    )
    return HistoricalValidationReport(
        dataset=dataset,
        pattern_rows=pattern_rows,
        out_of_sample=out_of_sample,
        walk_forward_folds=folds,
        walk_forward_test=walk_forward_test,
    )
