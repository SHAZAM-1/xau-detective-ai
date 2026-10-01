"""Deterministic support/resistance zone detection for research.

Zones are descriptive price areas derived only from historical closed candles.
They do not create trades or override strategy/risk policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .market import Candle


@dataclass(frozen=True)
class PriceZone:
    kind: str
    low: Decimal
    high: Decimal
    midpoint: Decimal
    touches: int


@dataclass(frozen=True)
class ZoneAnalysis:
    support: tuple[PriceZone, ...]
    resistance: tuple[PriceZone, ...]


def _cluster(levels: list[Decimal], tolerance: Decimal, kind: str) -> tuple[PriceZone, ...]:
    if not levels:
        return ()
    levels.sort()
    clusters: list[list[Decimal]] = [[levels[0]]]
    for level in levels[1:]:
        current = clusters[-1]
        center = sum(current, Decimal(0)) / Decimal(len(current))
        if abs(level - center) <= tolerance:
            current.append(level)
        else:
            clusters.append([level])

    zones = []
    for cluster in clusters:
        low = min(cluster) - tolerance
        high = max(cluster) + tolerance
        midpoint = (low + high) / Decimal(2)
        zones.append(PriceZone(kind, low, high, midpoint, len(cluster)))
    return tuple(zones)


def analyze_zones(
    candles: tuple[Candle, ...],
    *,
    lookback: int = 50,
    tolerance_fraction: Decimal = Decimal("0.001"),
    min_touches: int = 2,
) -> ZoneAnalysis:
    if lookback < 3 or tolerance_fraction <= 0 or min_touches < 1:
        return ZoneAnalysis((), ())
    window = candles[-lookback:] if len(candles) >= lookback else candles
    if len(window) < 3:
        return ZoneAnalysis((), ())

    prices = tuple(c.close for c in window)
    reference = max(prices) - min(prices)
    tolerance = reference * tolerance_fraction
    if tolerance <= 0:
        return ZoneAnalysis((), ())

    support_levels: list[Decimal] = []
    resistance_levels: list[Decimal] = []
    for index in range(1, len(window) - 1):
        previous_candle = window[index - 1]
        current = window[index]
        next_candle = window[index + 1]
        if current.low <= previous_candle.low and current.low <= next_candle.low:
            support_levels.append(current.low)
        if current.high >= previous_candle.high and current.high >= next_candle.high:
            resistance_levels.append(current.high)

    support = tuple(
        zone for zone in _cluster(support_levels, tolerance, "SUPPORT")
        if zone.touches >= min_touches
    )
    resistance = tuple(
        zone for zone in _cluster(resistance_levels, tolerance, "RESISTANCE")
        if zone.touches >= min_touches
    )
    return ZoneAnalysis(support, resistance)
