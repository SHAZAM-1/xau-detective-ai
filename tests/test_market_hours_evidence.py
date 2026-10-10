from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from xau_detective.market_hours_evidence import (
    collect_market_hours_evidence,
    resolve_symbol_read_only,
)


def _rate(timestamp):
    return SimpleNamespace(
        time=int(timestamp.timestamp()),
        open=4000.0,
        high=4010.0,
        low=3990.0,
        close=4005.0,
        tick_volume=10,
    )


class FakeMT5:
    TIMEFRAME_D1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_H1 = 16385 + 1
    TIMEFRAME_M15 = 15
    TIMEFRAME_M5 = 5

    def __init__(self):
        self.calls = []
        self.fail = False

    def copy_rates_range(self, symbol, timeframe, start, end):
        self.calls.append((symbol, timeframe, start, end))
        if self.fail:
            return None
        if timeframe == self.TIMEFRAME_M5 and start == datetime(
            2026, 9, 28, 18, tzinfo=UTC
        ):
            return (
                _rate(datetime(2026, 9, 28, 20, tzinfo=UTC)),
                _rate(datetime(2026, 9, 29, 0, tzinfo=UTC)),
            )
        if timeframe == self.TIMEFRAME_D1:
            timestamp = datetime(
                start.year,
                start.month,
                start.day,
                21 if start.month in {3, 4, 9} else 22,
                tzinfo=UTC,
            )
            return (_rate(timestamp),)
        return (_rate(start + timedelta(hours=1)),)


def test_collect_market_hours_evidence_records_observed_gaps_and_d1_offsets():
    mt5 = FakeMT5()
    evidence = collect_market_hours_evidence(mt5, "XAUUSD.a")

    assert evidence["read_only"] is True
    assert evidence["account_mode"] == "DEMO"
    assert evidence["symbol"] == "XAUUSD.a"
    assert len(mt5.calls) == 30

    rollover = evidence["windows"]["ordinary_weekday_rollover"]["M5"]
    assert rollover["candle_count"] == 2
    assert rollover["gaps_over_two_intervals"][0]["elapsed_seconds"] == 14400

    d1 = evidence["windows"]["ordinary_weekday_rollover"]["D1"]
    assert d1["d1_open_offset_samples"][0]["inferred_utc_offset_minutes"] == 180


def test_collect_market_hours_evidence_fails_closed_when_mt5_returns_none():
    mt5 = FakeMT5()
    mt5.fail = True
    with pytest.raises(RuntimeError, match="MT5_RANGE_REQUEST_FAILED"):
        collect_market_hours_evidence(mt5, "XAUUSD.a")



def test_read_only_symbol_resolution_does_not_select_market_watch_symbol():
    class SymbolMT5:
        def symbol_info(self, symbol):
            return None

        def symbols_get(self):
            return (SimpleNamespace(name="XAUUSD.a"),)

        def symbol_select(self, symbol, selected):
            raise AssertionError("read-only resolver must not change Market Watch")

    assert resolve_symbol_read_only(SymbolMT5(), "XAUUSD") == "XAUUSD.a"


def test_read_only_symbol_resolution_rejects_ambiguous_suffixes():
    class AmbiguousMT5:
        def symbol_info(self, symbol):
            return None

        def symbols_get(self):
            return (
                SimpleNamespace(name="XAUUSD.a"),
                SimpleNamespace(name="XAUUSD#"),
            )

    with pytest.raises(RuntimeError, match="MT5_SYMBOL_AMBIGUOUS"):
        resolve_symbol_read_only(AmbiguousMT5(), "XAUUSD")
