"""Historical candlestick-pattern study tools for XAUUSD research.

This module is deliberately descriptive: it measures what happened after a
pattern and never turns a pattern into a trade signal by itself.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from .candlestick import CandlePattern, detect_candlestick_patterns
from .market import Candle


@dataclass(frozen=True)
class PatternObservation:
    pattern: str
    index: int
    direction: str
    confidence: Decimal
    forward_returns: tuple[Decimal, ...]
    mfe: Decimal
    mae: Decimal


@dataclass(frozen=True)
class PatternStudyResult:
    pattern: str
    observations: int
    bullish_follow_through: int
    bearish_follow_through: int
    neutral: int
    average_forward_return: Decimal
    median_forward_return: Decimal
    directional_win_rate: Decimal
    expectancy: Decimal
    average_mfe: Decimal
    average_mae: Decimal
    sample_horizon: int


def _zero() -> Decimal:
    return Decimal("0")


def _forward_return(entry: Decimal, exit_price: Decimal) -> Decimal:
    if entry <= 0:
        raise ValueError("entry price must be positive")
    return (exit_price - entry) / entry


def _observation(
    pattern: CandlePattern,
    candles: tuple[Candle, ...],
    horizon: int,
) -> PatternObservation | None:
    end = pattern.index + horizon
    if end >= len(candles):
        return None

    entry = candles[pattern.index].close
    if entry <= 0:
        return None

    future = candles[pattern.index + 1 : end + 1]
    returns = tuple(_forward_return(entry, candle.close) for candle in future)
    if not returns:
        return None

    if pattern.direction == "BULLISH":
        mfe = max(_forward_return(entry, candle.high) for candle in future)
        mae = max(_zero(), max((_forward_return(entry, candle.low) * Decimal("-1") for candle in future), default=_zero()))
        expectancy = returns[-1]
    elif pattern.direction == "BEARISH":
        mfe = max((entry - candle.low) / entry for candle in future)
        mae = max(_zero(), max(((candle.high - entry) / entry for candle in future), default=_zero()))
        expectancy = -returns[-1]
    else:
        mfe = max((_forward_return(entry, candle.high) for candle in future), default=_zero())
        mae = max(_zero(), max((_forward_return(entry, candle.low) * Decimal("-1") for candle in future), default=_zero()))
        expectancy = returns[-1]

    return PatternObservation(
        pattern.name,
        pattern.index,
        pattern.direction,
        pattern.confidence,
        returns,
        mfe,
        mae,
    )


def study_patterns(
    candles: tuple[Candle, ...],
    *,
    horizon: int = 5,
) -> tuple[PatternStudyResult, ...]:
    """Measure every detected pattern with a fixed forward horizon.

    The function uses only candles after the pattern candle for outcomes, so it
    is safe to use as a research primitive without look-ahead in the detection
    step. The final incomplete horizon is excluded from the sample.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")

    patterns = detect_candlestick_patterns(candles)
    observations: dict[str, list[PatternObservation]] = defaultdict(list)

    for pattern in patterns:
        item = _observation(pattern, candles, horizon)
        if item is not None:
            observations[pattern.name].append(item)

    results: list[PatternStudyResult] = []
    for name, items in sorted(observations.items()):
        if not items:
            continue
        returns = [item.forward_returns[-1] for item in items]
        bullish = sum(item.forward_returns[-1] > 0 for item in items)
        bearish = sum(item.forward_returns[-1] < 0 for item in items)
        neutral = len(items) - bullish - bearish
        directional_wins = sum(
            (item.forward_returns[-1] > 0 if item.direction == "BULLISH" else
             item.forward_returns[-1] < 0 if item.direction == "BEARISH" else
             item.forward_returns[-1] > 0)
            for item in items
        )
        directional_win_rate = Decimal(directional_wins) / Decimal(len(items))

        directional_values: list[Decimal] = []
        for item in items:
            value = item.forward_returns[-1]
            if item.direction == "BEARISH":
                value = -value
            directional_values.append(value)

        results.append(
            PatternStudyResult(
                pattern=name,
                observations=len(items),
                bullish_follow_through=bullish,
                bearish_follow_through=bearish,
                neutral=neutral,
                average_forward_return=sum(returns, _zero()) / Decimal(len(returns)),
                median_forward_return=median(returns),
                directional_win_rate=directional_win_rate,
                expectancy=sum(directional_values, _zero()) / Decimal(len(directional_values)),
                average_mfe=sum((item.mfe for item in items), _zero()) / Decimal(len(items)),
                average_mae=sum((item.mae for item in items), _zero()) / Decimal(len(items)),
                sample_horizon=horizon,
            )
        )

    return tuple(results)

@dataclass(frozen=True)
class PatternDatasetRow:
    timeframe: str
    pattern: str
    timestamp: object
    index: int
    direction: str
    confidence: Decimal
    horizon: int
    forward_return: Decimal
    mfe: Decimal
    mae: Decimal


def build_pattern_dataset(
    candles_by_timeframe: dict[str, tuple[Candle, ...]],
    *,
    horizons: tuple[int, ...] = (1, 3, 5),
) -> tuple[PatternDatasetRow, ...]:
    """Build point-in-time-safe pattern/outcome rows for offline research.

    Rows are emitted only when the complete forward horizon exists. The builder
    never uses future candles to decide whether a pattern exists.
    """
    if not horizons or any(horizon <= 0 for horizon in horizons):
        raise ValueError("horizons must contain only positive values")

    rows: list[PatternDatasetRow] = []
    for timeframe, candles in sorted(candles_by_timeframe.items()):
        patterns = detect_candlestick_patterns(candles)
        for pattern in patterns:
            for horizon in horizons:
                item = _observation(pattern, candles, horizon)
                if item is None:
                    continue
                rows.append(
                    PatternDatasetRow(
                        timeframe=timeframe,
                        pattern=pattern.name,
                        timestamp=candles[pattern.index].timestamp,
                        index=pattern.index,
                        direction=pattern.direction,
                        confidence=pattern.confidence,
                        horizon=horizon,
                        forward_return=item.forward_returns[-1],
                        mfe=item.mfe,
                        mae=item.mae,
                    )
                )
    return tuple(rows)
