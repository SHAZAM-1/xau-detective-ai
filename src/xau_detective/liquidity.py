"""Look-ahead-safe liquidity reference features.

The module intentionally uses observable price levels rather than asserting
that concepts such as "liquidity pools" have a special causal mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .market import Candle


@dataclass(frozen=True)
class LiquiditySnapshot:
    range_high: Decimal | None
    range_low: Decimal | None
    swept_high: bool
    swept_low: bool
    equal_highs: bool
    equal_lows: bool


def analyze_liquidity(
    candles: tuple[Candle, ...],
    *,
    lookback: int = 20,
    equality_tolerance: Decimal = Decimal("0.10"),
) -> LiquiditySnapshot:
    if len(candles) < lookback + 1 or lookback < 2:
        return LiquiditySnapshot(None, None, False, False, False, False)

    previous = candles[-lookback - 1:-1]
    current = candles[-1]
    high = max(c.high for c in previous)
    low = min(c.low for c in previous)

    swept_high = current.high > high and current.close < high
    swept_low = current.low < low and current.close > low

    highs = sorted(c.high for c in previous)
    lows = sorted(c.low for c in previous)
    equal_highs = abs(highs[-1] - highs[-2]) <= equality_tolerance
    equal_lows = abs(lows[0] - lows[1]) <= equality_tolerance

    return LiquiditySnapshot(
        high,
        low,
        swept_high,
        swept_low,
        equal_highs,
        equal_lows,
    )
