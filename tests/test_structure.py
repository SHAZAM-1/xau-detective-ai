from datetime import UTC, datetime, timedelta
from decimal import Decimal
from xau_detective.market import Candle
from xau_detective.models import Direction
from xau_detective.structure import analyze_structure

def test_upside_breakout_can_create_buy_structure():
    t = datetime(2026, 1, 1, tzinfo=UTC)
    candles = tuple(Candle(t + timedelta(minutes=i), Decimal(100), Decimal(101 + i), Decimal(90 + i), Decimal(100 + i)) for i in range(20)) + (Candle(t + timedelta(minutes=20), Decimal(120), Decimal(123), Decimal(110), Decimal(122)),)
    result = analyze_structure(candles, lookback=20)
    assert result.direction is Direction.BUY
    assert result.breakout

def test_confirmed_swing_sequence_is_exposed():
    t = datetime(2026, 1, 1, tzinfo=UTC)
    closes = (100, 104, 101, 106, 103, 108, 105)
    candles = tuple(Candle(t + timedelta(minutes=i), Decimal(close), Decimal(close + 2), Decimal(close - 2), Decimal(close + 1)) for i, close in enumerate(closes)) + (Candle(t + timedelta(minutes=len(closes)), Decimal(105), Decimal(109), Decimal(103), Decimal(108)),)
    result = analyze_structure(candles, lookback=5, pivot_window=1)
    assert result.swing_highs
    assert result.swing_lows
    assert result.higher_high
    assert result.higher_low

def test_bos_is_a_new_crossing_not_a_repeated_state():
    t = datetime(2026, 1, 1, tzinfo=UTC)
    closes = (100, 105, 101, 106, 102, 107, 108)
    candles = tuple(Candle(t + timedelta(minutes=i), Decimal(close), Decimal(close + 1), Decimal(close - 1), Decimal(close)) for i, close in enumerate(closes))
    first = analyze_structure(candles, lookback=5, pivot_window=1)
    assert first.break_of_structure == "BULLISH_BOS"
    continued = candles + (Candle(t + timedelta(minutes=len(candles)), Decimal(108), Decimal(109), Decimal(107), Decimal(108)),)
    second = analyze_structure(continued, lookback=5, pivot_window=1)
    assert second.break_of_structure is None

def test_structure_state_is_bullish_for_higher_highs_and_higher_lows():
    t = datetime(2026, 1, 1, tzinfo=UTC)
    closes = (100, 105, 101, 108, 103, 111, 106, 112)
    candles = tuple(Candle(t + timedelta(minutes=i), Decimal(close), Decimal(close + 1), Decimal(close - 1), Decimal(close)) for i, close in enumerate(closes))
    result = analyze_structure(candles, lookback=5, pivot_window=1)
    assert result.structure_state == "BULLISH"

def test_invalid_structure_configuration_fails_closed():
    t = datetime(2026, 1, 1, tzinfo=UTC)
    candles = (Candle(t, Decimal(100), Decimal(102), Decimal(98), Decimal(101)), Candle(t + timedelta(minutes=1), Decimal(101), Decimal(103), Decimal(99), Decimal(102)), Candle(t + timedelta(minutes=2), Decimal(102), Decimal(104), Decimal(100), Decimal(103)))
    result = analyze_structure(candles, lookback=0, pivot_window=1)
    assert result.direction is Direction.NO_TRADE
    assert result.range_high is None
    assert result.range_low is None
