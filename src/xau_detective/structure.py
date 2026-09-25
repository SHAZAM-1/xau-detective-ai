"""Small, deterministic structure features for research; not a magic SMC detector."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .market import Candle
from .models import Direction


@dataclass(frozen=True)
class StructureSnapshot:
    direction: Direction
    higher_high: bool
    higher_low: bool
    lower_high: bool
    lower_low: bool
    breakout: bool
    range_high: Decimal | None
    range_low: Decimal | None


def analyze_structure(candles: tuple[Candle, ...], lookback: int = 20) -> StructureSnapshot:
    if len(candles) < max(3, lookback + 1):
        return StructureSnapshot(Direction.NO_TRADE, False, False, False, False, False, None, None)

    previous = candles[-lookback - 1:-1]
    current = candles[-1]
    range_high = max(c.high for c in previous)
    range_low = min(c.low for c in previous)
    higher_high = current.high > previous[-1].high
    higher_low = current.low > previous[-1].low
    lower_high = current.high < previous[-1].high
    lower_low = current.low < previous[-1].low
    breakout_up = current.close > range_high
    breakout_down = current.close < range_low

    if breakout_up and higher_low:
        direction = Direction.BUY
    elif breakout_down and lower_high:
        direction = Direction.SELL
    else:
        direction = Direction.NO_TRADE

    return StructureSnapshot(
        direction, higher_high, higher_low, lower_high, lower_low,
        breakout_up or breakout_down, range_high, range_low,
    )
