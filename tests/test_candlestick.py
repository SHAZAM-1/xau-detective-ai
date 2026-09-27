from datetime import datetime, timezone
from decimal import Decimal

from xau_detective.candlestick import (
    PRO_SCALPER_CANDLESTICK_PATTERNS,
    PRO_SCALPER_CHART_PATTERNS,
    PriceActionMove,
    detect_candlestick_patterns,
    detect_price_action_moves,
    study_patterns,
)
from xau_detective.market import Candle


def candle(o, h, l, c, minute):
    return Candle(
        timestamp=datetime(2026, 9, 27, 10, minute, tzinfo=timezone.utc),
        open=Decimal(str(o)),
        high=Decimal(str(h)),
        low=Decimal(str(l)),
        close=Decimal(str(c)),
    )


def test_detects_bullish_engulfing():
    candles = (
        candle(100, 101, 98, 99, 0),
        candle(98.5, 103, 98, 102.5, 1),
    )
    names = {item.name for item in detect_candlestick_patterns(candles)}
    assert "BULLISH_ENGULFING" in names


def test_detects_doji_and_hammer():
    candles = (
        candle(100, 105, 95, 100.2, 0),
        candle(100, 101, 94, 100.1, 1),
    )
    names = {item.name for item in detect_candlestick_patterns(candles)}
    assert "DOJI" in names
    assert "HAMMER" in names


def test_detects_impulse_breakout_and_rejection():
    candles = tuple(
        candle(100 + i, 101 + i, 99 + i, 100.5 + i, i)
        for i in range(5)
    ) + (candle(105, 110, 104, 109.5, 5),)
    moves = {item.move for item in detect_price_action_moves(candles)}
    assert PriceActionMove.EXPANSION in moves
    assert PriceActionMove.IMPULSE_UP in moves
    assert PriceActionMove.BREAKOUT_UP in moves


def test_pattern_study_is_descriptive():
    candles = tuple(
        candle(100 + i, 101.5 + i, 99.5 + i, 101 + i, i)
        for i in range(12)
    )
    studies = study_patterns(candles, horizon=2)
    assert isinstance(studies, tuple)
    if studies:
        assert studies[0].observations > 0


def test_pro_scalper_pattern_catalog_is_registered():
    assert len(PRO_SCALPER_CANDLESTICK_PATTERNS) >= 25
    assert len(PRO_SCALPER_CHART_PATTERNS) == 20
    assert "DRAGONFLY_DOJI" in PRO_SCALPER_CANDLESTICK_PATTERNS
    assert "DOUBLE_TOP" in PRO_SCALPER_CHART_PATTERNS
