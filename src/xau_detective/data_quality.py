"""Data-quality gates before market features are trusted."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
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
        if any(price <= 0 for price in (candle.open, candle.high, candle.low, candle.close)):
            reasons.append("NON_POSITIVE_PRICE")
            break
        if candle.volume < 0:
            reasons.append("NEGATIVE_VOLUME")
            break
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            reasons.append("INVALID_OHLC")
            break
        if candle.low > candle.high:
            reasons.append("INVALID_RANGE")
            break
        if candle.high == candle.low:
            reasons.append("ZERO_RANGE_CANDLE")
            break
    return DataQuality(not reasons, tuple(reasons))
