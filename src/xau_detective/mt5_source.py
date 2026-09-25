"""Concrete MetaTrader 5 candle source.

This module is intentionally isolated from the deterministic core. Install the
optional dependency with: pip install -e ".[mt5]".
"""
from __future__ import annotations

from typing import Any

from .market import Candle
from .mt5_adapter import candle_from_mt5
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

    def shutdown(self) -> None:
        self.mt5.shutdown()
