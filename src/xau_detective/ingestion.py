"""Market-data ingestion orchestration independent of any broker SDK."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from .data_quality import DataQuality, validate_candles
from .market import Candle
from .timeframes import Timeframe, expected_interval


class CandleSource(Protocol):
    def fetch(self, symbol: str, timeframe: Timeframe, count: int) -> tuple[Candle, ...]:
        ...


def keep_closed_candles(candles: tuple[Candle, ...], *, now, timeframe: Timeframe) -> tuple[Candle, ...]:
    interval = expected_interval(timeframe)
    return tuple(candle for candle in candles if candle.timestamp + interval <= now)


@dataclass(frozen=True)
class TimeframeSnapshot:
    timeframe: Timeframe
    candles: tuple[Candle, ...]
    quality: DataQuality


def load_timeframe(
    source: CandleSource,
    symbol: str,
    timeframe: Timeframe,
    count: int,
    *,
    now,
    max_staleness: timedelta | None = None,
) -> TimeframeSnapshot:
    raw = source.fetch(symbol, timeframe, count)
    closed = keep_closed_candles(raw, now=now, timeframe=timeframe)
    quality = validate_candles(closed, expected_interval(timeframe))
    if quality.usable and max_staleness is not None and closed:
        if now - closed[-1].timestamp > max_staleness:
            quality = DataQuality(False, (*quality.reasons, "STALE_DATA"))
    return TimeframeSnapshot(timeframe, closed, quality)


def load_multi_timeframe(
    source: CandleSource,
    symbol: str,
    timeframes: tuple[Timeframe, ...],
    count: int,
    *,
    now,
    max_staleness: timedelta | None = None,
) -> tuple[TimeframeSnapshot, ...]:
    return tuple(
        load_timeframe(
            source,
            symbol,
            timeframe,
            count,
            now=now,
            max_staleness=max_staleness,
        )
        for timeframe in timeframes
    )
