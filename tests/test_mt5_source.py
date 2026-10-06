from datetime import UTC, datetime
from decimal import Decimal

from xau_detective.mt5_source import MT5CandleSource
from xau_detective.timeframes import Timeframe


class FakeMT5:
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        assert symbol == "XAUUSD"
        assert timeframe == self.TIMEFRAME_M5
        assert start == 0
        assert count == 2
        return [
            {
                "time": 1767225600,
                "open": 4000,
                "high": 4010,
                "low": 3990,
                "close": 4005,
                "tick_volume": 100,
            },
            {
                "time": 1767225900,
                "open": 4005,
                "high": 4015,
                "low": 4000,
                "close": 4010,
                "tick_volume": 110,
            },
        ]

    def last_error(self):
        return "fake error"

    def symbol_info_tick(self, symbol):
        assert symbol == "XAUUSD"
        return type("Tick", (), {"time": 1767226200})()

    def shutdown(self):
        pass


def test_mt5_source_fetch_maps_rates():
    candles = MT5CandleSource(FakeMT5()).fetch("XAUUSD", Timeframe.M5, 2)
    assert len(candles) == 2
    assert candles[0].close == Decimal(4005)
    assert candles[1].close == Decimal(4010)



def test_mt5_source_uses_terminal_tick_time():
    source = MT5CandleSource(FakeMT5())
    assert source.market_time("XAUUSD") == datetime.fromtimestamp(1767226200, tz=UTC)
