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

        # Pro-Scalper XAUUSD catalog additions: the site lists 25 interactive
        # candlestick patterns. These are encoded as measurable OHLC features so
        # the research engine can test them on XAUUSD instead of treating them as
        # guaranteed signals.
        if body_ratio <= Decimal("0.10"):
            found.append(CandlePattern("DOJI", PatternFamily.SINGLE, "NEUTRAL", Decimal("0.8"), i))
        if body_ratio <= Decimal("0.30") and upper_ratio >= Decimal("0.25") and lower_ratio >= Decimal("0.25"):
            found.append(CandlePattern("SPINNING_TOP", PatternFamily.SINGLE, "NEUTRAL", Decimal("0.55"), i))
        if lower_ratio >= Decimal("0.75") and upper_ratio <= Decimal("0.10"):
            found.append(CandlePattern("DRAGONFLY_DOJI", PatternFamily.SINGLE, "BULLISH", Decimal("0.78"), i))
        if upper_ratio >= Decimal("0.75") and lower_ratio <= Decimal("0.10"):
            found.append(CandlePattern("GRAVESTONE_DOJI", PatternFamily.SINGLE, "BEARISH", Decimal("0.78"), i))
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
            if p.bullish and c.bearish and c.open < p.close and c.close > p.open and c.body < p.body:
                found.append(CandlePattern("BEARISH_HARAMI", PatternFamily.TWO_CANDLE, "BEARISH", Decimal("0.62"), i))
            if p.bearish and c.bullish and c.open > p.close and c.close < p.open and c.body < p.body:
                found.append(CandlePattern("BULLISH_HARAMI", PatternFamily.TWO_CANDLE, "BULLISH", Decimal("0.62"), i))
            if abs(c.high - p.high) <= reference * Decimal("0.10") and p.bullish and c.bearish:
                found.append(CandlePattern("TWEEZER_TOP", PatternFamily.TWO_CANDLE, "BEARISH", Decimal("0.68"), i))
            if abs(c.low - p.low) <= reference * Decimal("0.10") and p.bearish and c.bullish:
                found.append(CandlePattern("TWEEZER_BOTTOM", PatternFamily.TWO_CANDLE, "BULLISH", Decimal("0.68"), i))
            if (p.bullish and c.bearish and c.open < p.open and c.close < p.close) or (
                p.bearish and c.bullish and c.open > p.open and c.close > p.close
            ):
                if abs(c.open - p.close) >= reference * Decimal("0.50"):
                    found.append(CandlePattern("KICKER", PatternFamily.TWO_CANDLE, "BULLISH" if c.bullish else "BEARISH", Decimal("0.70"), i))
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
            if a.bullish and b.bearish and c.bearish and b.high < a.high and b.low > a.low and c.close < b.close:
                found.append(CandlePattern("THREE_INSIDE_DOWN", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.68"), i))
            if a.bearish and b.bullish and c.bullish and b.high < a.high and b.low > a.low and c.close > b.close:
                found.append(CandlePattern("THREE_INSIDE_UP", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.68"), i))
            if a.bearish and b.bullish and c.bullish and b.high < a.high and b.low > a.low and c.close > a.open:
                found.append(CandlePattern("RISING_THREE_METHODS", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.65"), i))
            if a.bullish and b.bearish and c.bearish and b.high < a.high and b.low > a.low and c.close < a.open:
                found.append(CandlePattern("FALLING_THREE_METHODS", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.65"), i))
            if a.high < b.low and b.high < c.low:
                found.append(CandlePattern("ABANDONED_BABY_BULL", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.72"), i))
            if a.low > b.high and b.low > c.high:
                found.append(CandlePattern("ABANDONED_BABY_BEAR", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.72"), i))
            if a.high < b.high < c.high and a.low < b.low < c.low:
                found.append(CandlePattern("THREE_RISING", PatternFamily.THREE_CANDLE, "BULLISH", Decimal("0.65"), i))
            if a.high > b.high > c.high and a.low > b.low > c.low:
                found.append(CandlePattern("THREE_FALLING", PatternFamily.THREE_CANDLE, "BEARISH", Decimal("0.65"), i))
    return tuple(found)

    
def detect_price_action_moves(candles: tuple[Candle, ...], lookback: int = 10) -> tuple[PriceActionEvent, ...]:
    events = []
    for i, c in enumerate(candles):
        prior = candles[max(0, i - lookback):i]
        if not prior:
            continue
        avg_range = sum((_range(x) for x in prior), Decimal(0)) / Decimal(len(prior))
        if avg_range <= 0:
            continue
        strength = _range(c) / avg_range

        if i >= 1 and c.high <= candles[i - 1].high and c.low >= candles[i - 1].low:
            events.append(PriceActionEvent(PriceActionMove.INSIDE_BAR, "NEUTRAL", Decimal("0.7"), i))
        elif i >= 1 and c.high >= candles[i - 1].high and c.low <= candles[i - 1].low:
            events.append(PriceActionEvent(PriceActionMove.OUTSIDE_BAR, "BULLISH" if c.bullish else "BEARISH", Decimal("0.7"), i))

        if strength >= Decimal("1.8"):
            move = PriceActionMove.IMPULSE_UP if c.bullish else PriceActionMove.IMPULSE_DOWN
            events.append(PriceActionEvent(PriceActionMove.EXPANSION, "BULLISH" if c.bullish else "BEARISH", strength, i))
            events.append(PriceActionEvent(move, "BULLISH" if c.bullish else "BEARISH", strength, i))
        elif strength <= Decimal("0.55"):
            events.append(PriceActionEvent(PriceActionMove.COMPRESSION, "NEUTRAL", Decimal("0.55"), i))

        if _upper(c) >= c.body * 2 and _upper(c) > _lower(c) * Decimal("1.5"):
            events.append(PriceActionEvent(PriceActionMove.REJECTION_HIGH, "BEARISH", min(Decimal("1"), _upper(c) / _range(c)), i))
        if _lower(c) >= c.body * 2 and _lower(c) > _upper(c) * Decimal("1.5"):
            events.append(PriceActionEvent(PriceActionMove.REJECTION_LOW, "BULLISH", min(Decimal("1"), _lower(c) / _range(c)), i))

        if len(prior) >= 3:
            high = max(x.high for x in prior)
            low = min(x.low for x in prior)
            if c.close > high:
                events.append(PriceActionEvent(PriceActionMove.BREAKOUT_UP, "BULLISH", strength, i))
            elif c.close < low:
                events.append(PriceActionEvent(PriceActionMove.BREAKOUT_DOWN, "BEARISH", strength, i))
            else:
                events.append(PriceActionEvent(PriceActionMove.RANGE, "NEUTRAL", Decimal("0.5"), i))
    return tuple(events)


def study_patterns(candles: tuple[Candle, ...], *, horizon: int = 3, threshold: Decimal = Decimal("0.001")) -> tuple[PatternStudy, ...]:
    """Measure forward outcomes instead of assuming a pattern has predictive power."""
    patterns = detect_candlestick_patterns(candles)
    grouped: dict[str, list[Decimal]] = {}
    for pattern in patterns:
        if pattern.index + horizon >= len(candles):
            continue
        base = candles[pattern.index].close
        future = candles[pattern.index + horizon].close
        if base > 0:
            grouped.setdefault(pattern.name, []).append((future - base) / base)

    studies = []
    for name, returns in grouped.items():
        positive = sum(1 for value in returns if value > threshold)
        negative = sum(1 for value in returns if value < -threshold)
        neutral = len(returns) - positive - negative
        studies.append(
            PatternStudy(
                pattern=name,
                observations=len(returns),
                bullish_follow_through=positive,
                bearish_follow_through=negative,
                neutral=neutral,
                average_forward_return=sum(returns, Decimal(0)) / Decimal(len(returns)),
                median_forward_return=median(returns),
                positive_rate=Decimal(positive) / Decimal(len(returns)),
                sample_horizon=horizon,
            )
        )
    return tuple(sorted(studies, key=lambda item: item.observations, reverse=True))
