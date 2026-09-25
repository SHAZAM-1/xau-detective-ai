"""Market-data ingestion orchestration independent of any broker SDK."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from .data_quality import DataQuality, validate_candles
from .market import Candle
from .timeframes import Timeframe


class CandleSource(Protocol):
    def fetch(self, symbol: str, timeframe: Timeframe, count: int) -> tuple[Candle, ...]:
        ...


_INTERVALS = {
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),
}


@dataclass(frozen=True)
class TimeframeSnapshot:
    timeframe: Timeframe
    candles: tuple[Candle, ...]
    quality: DataQuality


def keep_closed_candles(
    candles: tuple[Candle, ...],
    *,
    now,
    timeframe: Timeframe,
) -> tuple[Candle, ...]:
    """Drop the currently forming candle when it overlaps the current period."""
    interval = _INTERVALS[timeframe]
    if not candles:
        return ()
    closed: list[Candle] = []
    for candle in candles:
        if candle.timestamp + interval <= now:
            closed.append(candle)
    return tuple(closed)


def load_timeframe(
    source: CandleSource,
    symbol: str,
    timeframe: Timeframe,
    count: int,
    *,
    now,
) -> TimeframeSnapshot:
    raw = source.fetch(symbol, timeframe, count)
    closed = keep_closed_candles(raw, now=now, timeframe=timeframe)
    quality = validate_candles(closed, _INTERVALS[timeframe])
    return TimeframeSnapshot(timeframe, closed, quality)


def load_multi_timeframe(
    source: CandleSource,
    symbol: str,
    timeframes: tuple[Timeframe, ...],
    count: int,
    *,
    now,
) -> tuple[TimeframeSnapshot, ...]:
    return tuple(
        load_timeframe(source, symbol, timeframe, count, now=now)
        for timeframe in timeframes
    )
