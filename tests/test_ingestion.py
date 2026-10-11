from datetime import UTC, datetime, timedelta

from xau_detective.ingestion import keep_closed_candles, load_multi_timeframe, load_timeframe
from xau_detective.market import Candle
from xau_detective.timeframes import Timeframe, expected_interval


def candle(ts, low=0.5):
    return Candle(ts, 1, 2, low, 1, 1)


class FakeSource:
    def __init__(self, candles):
        self.candles = candles
        self.calls = []

    def fetch(self, symbol, timeframe, count):
        self.calls.append((symbol, timeframe, count))
        return self.candles


def test_expected_intervals_are_explicit():
    assert expected_interval(Timeframe.M5).total_seconds() == 300
    assert expected_interval(Timeframe.H1).total_seconds() == 3600


def test_keep_closed_candles_drops_forming_candle():
    now = datetime(2026, 9, 26, 14, 0, tzinfo=UTC)
    candles = (
        candle(datetime(2026, 9, 26, 13, 55, tzinfo=UTC)),
        candle(datetime(2026, 9, 26, 14, 0, tzinfo=UTC)),
    )
    assert len(keep_closed_candles(candles, now=now, timeframe=Timeframe.M5)) == 1


def test_load_timeframe_rejects_stale_closed_data():
    now = datetime(2026, 9, 26, 14, 30, tzinfo=UTC)
    candles = (
        candle(datetime(2026, 9, 26, 14, 0, tzinfo=UTC)),
        candle(datetime(2026, 9, 26, 14, 5, tzinfo=UTC)),
    )
    snapshot = load_timeframe(
        FakeSource(candles),
        "XAUUSD",
        Timeframe.M5,
        10,
        now=now,
        max_staleness=timedelta(minutes=10),
    )
    assert not snapshot.quality.usable
    assert "STALE_DATA" in snapshot.quality.reasons


def test_load_timeframe_accepts_fresh_closed_data():
    now = datetime(2026, 9, 26, 14, 10, tzinfo=UTC)
    candles = (
        candle(datetime(2026, 9, 26, 14, 0, tzinfo=UTC)),
        candle(datetime(2026, 9, 26, 14, 5, tzinfo=UTC)),
    )
    snapshot = load_timeframe(
        FakeSource(candles),
        "XAUUSD",
        Timeframe.M5,
        10,
        now=now,
        max_staleness=timedelta(minutes=10),
    )
    assert snapshot.quality.usable


def test_load_multi_timeframe_preserves_requested_order():
    now = datetime(2026, 9, 26, 14, 10, tzinfo=UTC)
    source = FakeSource((candle(datetime(2026, 9, 26, 14, 0, tzinfo=UTC)),))
    snapshots = load_multi_timeframe(
        source,
        "XAUUSD",
        (Timeframe.H1, Timeframe.M15, Timeframe.M5),
        10,
        now=now,
    )
    assert tuple(snapshot.timeframe for snapshot in snapshots) == (
        Timeframe.H1,
        Timeframe.M15,
        Timeframe.M5,
    )
    assert source.calls == [
        ("XAUUSD", Timeframe.H1, 10),
        ("XAUUSD", Timeframe.M15, 10),
        ("XAUUSD", Timeframe.M5, 10),
    ]



def test_load_timeframe_passes_gap_policy_to_quality_gate():
    now = datetime(2026, 10, 6, 2, 0, tzinfo=UTC)
    candles = (
        candle(datetime(2026, 10, 5, 23, 55, tzinfo=UTC)),
        candle(datetime(2026, 10, 6, 1, 0, tzinfo=UTC)),
    )
    snapshot = load_timeframe(
        FakeSource(candles),
        "XAUUSD",
        Timeframe.M5,
        10,
        now=now,
        gap_is_expected=lambda previous, current: True,
    )
    assert snapshot.quality.usable
