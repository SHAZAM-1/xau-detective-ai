"""Market-data ingestion orchestration independent of any broker SDK."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .data_quality import DataQuality, validate_candles
from .market import Candle
from .timeframes import Timeframe, expected_interval


class CandleSource(Protocol):
    def fetch(self, symbol: str, timeframe: Timeframe, count: int) -> tuple[Candle, ...]:
        ...


def keep_closed_candles(candles: tuple[Candle, ...], *, now, timeframe: Timeframe) -> tuple[Candle, ...]:
    interval = expected_interval(timeframe)
    if not candles:
        return ()
    return tuple(candle for candle in candles if candle.timestamp + interval <= now)


@dataclass(frozen=True)
class TimeframeSnapshot:
    timeframe: Timeframe
    candles: tuple[Candle, ...]
    quality: DataQuality


def load_timeframe(source: CandleSource, symbol: str, timeframe: Timeframe, count: int, *, now) -> TimeframeSnapshot:
    raw = source.fetch(symbol, timeframe, count)
    closed = keep_closed_candles(raw, now=now, timeframe=timeframe)
    quality = validate_candles(closed, expected_interval(timeframe))
    return TimeframeSnapshot(timeframe, closed, quality)


def load_multi_timeframe(source: CandleSource, symbol: str, timeframes: tuple[Timeframe, ...], count: int, *, now) -> tuple[TimeframeSnapshot, ...]:
    return tuple(load_timeframe(source, symbol, timeframe, count, now=now) for timeframe in timeframes)
