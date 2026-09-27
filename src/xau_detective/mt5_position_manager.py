"""MT5 Demo position and order lifecycle inspection.

This module is read-only: it reconciles broker state after submission without
making trading decisions or opening/closing positions.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PositionSnapshot:
    ticket: str
    symbol: str
    volume: Decimal
    price_open: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    magic: int | None
    comment: str | None


@dataclass(frozen=True)
class OrderSnapshot:
    ticket: str
    symbol: str
    volume: Decimal
    price_open: Decimal
    magic: int | None
    comment: str | None
    state: str | None


@dataclass(frozen=True)
class LifecycleSnapshot:
    positions: tuple[PositionSnapshot, ...]
    orders: tuple[OrderSnapshot, ...]

    @property
    def active(self) -> bool:
        return bool(self.positions or self.orders)


class MT5PositionManager:
    """Inspect broker lifecycle state for one symbol/magic pair."""

    def __init__(self, mt5_module: Any, *, symbol: str, magic: int) -> None:
        self._mt5 = mt5_module
        self._symbol = symbol
        self._magic = magic

    @staticmethod
    def _decimal(value: Any, default: str = "0") -> Decimal:
        return Decimal(str(default if value is None else value))

    def _matches(self, item: Any) -> bool:
        symbol = str(getattr(item, "symbol", ""))
        magic = getattr(item, "magic", None)
        return symbol == self._symbol and (
            magic is None or int(magic) == self._magic
        )

    def _position(self, item: Any) -> PositionSnapshot:
        return PositionSnapshot(
            ticket=str(getattr(item, "ticket")),
            symbol=str(getattr(item, "symbol")),
            volume=self._decimal(getattr(item, "volume", 0)),
            price_open=self._decimal(getattr(item, "price_open", 0)),
            stop_loss=self._decimal(getattr(item, "sl", 0)),
            take_profit=self._decimal(getattr(item, "tp", 0)),
            magic=(
                int(getattr(item, "magic"))
                if getattr(item, "magic", None) is not None
                else None
            ),
            comment=getattr(item, "comment", None),
        )

    def _order(self, item: Any) -> OrderSnapshot:
        return OrderSnapshot(
            ticket=str(getattr(item, "ticket")),
            symbol=str(getattr(item, "symbol")),
            volume=self._decimal(
                getattr(item, "volume_current", getattr(item, "volume_initial", 0))
            ),
            price_open=self._decimal(getattr(item, "price_open", 0)),
            magic=(
                int(getattr(item, "magic"))
                if getattr(item, "magic", None) is not None
                else None
            ),
            comment=getattr(item, "comment", None),
            state=(
                str(getattr(item, "state"))
                if getattr(item, "state", None) is not None
                else None
            ),
        )

    def snapshot(self) -> LifecycleSnapshot:
        positions_get = getattr(self._mt5, "positions_get", None)
        orders_get = getattr(self._mt5, "orders_get", None)

        raw_positions = positions_get(symbol=self._symbol) if callable(positions_get) else ()
        raw_orders = orders_get(symbol=self._symbol) if callable(orders_get) else ()

        positions = tuple(
            self._position(item)
            for item in (raw_positions or ())
            if self._matches(item)
        )
        orders = tuple(
            self._order(item)
            for item in (raw_orders or ())
            if self._matches(item)
        )
        return LifecycleSnapshot(positions=positions, orders=orders)

    def find_ticket(self, ticket: str) -> PositionSnapshot | OrderSnapshot | None:
        state = self.snapshot()
        for item in (*state.positions, *state.orders):
            if item.ticket == str(ticket):
                return item
        return None
