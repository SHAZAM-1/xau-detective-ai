"""Optional MetaTrader 5 adapter boundary.

The core engine does not import the MetaTrader5 package. This keeps research and
unit tests broker-independent while allowing a live MT5 connector later.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .market import Candle
from .models import AccountSnapshot, BrokerSpec


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def candle_from_mt5(rate: Any) -> Candle:
    def get(name: str) -> Any:
        if isinstance(rate, dict):
            return rate[name]
        return getattr(rate, name)

    timestamp = get("time")
    if isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    volume = (
        get("tick_volume")
        if (isinstance(rate, dict) and "tick_volume" in rate)
        or hasattr(rate, "tick_volume")
        else 0
    )
    return Candle(
        timestamp=timestamp,
        open=_decimal(get("open")),
        high=_decimal(get("high")),
        low=_decimal(get("low")),
        close=_decimal(get("close")),
        volume=_decimal(volume),
    )


def candles_from_mt5(rates: Any) -> tuple[Candle, ...]:
    return tuple(candle_from_mt5(rate) for rate in rates)


def broker_spec_from_mt5(symbol_info: Any) -> BrokerSpec:
    return BrokerSpec(
        symbol=str(symbol_info.name),
        contract_size=_decimal(symbol_info.trade_contract_size),
        volume_min=_decimal(symbol_info.volume_min),
        volume_max=_decimal(symbol_info.volume_max),
        volume_step=_decimal(symbol_info.volume_step),
        tick_size=_decimal(symbol_info.trade_tick_size),
        tick_value=_decimal(symbol_info.trade_tick_value),
        point=_decimal(symbol_info.point),
        min_stop_distance=_decimal(symbol_info.trade_stops_level) * _decimal(symbol_info.point),
    )


def account_snapshot_from_mt5(account_info: Any) -> AccountSnapshot:
    return AccountSnapshot(
        balance=_decimal(account_info.balance),
        equity=_decimal(account_info.equity),
        free_margin=_decimal(account_info.margin_free),
    )
