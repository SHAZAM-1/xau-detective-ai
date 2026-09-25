from datetime import datetime, timedelta, timezone
from decimal import Decimal


from xau_detective.ingestion import keep_closed_candles, load_multi_timeframe
from xau_detective.market import Candle
from xau_detective.timeframes import Timeframe


def candle(ts):
    return Candle(
        ts, Decimal(4000), Decimal(4010), Decimal(3990), Decimal(4005)
    )


class FakeSource:
    def __init__(self, candles):
        self.candles = candles

    def fetch(self, symbol, timeframe, count):
        return self.candles[:count]


def test_forming_candle_is_removed():
    now = datetime(2026, 1, 1, 10, 10, tzinfo=timezone.utc)
    candles = (
        candle(datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)),
        candle(datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc)),
    )
    closed = keep_closed_candles(candles, now=now, timeframe=Timeframe.M5)
    assert len(closed) == 2


def test_current_candle_is_not_used():
    now = datetime(2026, 1, 1, 10, 4, tzinfo=timezone.utc)
    candles = (
        candle(datetime(2026, 1, 1, 9, 55, tzinfo=timezone.utc)),
        candle(datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)),
    )
    closed = keep_closed_candles(candles, now=now, timeframe=Timeframe.M5)
    assert len(closed) == 1


def test_multi_timeframe_loader_runs_quality_gate():
    now = datetime(2026, 1, 1, 10, 10, tzinfo=timezone.utc)
    candles = tuple(
        candle(datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=5 * i))
        for i in range(20)
    )
    snapshots = load_multi_timeframe(
        FakeSource(candles),
        "XAUUSD",
        (Timeframe.M5,),
        20,
        now=now,
    )
    assert len(snapshots) == 1
    assert snapshots[0].quality.usable
