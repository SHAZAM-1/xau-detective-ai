"""Research-only comparison of deterministic market-analysis method families.

This module classifies observable evidence. It does not create orders, size
positions, alter risk policy, or override the project's decision gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .market import Candle


@dataclass(frozen=True)
class MethodSignal:
    method: str
    direction: str
    strength: Decimal
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class MethodAnalysis:
    signals: tuple[MethodSignal, ...]
    contradictions: tuple[str, ...]


def analyze_methods(candles: tuple[Candle, ...], *, lookback: int = 20) -> MethodAnalysis:
    if len(candles) < max(lookback + 1, 3):
        return MethodAnalysis((), ("INSUFFICIENT_DATA",))

    previous = candles[-lookback - 1:-1]
    current = candles[-1]
    high = max(c.high for c in previous)
    low = min(c.low for c in previous)
    midpoint = (high + low) / Decimal(2)

    signals: list[MethodSignal] = []

    if current.close > high:
        signals.append(MethodSignal("BREAKOUT", "BUY", Decimal(1), ("CLOSE_ABOVE_LOOKBACK_HIGH",)))
    elif current.close < low:
        signals.append(MethodSignal("BREAKOUT", "SELL", Decimal(1), ("CLOSE_BELOW_LOOKBACK_LOW",)))

    if current.close > midpoint:
        signals.append(MethodSignal("MEAN_REVERSION_CONTEXT", "SELL", Decimal(1), ("PRICE_ABOVE_RANGE_MIDPOINT",)))
    elif current.close < midpoint:
        signals.append(MethodSignal("MEAN_REVERSION_CONTEXT", "BUY", Decimal(1), ("PRICE_BELOW_RANGE_MIDPOINT",)))

    if current.close > previous[-1].close:
        signals.append(MethodSignal("MOMENTUM", "BUY", Decimal(1), ("CLOSE_RISING",)))
    elif current.close < previous[-1].close:
        signals.append(MethodSignal("MOMENTUM", "SELL", Decimal(1), ("CLOSE_FALLING",)))

    if current.high > high and current.close < high:
        signals.append(MethodSignal("LIQUIDITY_SWEEP", "SELL", Decimal(1), ("HIGH_SWEPT_AND_CLOSE_RETURNED",)))
    if current.low < low and current.close > low:
        signals.append(MethodSignal("LIQUIDITY_SWEEP", "BUY", Decimal(1), ("LOW_SWEPT_AND_CLOSE_RETURNED",)))

    directions = {signal.direction for signal in signals}
    contradictions = ()
    if "BUY" in directions and "SELL" in directions:
        contradictions = ("METHOD_DIRECTION_CONFLICT",)

    return MethodAnalysis(tuple(signals), contradictions)
