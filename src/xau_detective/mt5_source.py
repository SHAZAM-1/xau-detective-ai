"""Concrete MetaTrader 5 candle source.

This module is intentionally isolated from the deterministic core. Install the
optional dependency with: pip install -e ".[mt5]".
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .broker_clock import infer_broker_offset, to_broker_time
from .market import Candle
from .mt5_adapter import _utc_timestamp, candle_from_mt5
from .timeframes import Timeframe


class MT5CandleSource:
    def __init__(self, mt5_module: Any | None = None) -> None:
        if mt5_module is None:
            try:
                import MetaTrader5 as mt5
            except ImportError as exc:
                raise RuntimeError(
                    'MetaTrader5 is not installed. Use: pip install -e ".[mt5]"'
                ) from exc
            mt5_module = mt5
        self.mt5 = mt5_module

    def fetch(self, symbol: str, timeframe: Timeframe, count: int) -> tuple[Candle, ...]:
        if count <= 0:
            return ()
        tf = {
            Timeframe.M5: self.mt5.TIMEFRAME_M5,
            Timeframe.M15: self.mt5.TIMEFRAME_M15,
            Timeframe.H1: self.mt5.TIMEFRAME_H1,
            Timeframe.H4: self.mt5.TIMEFRAME_H4,
            Timeframe.D1: self.mt5.TIMEFRAME_D1,
        }[timeframe]
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            error = self.mt5.last_error()
            raise RuntimeError(f"MT5 candle request failed: {error}")
        return tuple(candle_from_mt5(rate) for rate in rates)

    def market_time(self, symbol: str) -> datetime:
        """Return the MT5 market clock normalized to UTC."""
        try:
            tick = self.mt5.symbol_info_tick(symbol)
        except Exception as exc:
            raise RuntimeError("MT5_MARKET_TIME_UNAVAILABLE") from exc
        if tick is None or not hasattr(tick, "time"):
            raise RuntimeError("MT5_MARKET_TIME_UNAVAILABLE")
        return _utc_timestamp(tick.time)

    def broker_offset(self, symbol: str) -> timedelta:
        """Infer the current broker server UTC offset from D1 candle opens."""
        daily = self.fetch(symbol, Timeframe.D1, 3)
        return infer_broker_offset(candle.timestamp for candle in daily)

    def broker_time(self, symbol: str, timestamp: datetime | None = None) -> datetime:
        """Return a UTC timestamp converted to the broker's current server time."""
        utc_timestamp = timestamp or self.market_time(symbol)
        return to_broker_time(utc_timestamp, self.broker_offset(symbol))

    def shutdown(self) -> None:
        self.mt5.shutdown()
