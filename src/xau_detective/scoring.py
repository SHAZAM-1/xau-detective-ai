"""Leakage-safe baseline statistical scoring for XAUUSD research.

This module is deliberately conservative:
- training statistics are fit only on supplied historical rows;
- no future/test rows are used for fitting;
- score is setup quality, never win probability;
- low-sample contexts remain eligible for NO_TRADE upstream.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .pattern_study import PatternDatasetRow


@dataclass(frozen=True)
class ScoreBucket:
    key: tuple[str, str, str, int]
    observations: int
    wins: int
    smoothed_rate: Decimal
    expectancy: Decimal


@dataclass(frozen=True)
class CalibratedScore:
    score: int
    historical_edge: Decimal
    sample_size: int
    bucket: tuple[str, str, str, int]
    reason: str


@dataclass(frozen=True)
class BaselineScoringConfig:
    min_observations: int = 30
    prior_strength: Decimal = Decimal("20")
    min_score: int = 0
    max_score: int = 100
    neutral_score: int = 50

    def __post_init__(self) -> None:
        if self.min_observations <= 0:
            raise ValueError("min_observations must be positive")
        if self.prior_strength <= 0:
            raise ValueError("prior_strength must be positive")
        if self.min_score < 0 or self.max_score > 100 or self.min_score >= self.max_score:
            raise ValueError("score bounds must satisfy 0 <= min_score < max_score <= 100")


def _directional_value(row: PatternDatasetRow) -> Decimal:
    value = row.forward_return
    return -value if row.direction == "BEARISH" else value


def _bucket_key(row: PatternDatasetRow) -> tuple[str, str, str, int]:
    return (row.timeframe, row.pattern, row.direction, row.horizon)


def fit_baseline(rows: tuple[PatternDatasetRow, ...], config: BaselineScoringConfig = BaselineScoringConfig()) -> tuple[ScoreBucket, ...]:
    """Fit smoothed directional outcome statistics using training rows only."""
    if not rows:
        return ()

    groups: dict[tuple[str, str, str, int], list[PatternDatasetRow]] = defaultdict(list)
    for row in rows:
        groups[_bucket_key(row)].append(row)

    wins = sum(_directional_value(row) > 0 for row in rows)
    base_rate = Decimal(wins) / Decimal(len(rows))

    buckets: list[ScoreBucket] = []
    for key, items in sorted(groups.items()):
        count = len(items)
        bucket_wins = sum(_directional_value(row) > 0 for row in items)
        raw_rate = Decimal(bucket_wins) / Decimal(count)
        smoothed = (Decimal(count) * raw_rate + config.prior_strength * base_rate) / (Decimal(count) + config.prior_strength)
        expectancy = sum((_directional_value(row) for row in items), Decimal(0)) / Decimal(count)
        buckets.append(ScoreBucket(key, count, bucket_wins, smoothed, expectancy))

    return tuple(buckets)


def score_row(row: PatternDatasetRow, buckets: tuple[ScoreBucket, ...], *, config: BaselineScoringConfig = BaselineScoringConfig()) -> CalibratedScore:
    """Score one row using a model fitted independently from that row.

    Callers must ensure buckets were fitted on a training window that does not
    contain the scored row or its future outcome.
    """
    key = _bucket_key(row)
    bucket = next((item for item in buckets if item.key == key), None)
    if bucket is None:
        return CalibratedScore(config.neutral_score, Decimal(0), 0, key, "UNSEEN_CONTEXT")
    if bucket.observations < config.min_observations:
        return CalibratedScore(config.neutral_score, bucket.expectancy, bucket.observations, key, "INSUFFICIENT_SAMPLE")
    score = int(round(float(bucket.smoothed_rate * Decimal(100))))
    score = max(config.min_score, min(config.max_score, score))
    return CalibratedScore(score, bucket.expectancy, bucket.observations, key, "CALIBRATED_BASELINE")


def score_rows_oos(train_rows: tuple[PatternDatasetRow, ...], test_rows: tuple[PatternDatasetRow, ...], *, config: BaselineScoringConfig = BaselineScoringConfig()) -> tuple[CalibratedScore, ...]:
    """Fit only on train_rows, then score test_rows."""
    buckets = fit_baseline(train_rows, config)
    return tuple(score_row(row, buckets, config=config) for row in test_rows)
