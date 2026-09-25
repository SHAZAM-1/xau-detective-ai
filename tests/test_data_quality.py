from datetime import datetime, timedelta
from decimal import Decimal
from xau_detective.data_quality import validate_candles
from xau_detective.market import Candle


def c(t):
    return Candle(t, Decimal("1"), Decimal("2"), Decimal("0.5"), Decimal("1.5"))


def test_data_gap_is_rejected():
    t = datetime.now()
    result = validate_candles((c(t), c(t + timedelta(hours=3))), timedelta(hours=1))
    assert not result.usable
    assert "DATA_GAP" in result.reasons
