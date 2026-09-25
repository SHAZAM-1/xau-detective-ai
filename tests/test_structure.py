from datetime import datetime, timedelta
from decimal import Decimal

from xau_detective.market import Candle
from xau_detective.models import Direction
from xau_detective.structure import analyze_structure


def test_upside_breakout_can_create_buy_structure():
    t = datetime(2026, 1, 1)
    candles = tuple(
        Candle(
            t + timedelta(minutes=i),
            Decimal("100"),
            Decimal(101 + i),
            Decimal("99"),
            Decimal(100 + i),
        )
        for i in range(21)
    )
    result = analyze_structure(candles, lookback=20)
    assert result.direction is Direction.BUY
    assert result.breakout
