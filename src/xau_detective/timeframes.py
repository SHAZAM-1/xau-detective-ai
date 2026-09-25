"""Timeframe labels and closed-candle discipline."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Timeframe(str, Enum):
    D1 = "D1"
    H4 = "H4"
    H1 = "H1"
    M15 = "M15"
    M5 = "M5"


@dataclass(frozen=True)
class TimeframeMap:
    context: Timeframe = Timeframe.D1
    regime: Timeframe = Timeframe.H4
    structure: Timeframe = Timeframe.H1
    setup: Timeframe = Timeframe.M15
    entry: Timeframe = Timeframe.M5

    def values(self) -> tuple[Timeframe, ...]:
        return (self.context, self.regime, self.structure, self.setup, self.entry)
