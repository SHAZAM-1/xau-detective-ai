"""Candlestick and price-action research engine for XAUUSD."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from statistics import median

from .market import Candle


class PatternFamily(str, Enum):
    SINGLE = "SINGLE"
    TWO_CANDLE = "TWO_CANDLE"
    THREE_CANDLE = "THREE_CANDLE"


class PriceActionMove(str, Enum):
    IMPULSE_UP = "IMPULSE_UP"
    IMPULSE_DOWN = "IMPULSE_DOWN"
    REJECTION_HIGH = "REJECTION_HIGH"
    REJECTION_LOW = "REJECTION_LOW"
    COMPRESSION = "COMPRESSION"
    EXPANSION = "EXPANSION"
    INSIDE_BAR = "INSIDE_BAR"
    OUTSIDE_BAR = "OUTSIDE_BAR"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    PULLBACK_UP = "PULLBACK_UP"
    PULLBACK_DOWN = "PULLBACK_DOWN"
    RANGE = "RANGE"


@dataclass(frozen=True)
class CandlePattern:
    name: str
    family: PatternFamily
    direction: str
    confidence: Decimal
    index: int


@dataclass(frozen=True)
class PriceActionEvent:
    move: PriceActionMove
    direction: str
    strength: Decimal
    index: int


@dataclass(frozen=True)
class PatternStudy:
    pattern: str
    observations: int
    bullish_follow_through: int
    bearish_follow_through: int
    neutral: int
    average_forward_return: Decimal
    median_forward_return: Decimal
    positive_rate: Decimal
    sample_horizon: int


def _range(c: Candle) -> Decimal:
    return max(c.range, Decimal(0))


def _upper(c: Candle) -> Decimal:
    return max(c.high - max(c.open, c.close), Decimal(0))


def _lower(c: Candle) -> Decimal:
    return max(min(c.open, c.close) - c.low, Decimal(0))


def _small_body(c: Candle, reference: Decimal) -> bool:
    return c.body <= reference * Decimal("0.35")


def _long_body(c: Candle, reference: Decimal) -> bool:
    return c.body >= reference * Decimal("1.25")


def detect_candlestick_patterns(candles: tuple[Candle, ...]) -> tuple[CandlePattern, ...]:
    found = []
    for i, c in enumerate(candles):
        prior = candles[max(0, i - 20):i]
        reference = median([_range(x) for x in prior]) if prior else _range(c)
        reference = max(reference, Decimal("0.00000001"))
        rng = _range(c)
        if rng <= 0:
            continue
        body_ratio = c.body / rng
        upper_ratio = _upper(c) / rng
        lower_ratio = _lower(c) / rng

        if body_ratio <= Decimal("0.10"):
            found.append(CandlePattern("DOJI", PatternFamily.SINGLE, "NEUTRAL", Decimal("0.8"), i))
        if lower_ratio >= Decimal("0.60") and body_ratio <= Decimal("0.35"):
            found.append(CandlePattern("HAMMER", PatternFamily.SINGLE, "BULLISH", Decimal("0.75"), i))
        if upper_ratio >= Decimal("0.60") and body_ratio <= Decimal("0.35"):
            found.append(CandlePattern("SHOOTING_STAR", PatternFamily.SINGLE, "BEARISH", Decimal("0.75"), i))
        if upper_ratio >= Decimal("0.60") and lower_ratio <= Decimal("0.15") and c.bearish:
            found.append(CandlePattern("INVERTED_HAMMER", PatternFamily.SINGLE, "BULLISH", Decimal("0.60"), i))
        if lower_ratio >= Decimal("0.60") and upper_ratio <= Decimal("0.15") and c.bullish:
            found.append(CandlePattern("HANGING_MAN", PatternFamily.SINGLE, "BEARISH", Decimal("0.60"), i))
        if _long_body(c, reference) and body_ratio >= Decimal("0.75"):
            name = "MARUBOZU_BULL" if c.bullish else "MARUBOZU_BEAR"
            direction = "BULLISH" if c.bullish else "BEARISH"
            found.append(CandlePattern(name, PatternFamily.SINGLE, direction, Decimal("0.70"), i))

        if i >= 1:
            p = candles[i - 1]
            if p.bearish and c.bullish and c.open <= p.close and c.close >= p.open and c.body >= p.body * Decimal("0.8"):
                found.append(CandlePattern("BULLISH_ENGULFING", PatternFamily.TWO_CANDLE, "BULLISH", Decimal("0.85"), i))
            if p.bullish and c.bearish and c.open >= p.close and c.close <= p.open and c.body >= p.body * Decimal("0.8"):
                found.append(CandlePattern("BEARISH_ENGULFING", PatternFamily.TWO_CANDLE, "BEARISH", Decimal("0.85"), i))
            if p.bearish and c.bullish and c.close > (p.open + p.close) / 2 and c.close < p.open:
                found.append(CandlePattern("PIERCING", PatternFamily.TWO_CANDLE, "BULLISH", Decimal("0.65"), i))
            if p.bullish and c.bearish and c.close < (p.open + p.close) / 2 and c.close > p.open:
                found.append(CandlePattern("DARK_CLOUD_COVER", PatternFamily.TWO_CANDLE, "BEARISH", Decimal("0.65"), i))
            if _small_body(c, reference) and c.high <= p.high and c.low >= p.low:
                found.append(CandlePattern("INSIDE_BAR", PatternFamily.TWO_CANDLE, "NEUTRAL", Decimal("0.75"), i))
            if c.high >= p.high and c.low <= p.low:
                found.append(CandlePattern("OUTSIDE_BAR", PatternFamily.TWO_CANDLE, "BULLISH" if c.bullish else "BEARISH", Decimal("0.65"), i))

        if i >= 2:
            a, b = candles[i - 2], candles[i - 1]
            if a.bearish and _small_body(b, reference) and c.bullish and c.close > (a.open + a.close) / 2:
                found.append(CandlePattern("MORNING_STAR", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.80"), i))
            if a.bullish and _small_body(b, reference) and c.bearish and c.close < (a.open + a.close) / 2:
                found.append(CandlePattern("EVENING_STAR", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.80"), i))
            if a.bearish and b.bullish and c.bullish and b.close > a.close and c.close > b.close:
                found.append(CandlePattern("THREE_WHITE_SOLDIERS", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.78"), i))
            if a.bullish and b.bearish and c.bearish and b.close < a.close and c.close < b.close:
                found.append(CandlePattern("THREE_BLACK_CROWS", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.78"), i))
            if a.high < b.high < c.high and a.low < b.low < c.low:
                found.append(CandlePattern("THREE_RISING", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.65"), i))
            if a.high > b.high > c.high and a.low > b.low > c.low:
                found.append(CandlePattern("THREE_FALLING", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.65"), i))
    return tuple(found)
