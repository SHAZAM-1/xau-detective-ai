from datetime import UTC, datetime
from xau_detective.ingestion import keep_closed_candles
from xau_detective.market import Candle
from xau_detective.timeframes import Timeframe, expected_interval

def candle(ts):
    return Candle(ts, 1, 2, 0, 1, 1)

def test_expected_intervals_are_explicit():
    assert expected_interval(Timeframe.M5).total_seconds() == 300
    assert expected_interval(Timeframe.H1).total_seconds() == 3600

def test_keep_closed_candles_drops_forming_candle():
    now = datetime(2026, 9, 26, 14, 0, tzinfo=UTC)
    candles = (candle(datetime(2026, 9, 26, 13, 55, tzinfo=UTC)), candle(datetime(2026, 9, 26, 14, 0, tzinfo=UTC)))
    assert len(keep_closed_candles(candles, now=now, timeframe=Timeframe.M5)) == 1
