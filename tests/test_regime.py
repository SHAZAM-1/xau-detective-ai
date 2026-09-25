from datetime import datetime, timedelta
from decimal import Decimal


from xau_detective.market import Candle
from xau_detective.regime import TrendState, VolatilityState, classify_regime


def rising_candles(n=80):
    t = datetime(2026, 1, 1)
    return tuple(
        Candle(
            t + timedelta(hours=i),
            Decimal(100 + i),
            Decimal(102 + i),
            Decimal(99 + i),
            Decimal(101 + i),
        )
        for i in range(n)
    )


def test_regime_detects_uptrend():
    result = classify_regime(rising_candles())
    assert result.trend is TrendState.UP
    assert result.volatility is VolatilityState.HIGH


def test_regime_requires_history():
    result = classify_regime(rising_candles(10))
    assert result.trend is TrendState.UNKNOWN
