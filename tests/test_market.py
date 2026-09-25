from datetime import UTC, datetime,from decimal import Decimal

from xau_detective.market import Candle, true_range

def test_true_range_uses_gap():
    c = Candle(datetime.now(UTC), Decimal(100), Decimal(105), Decimal(99), Decimal(104))
    assert true_range(c, Decimal(90)) == Decimal(15)
