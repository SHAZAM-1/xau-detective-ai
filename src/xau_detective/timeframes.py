"""Timeframe labels and closed-candle discipline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class Timeframe(str, Enum):
    D1 = "D1"
    H4 = "H4"
    H1 = "H1"
    M15 = "M15"
    M5 = "M5"


_INTERVALS = {
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),
}


def expected_interval(timeframe: Timeframe) -> timedelta:
    return _INTERVALS[timeframe]


@dataclass(frozen=True)
class TimeframeMap:
    context: Timeframe = Timeframe.D1
    regime: Timeframe = Timeframe.H4
    structure: Timeframe = Timeframe.H1
    setup: Timeframe = Timeframe.M15
    entry: Timeframe = Timeframe.M5

    def values(self) -> tuple[Timeframe, ...]:
        return (self.context, self.regime, self.structure, self.setup, self.entry)
