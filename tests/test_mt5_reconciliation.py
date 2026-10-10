from decimal import Decimal
from types import SimpleNamespace

from xau_detective.mt5_reconciliation import (
    MT5TradeReconciler,
    TradeLifecycleState,
)


class FakeMT5:
    DEAL_ENTRY_OUT = 1
    DEAL_REASON_SL = 4
    DEAL_REASON_TP = 5

    def __init__(self, position=None, order=None, deals=()):
        self.position = position
        self.order = order
        self.deals = deals

    def positions_get(self, *, symbol):
        return (self.position,) if self.position else ()

    def orders_get(self, *, symbol):
        return (self.order,) if self.order else ()

    def history_deals_get(self, **kwargs):
        return self.deals


def test_reconciles_open_position():
    mt5 = FakeMT5(
        position=SimpleNamespace(
            ticket=777,
            symbol="XAUUSD",
            volume=Decimal("0.01"),
            price_open=Decimal("4000"),
            sl=Decimal("3990"),
            tp=Decimal("4020"),
            magic=260926,
            comment="xau-detective-demo",
        )
    )
    result = MT5TradeReconciler(
        mt5, symbol="XAUUSD", magic=260926
    ).reconcile(order_id="123", position_id="777", requested_volume="0.01")

    assert result.state is TradeLifecycleState.POSITION_OPEN
    assert result.position_id == "777"


def test_detects_partial_fill_by_active_position_volume():
    mt5 = FakeMT5(
        position=SimpleNamespace(
            ticket=777,
            symbol="XAUUSD",
            volume=Decimal("0.01"),
            price_open=Decimal("4000"),
            sl=Decimal("3990"),
            tp=Decimal("4020"),
            magic=260926,
            comment="xau-detective-demo",
        )
    )
    result = MT5TradeReconciler(
        mt5, symbol="XAUUSD", magic=260926
    ).reconcile(order_id="123", position_id="777", requested_volume="0.02")

    assert result.state is TradeLifecycleState.PARTIAL_FILL


def test_classifies_sl_close_from_history():
    mt5 = FakeMT5(
        deals=(
            SimpleNamespace(
                entry=1,
                reason=4,
            ),
        )
    )
    result = MT5TradeReconciler(
        mt5, symbol="XAUUSD", magic=260926
    ).reconcile(order_id="123", position_id="777")

    assert result.state is TradeLifecycleState.CLOSED_BY_SL


def test_classifies_tp_close_from_history():
    mt5 = FakeMT5(
        deals=(
            SimpleNamespace(
                entry=1,
                reason=5,
            ),
        )
    )
    result = MT5TradeReconciler(
        mt5, symbol="XAUUSD", magic=260926
    ).reconcile(order_id="123", position_id="777")

    assert result.state is TradeLifecycleState.CLOSED_BY_TP


def test_missing_broker_state_is_not_found():
    result = MT5TradeReconciler(
        FakeMT5(), symbol="XAUUSD", magic=260926
    ).reconcile(order_id="123")

    assert result.state is TradeLifecycleState.NOT_FOUND


def test_unrelated_active_position_does_not_resolve_missing_order():
    unrelated_position = SimpleNamespace(
        ticket=777,
        symbol="XAUUSD",
        volume=Decimal("0.01"),
        price_open=Decimal("4000"),
        sl=Decimal("3990"),
        tp=Decimal("4020"),
        magic=260926,
        comment="xau-detective-demo",
    )
    mt5 = FakeMT5(position=unrelated_position)

    result = MT5TradeReconciler(
        mt5, symbol="XAUUSD", magic=260926
    ).reconcile(order_id="123")

    assert result.state is TradeLifecycleState.NOT_FOUND
    assert result.reason == "BROKER_STATE_NOT_FOUND"
