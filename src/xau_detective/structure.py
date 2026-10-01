"""Deterministic market-structure features for research; not a magic SMC detector."""
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
    swing_highs: tuple[Decimal, ...] = ()
    swing_lows: tuple[Decimal, ...] = ()
    break_of_structure: str | None = None
    change_of_character: str | None = None


def _confirmed_swings(
    candles: tuple[Candle, ...],
    *,
    pivot_window: int,
) -> tuple[tuple[Decimal, ...], tuple[Decimal, ...]]:
    """Return confirmed pivot highs/lows without using an unconfirmed edge candle."""
    if pivot_window < 1 or len(candles) < (2 * pivot_window) + 1:
        return (), ()

    highs: list[Decimal] = []
    lows: list[Decimal] = []
    last_pivot_index = len(candles) - pivot_window

    for index in range(pivot_window, last_pivot_index):
        candle = candles[index]
        left = candles[index - pivot_window:index]
        right = candles[index + 1:index + pivot_window + 1]
        if all(candle.high > other.high for other in (*left, *right)):
            highs.append(candle.high)
        if all(candle.low < other.low for other in (*left, *right)):
            lows.append(candle.low)

    return tuple(highs), tuple(lows)


def _classify_swings(values: tuple[Decimal, ...]) -> tuple[bool, bool]:
    if len(values) < 2:
        return False, False
    return values[-1] > values[-2], values[-1] < values[-2]


def analyze_structure(
    candles: tuple[Candle, ...],
    lookback: int = 20,
    *,
    pivot_window: int = 2,
) -> StructureSnapshot:
    """Analyze range, confirmed swings, BOS and possible CHoCH.

    Swing points are only included after enough candles exist on both sides of
    the pivot, preventing the current edge candle from being treated as a
    confirmed swing. The result is descriptive research evidence only.
    """
    if (
        lookback < 1
        or pivot_window < 1
        or len(candles) < max(3, lookback + 1)
    ):
        return StructureSnapshot(
            Direction.NO_TRADE,
            False,
            False,
            False,
            False,
            False,
            None,
            None,
        )

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

    swing_highs, swing_lows = _confirmed_swings(
        candles,
        pivot_window=pivot_window,
    )
    swing_higher_high, swing_lower_high = _classify_swings(swing_highs)
    swing_higher_low, swing_lower_low = _classify_swings(swing_lows)

    break_of_structure: str | None = None
    if swing_highs and current.close > swing_highs[-1]:
        break_of_structure = "BULLISH_BOS"
    elif swing_lows and current.close < swing_lows[-1]:
        break_of_structure = "BEARISH_BOS"

    change_of_character: str | None = None
    if break_of_structure == "BULLISH_BOS" and swing_lower_high:
        change_of_character = "BULLISH_CHOCH"
    elif break_of_structure == "BEARISH_BOS" and swing_higher_low:
        change_of_character = "BEARISH_CHOCH"

    higher_high = higher_high or swing_higher_high
    higher_low = higher_low or swing_higher_low
    lower_high = lower_high or swing_lower_high
    lower_low = lower_low or swing_lower_low

    if breakout_up and higher_low:
        direction = Direction.BUY
    elif breakout_down and lower_high:
        direction = Direction.SELL
    else:
        direction = Direction.NO_TRADE

    return StructureSnapshot(
        direction=direction,
        higher_high=higher_high,
        higher_low=higher_low,
        lower_high=lower_high,
        lower_low=lower_low,
        breakout=breakout_up or breakout_down,
        range_high=range_high,
        range_low=range_low,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        break_of_structure=break_of_structure,
        change_of_character=change_of_character,
    )
