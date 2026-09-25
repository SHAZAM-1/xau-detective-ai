"""Optional MetaTrader 5 adapter boundary.

The core engine does not import the MetaTrader5 package. This keeps research and
unit tests broker-independent while allowing a live MT5 connector later.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .market import Candle
from .models import AccountSnapshot, BrokerSpec

def