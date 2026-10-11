"""Data-quality gates before market features are trusted."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Callable

from .market import Candle
from .timeframes import Timeframe


@dataclass(frozen=True)
class DataQuality:
    usable: bool
    reasons: tuple[str, ...]


def validate_candles(
    candles: tuple[Candle, ...],
    expected_interval: timedelta | None = None,
    gap_is_expected: Callable[[object, object], bool] | None = None,
    *,
    timeframe: Timeframe | None = None,
    gap_is_expected_for_timeframe: Callable[[object, object, Timeframe], bool] | None = None,
) -> DataQuality:
    if not candles:
        return DataQuality(False, ("NO_CANDLES",))
    reasons: list[str] = []
    for candle in candles:
        if not isinstance(candle.timestamp, datetime):
            return DataQuality(False, ("INVALID_TIMESTAMP",))
        if candle.timestamp.tzinfo is None or candle.timestamp.utcoffset() is None:
            return DataQuality(False, ("NAIVE_TIMESTAMP",))
    for previous, current in pairwise(candles):
        if current.timestamp <= previous.timestamp:
            reasons.append("NON_MONOTONIC_TIMESTAMPS")
            break
        if expected_interval is not None and current.timestamp - previous.timestamp > expected_interval * 2:
            expected = False
            if gap_is_expected_for_timeframe is not None and timeframe is not None:
                expected = gap_is_expected_for_timeframe(
                    previous.timestamp, current.timestamp, timeframe
                )
            elif gap_is_expected is not None:
                expected = gap_is_expected(previous.timestamp, current.timestamp)
            if not expected:
                reasons.append("DATA_GAP")
                break
    for candle in candles:
        prices = (candle.open, candle.high, candle.low, candle.close)
        try:
            finite_prices = tuple(Decimal(str(price)) for price in prices)
            finite_volume = Decimal(str(candle.volume))
        except (InvalidOperation, TypeError, ValueError):
            reasons.append("INVALID_NUMERIC_VALUE")
            break
        if any(not price.is_finite() for price in finite_prices):
            reasons.append("NON_FINITE_PRICE")
            break
        if not finite_volume.is_finite():
            reasons.append("NON_FINITE_VOLUME")
            break
        if any(price <= 0 for price in finite_prices):
            reasons.append("NON_POSITIVE_PRICE")
            break
        if finite_volume < 0:
            reasons.append("NEGATIVE_VOLUME")
            break
        if finite_prices[1] < max(finite_prices[0], finite_prices[3]) or finite_prices[2] > min(finite_prices[0], finite_prices[3]):
            reasons.append("INVALID_OHLC")
            break
        if finite_prices[2] > finite_prices[1]:
            reasons.append("INVALID_RANGE")
            break
        if finite_prices[1] == finite_prices[2]:
            reasons.append("ZERO_RANGE_CANDLE")
            break
    return DataQuality(not reasons, tuple(reasons))
