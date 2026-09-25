"""Data-quality gates before market features are trusted."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .market import Candle


@dataclass(frozen=True)
class DataQuality:
    usable: bool
    reasons: tuple[str, ...]


def validate_candles(candles: tuple[Candle, ...], expected_interval: timedelta | None = None) -> DataQuality:
    if not candles:
        return DataQuality(False, ("NO_CANDLES",))
    reasons: list[str] = []
    for previous, current in zip(candles, candles[1:]):
        if current.timestamp <= previous.timestamp:
            reasons.append("NON_MONOTONIC_TIMESTAMPS")
            break
        if expected_interval is not None and current.timestamp - previous.timestamp > expected_interval * 2:
            reasons.append("DATA_GAP")
            break
    for candle in candles:
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            reasons.append("INVALID_OHLC")
            break
        if candle.low > candle.high:
            reasons.append("INVALID_RANGE")
            break
    return DataQuality(not reasons, tuple(reasons))
