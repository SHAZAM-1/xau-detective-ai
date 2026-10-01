"""Deterministic, research-only mean-reversion analysis.

This module identifies statistically stretched closes and re-entry toward a
rolling mean. It is deliberately independent of execution and risk policy.
Signals are descriptive research evidence and must be validated historically
before being used by a decision policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext

from .market import Candle

getcontext().prec = 28


@dataclass(frozen=True)
class MeanReversionSignal:
    direction: str
    z_score: Decimal
    mean: Decimal
    band_distance: Decimal
    evidence: tuple[str, ...]


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def _stddev(values: tuple[Decimal, ...], mean: Decimal) -> Decimal:
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
    return variance.sqrt()


def analyze_mean_reversion(
    candles: tuple[Candle, ...],
    *,
    lookback: int = 20,
    band_stddevs: Decimal = Decimal("2"),
) -> MeanReversionSignal | None:
    """Detect a closed-candle stretch followed by re-entry toward the mean."""
    if lookback < 3 or band_stddevs <= 0 or len(candles) < lookback + 1:
        return None

    window = tuple(c.close for c in candles[-lookback - 1:-1])
    current = candles[-1].close
    previous = candles[-2].close
    mean = _mean(window)
    stddev = _stddev(window, mean)
    if stddev <= 0:
        return None

    upper = mean + band_stddevs * stddev
    lower = mean - band_stddevs * stddev

    if previous >= lower and current < lower:
        z_score = (current - mean) / stddev
        return MeanReversionSignal(
            "BUY",
            z_score,
            mean,
            lower - current,
            ("CLOSE_REENTERED_BELOW_LOWER_BAND", "MEAN_REVERSION_STRETCH"),
        )
    if previous <= upper and current > upper:
        z_score = (current - mean) / stddev
        return MeanReversionSignal(
            "SELL",
            z_score,
            mean,
            current - upper,
            ("CLOSE_REENTERED_ABOVE_UPPER_BAND", "MEAN_REVERSION_STRETCH"),
        )
    return None
