"""Event-driven OHLC backtesting with explicit trading frictions.

Signals are evaluated on a closed candle and entered on the next candle open.
Spread, slippage and commission are included so research results are not based
on frictionless fills. When stop and target are both touched in one candle,
the conservative assumption is that the stop is hit first.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from .market import Candle
from .models import Direction

@