"""Deterministic MT5 Demo trade lifecycle reconciliation.

This module reads broker state after submission and classifies what actually
happened. It never opens, closes, or modifies a trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from typing import Any

from .mt5_position_manager import LifecycleSnapshot, MT5PositionManager


class TradeLifecycleState(str, Enum):
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    PENDING_ORDER = "PENDING_ORDER"
    POSITION_OPEN = "POSITION_OPEN"
    PARTIAL_FILL = "PARTIAL_FILL"
    CLOSED_BY_SL = "CLOSED_BY_SL"
    CLOSED_BY_TP = "CLOSED_BY_TP"
    CLOSED_MANUALLY = "CLOSED_MANUALLY"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class ReconciliationResult:
    state: TradeLifecycleState
    order_id: str | None
    position_id: str | None
    filled_volume: str | None
    reason: str


class MT5TradeReconciler:
    """Reconcile one Demo order against current and recent MT5 broker state."""

    def __init__(self, mt5_module: Any, *, symbol: str, magic: int) -> None:
        self._mt5 = mt5_module
        self._positions = MT5PositionManager(
            mt5_module, symbol=symbol, magic=magic
        )

    @staticmethod
    def _as_str(value: Any) -> str | None:
        return None if value is None else str(value)

    def _history_deals(self, order_id: str | None, position_id: str | None) -> tuple[Any, ...]:
        getter = getattr(self._mt5, "history_deals_get", None)
        if not callable(getter):
            return ()
        try:
            if position_id is not None:
                rows = getter(position=int(position_id))
            elif order_id is not None:
                rows = getter(order=int(order_id))
            else:
                return ()
        except (TypeError, ValueError):
            return ()
        return tuple(rows or ())

    def _classify_closed(self, deals: tuple[Any, ...]) -> TradeLifecycleState:
        if not deals:
            return TradeLifecycleState.NOT_FOUND

        reasons = {
            int(getattr(self._mt5, "DEAL_REASON_SL", 4)): TradeLifecycleState.CLOSED_BY_SL,
            int(getattr(self._mt5, "DEAL_REASON_TP", 5)): TradeLifecycleState.CLOSED_BY_TP,
        }
        exit_flag = getattr(self._mt5, "DEAL_ENTRY_OUT", 1)
        exit_deals = [deal for deal in deals if getattr(deal, "entry", None) == exit_flag]
        if not exit_deals:
            return TradeLifecycleState.NOT_FOUND

        return reasons.get(
            int(getattr(exit_deals[-1], "reason", -1)),
            TradeLifecycleState.CLOSED_MANUALLY,
        )

    def reconcile(
        self,
        *,
        order_id: str | None = None,
        position_id: str | None = None,
        requested_volume: str | None = None,
    ) -> ReconciliationResult:
        snapshot: LifecycleSnapshot = self._positions.snapshot()

        if position_id is not None:
            position = self._positions.find_ticket(position_id)
            if position is not None and hasattr(position, "volume"):
                volume = str(position.volume)
                if (
                    requested_volume is not None
                    and Decimal(volume) != Decimal(requested_volume)
                ):
                    return ReconciliationResult(
                        TradeLifecycleState.PARTIAL_FILL,
                        order_id,
                        position.ticket,
                        volume,
                        "ACTIVE_POSITION_VOLUME_DIFFERS_FROM_REQUEST",
                    )
                return ReconciliationResult(
                    TradeLifecycleState.POSITION_OPEN,
                    order_id,
                    position.ticket,
                    volume,
                    "POSITION_FOUND",
                )

        if order_id is not None:
            order = self._positions.find_ticket(order_id)
            if order is not None and not hasattr(order, "stop_loss"):
                return ReconciliationResult(
                    TradeLifecycleState.PENDING_ORDER,
                    order_id,
                    None,
                    str(order.volume),
                    "PENDING_ORDER_FOUND",
                )

        deals = self._history_deals(order_id, position_id)
        closed_state = self._classify_closed(deals)
        if closed_state is not TradeLifecycleState.NOT_FOUND:
            return ReconciliationResult(
                closed_state,
                order_id,
                position_id,
                None,
                "HISTORY_DEAL_FOUND",
            )

        if order_id is not None and snapshot.active:
            return ReconciliationResult(
                TradeLifecycleState.ORDER_ACCEPTED,
                order_id,
                position_id,
                None,
                "ORDER_ACCEPTED_NO_ACTIVE_MATCH",
            )

        return ReconciliationResult(
            TradeLifecycleState.NOT_FOUND,
            order_id,
            position_id,
            None,
            "BROKER_STATE_NOT_FOUND",
        )
