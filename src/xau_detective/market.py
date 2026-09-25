"""Normalized OHLCV market-data models and basic candle utilities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal(0)

    @property
    def body(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def range(self) -> Decimal:
        return self.high - self.low

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open


def true_range(current: Candle, previous_close: Decimal | None) -> Decimal:
    if previous_close is None:
        return current.range
    return max(
        current.range,
        abs(current.high - previous_close),
        abs(current.low - previous_close),
    )
