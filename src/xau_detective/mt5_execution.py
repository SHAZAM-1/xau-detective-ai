"""Concrete MetaTrader 5 Demo order gateway.

This module only maps a validated TradeIntent to MT5's order_send API.
The caller must enforce the Demo capability gate before invoking it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .demo_execution import TradeIntent
from .models import Direction


@dataclass(frozen=True)
class MT5OrderResponse:
    accepted: bool
    order_id: str | None
    deal_id: str | None
    filled_volume: Decimal | None
    price: Decimal | None
    retcode: int | None
    comment: str


class MetaTrader5DemoGateway:
    """Thin MT5 adapter; it never decides whether an account is Demo."""

    def __init__(
        self,
        mt5_module: Any,
        *,
        magic: int = 260926,
        comment: str = "xau-detective-demo",
        deviation: int = 20,
    ) -> None:
        self._mt5 = mt5_module
        self._magic = magic
        self._comment = comment
        self._deviation = deviation

    def build_request(self, intent: TradeIntent) -> dict[str, Any]:
        if intent.direction is Direction.BUY:
            order_type = self._mt5.ORDER_TYPE_BUY
        elif intent.direction is Direction.SELL:
            order_type = self._mt5.ORDER_TYPE_SELL
        else:
            raise ValueError("NO_TRADE_DIRECTION")

        return {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": intent.symbol,
            "volume": float(intent.volume),
            "type": order_type,
            "price": float(intent.entry),
            "sl": float(intent.stop_loss),
            "tp": float(intent.take_profit),
            "deviation": self._deviation,
            "magic": self._magic,
            "comment": self._comment,
            "type_time": getattr(
                self._mt5, "ORDER_TIME_GTC", 0
            ),
            "type_filling": self._filling_mode(intent.symbol),
        }

    def _filling_mode(self, symbol: str) -> int:
        info = self._mt5.symbol_info(symbol)
        if info is None:
            raise ValueError("SYMBOL_INFO_UNAVAILABLE")
        flags = int(getattr(info, "filling_mode", 0) or 0)
        fok = getattr(self._mt5, "ORDER_FILLING_FOK", 0)
        ioc = getattr(self._mt5, "ORDER_FILLING_IOC", 1)
        if flags & int(fok):
            return int(fok)
        if flags & int(ioc):
            return int(ioc)
        return int(ioc)

    def send_order_detailed(self, intent: TradeIntent) -> MT5OrderResponse:
        request = self.build_request(intent)
        order_check = getattr(self._mt5, "order_check", None)
        if callable(order_check):
            check = order_check(request)
            if check is None:
                raise RuntimeError("MT5_ORDER_CHECK_RETURNED_NONE")
            check_retcode = int(getattr(check, "retcode", -1))
            check_done = getattr(self._mt5, "TRADE_RETCODE_DONE", 10009)
            if check_retcode not in {int(check_done), 0}:
                comment = str(getattr(check, "comment", "MT5_ORDER_CHECK_REJECTED"))
                raise RuntimeError(
                    f"MT5_ORDER_CHECK_REJECTED:{check_retcode}:{comment}"
                )

        result = self._mt5.order_send(request)
        if result is None:
            raise RuntimeError("MT5_ORDER_SEND_RETURNED_NONE")

        retcode = int(getattr(result, "retcode", -1))
        done = getattr(self._mt5, "TRADE_RETCODE_DONE", 10009)
        placed = getattr(self._mt5, "TRADE_RETCODE_PLACED", 10008)
        if retcode not in {done, placed}:
            comment = str(getattr(result, "comment", "MT5_ORDER_REJECTED"))
            raise RuntimeError("MT5_ORDER_REJECTED:%s:%s" % (retcode, comment or "MT5_ORDER_REJECTED"))

        order_id = getattr(result, "order", None)
        if order_id is None:
            order_id = getattr(result, "deal", None)
        if order_id is None:
            raise RuntimeError("MT5_ORDER_ACCEPTED_WITHOUT_ID")
        return str(order_id)
