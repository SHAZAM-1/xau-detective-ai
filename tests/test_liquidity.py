from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.liquidity import analyze_liquidity
from xau_detective.market import Candle


def candles(values):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        Candle(
            start + timedelta(hours=i),
            Decimal(str(value)),
            Decimal(str(value + 2)),
            Decimal(str(value - 1)),
            Decimal(str(value + 1)),
        )
        for i, value in enumerate(values)
    )


def test_liquidity_is_lookahead_safe_and_detects_sweep():
    base = list(range(100, 120))
    base[-1] = 118
    result = analyze_liquidity(candles(base), lookback=10)
    assert result.range_high == Decimal(120)
    assert result.swept_high is False


def test_equal_levels():
    values = [100] * 8 + [101, 101, 102]
    result = analyze_liquidity(candles(values), lookback=10)
    assert result.equal_highs
