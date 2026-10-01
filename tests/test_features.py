from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.features import atr, compute_features
from xau_detective.market import Candle


def candles(n=60):
    t = datetime(2026, 1, 1, tzinfo=UTC)
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


def test_atr_uses_true_range():
    result = atr(candles(20), period=14)
    assert result is not None
    assert result > 0


def test_features_require_enough_history_for_long_ema():
    result = compute_features(candles(20), ema_fast_period=20, ema_slow_period=50)
    assert result.ema_fast is not None
    assert result.ema_slow is None
    assert result.return_pct is not None
