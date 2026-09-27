"""Context-stratified candlestick research for XAUUSD.

All context labels are computed from candles available at the pattern timestamp.
This module is research-only and does not generate trade decisions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .candlestick import detect_candlestick_patterns
from .market import Candle
from .regime import TrendState, VolatilityState, classify_regime
from .session import classify_session


@dataclass(frozen=True)
class ContextPatternObservation:
    timeframe: str
    pattern: str
    timestamp: object
    trend: str
    volatility: str
    session: str
    direction: str
    horizon: int
    forward_return: Decimal


@dataclass(frozen=True)
class ContextPatternStudyResult:
    timeframe: str
    pattern: str
    trend: str
    volatility: str
    session: str
    direction: str
    horizon: int
    observations: int
    directional_wins: int
    directional_win_rate: Decimal
    average_return: Decimal
    expectancy: Decimal


def _directional_return(direction: str, value: Decimal) -> Decimal:
    if direction == "BEARISH":
        return -value
    return value


def build_context_dataset(
    candles_by_timeframe: dict[str, tuple[Candle, ...]],
    *,
    horizons: tuple[int, ...] = (1, 3, 5),
) -> tuple[ContextPatternObservation, ...]:
    """Create point-in-time-safe pattern/context/outcome observations."""
    if not horizons or any(h <= 0 for h in horizons):
        raise ValueError("horizons must contain only positive values")

    rows: list[ContextPatternObservation] = []

    for timeframe, candles in sorted(candles_by_timeframe.items()):
        for pattern in detect_candlestick_patterns(candles):
            index = pattern.index
            # Context is calculated using data through the pattern candle only.
            prefix = candles[: index + 1]
            if not prefix:
                continue
            regime = classify_regime(prefix)
            session = classify_session(candles[index].timestamp).label

            for horizon in horizons:
                end = index + horizon
                if end >= len(candles):
                    continue
                entry = candles[index].close
                if entry <= 0:
                    continue
                future_close = candles[end].close
                forward_return = (future_close - entry) / entry
                rows.append(
                    ContextPatternObservation(
                        timeframe=timeframe,
                        pattern=pattern.name,
                        timestamp=candles[index].timestamp,
                        trend=regime.trend.value,
                        volatility=regime.volatility.value,
                        session=session,
                        direction=pattern.direction,
                        horizon=horizon,
                        forward_return=forward_return,
                    )
                )
    return tuple(rows)


def study_pattern_context(
    candles_by_timeframe: dict[str, tuple[Candle, ...]],
    *,
    horizons: tuple[int, ...] = (1, 3, 5),
) -> tuple[ContextPatternStudyResult, ...]:
    """Aggregate pattern edge by timeframe, regime, session and direction."""
    rows = build_context_dataset(candles_by_timeframe, horizons=horizons)
    grouped: dict[tuple[str, str, str, str, str, str, int], list[Decimal]] = defaultdict(list)

    for row in rows:
        key = (
            row.timeframe,
            row.pattern,
            row.trend,
            row.volatility,
            row.session,
            row.direction,
            row.horizon,
        )
        grouped[key].append(row.forward_return)

    results: list[ContextPatternStudyResult] = []
    for key, returns in sorted(grouped.items()):
        timeframe, pattern, trend, volatility, session, direction, horizon = key
        directional = [_directional_return(direction, value) for value in returns]
        wins = sum(value > 0 for value in directional)
        count = len(directional)
        results.append(
            ContextPatternStudyResult(
                timeframe=timeframe,
                pattern=pattern,
                trend=trend,
                volatility=volatility,
                session=session,
                direction=direction,
                horizon=horizon,
                observations=count,
                directional_wins=wins,
                directional_win_rate=Decimal(wins) / Decimal(count),
                average_return=sum(returns, Decimal(0)) / Decimal(count),
                expectancy=sum(directional, Decimal(0)) / Decimal(count),
            )
        )
    return tuple(results)
