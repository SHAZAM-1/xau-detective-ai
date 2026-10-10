from types import SimpleNamespace
from decimal import Decimal

from xau_detective.mt5_position_manager import MT5PositionManager


class FakeMT5:
    def positions_get(self, *, symbol):
        assert symbol == "XAUUSD"
        return (
            SimpleNamespace(
                ticket=101,
                symbol="XAUUSD",
                volume=Decimal("0.02"),
                price_open=Decimal("4000.20"),
                sl=Decimal("3995.20"),
                tp=Decimal("4010.20"),
                magic=260926,
                comment="xau-detective-demo",
            ),
            SimpleNamespace(
                ticket=999,
                symbol="XAUUSD",
                volume=Decimal("0.10"),
                price_open=Decimal("4001"),
                sl=Decimal("3990"),
                tp=Decimal("4020"),
                magic=123,
                comment="other",
            ),
        )

    def orders_get(self, *, symbol):
        assert symbol == "XAUUSD"
        return (
            SimpleNamespace(
                ticket=202,
                symbol="XAUUSD",
                volume_current=Decimal("0.03"),
                price_open=Decimal("4000.10"),
                magic=260926,
                comment="xau-detective-demo",
                state=1,
            ),
        )


def test_snapshot_filters_to_bot_symbol_and_magic():
    state = MT5PositionManager(
        FakeMT5(), symbol="XAUUSD", magic=260926
    ).snapshot()

    assert [p.ticket for p in state.positions] == ["101"]
    assert [o.ticket for o in state.orders] == ["202"]
    assert state.active is True


def test_find_ticket_reconciles_position():
    manager = MT5PositionManager(FakeMT5(), symbol="XAUUSD", magic=260926)

    item = manager.find_ticket("101")

    assert item is not None
    assert item.ticket == "101"
    assert item.volume == Decimal("0.02")


def test_missing_mt5_lifecycle_apis_fail_closed():
    class NoLifecycleMT5:
        pass

    try:
        MT5PositionManager(
            NoLifecycleMT5(), symbol="XAUUSD", magic=260926
        ).snapshot()
    except RuntimeError as exc:
        assert str(exc) == "MT5_LIFECYCLE_API_UNAVAILABLE"
    else:
        raise AssertionError("expected missing lifecycle APIs to fail closed")


def test_none_positions_result_fails_closed():
    class BrokenPositionsMT5(FakeMT5):
        def positions_get(self, *, symbol):
            return None

    try:
        MT5PositionManager(
            BrokenPositionsMT5(), symbol="XAUUSD", magic=260926
        ).snapshot()
    except RuntimeError as exc:
        assert str(exc) == "MT5_POSITIONS_UNAVAILABLE"
    else:
        raise AssertionError("expected unavailable positions to fail closed")


def test_none_orders_result_fails_closed():
    class BrokenOrdersMT5(FakeMT5):
        def orders_get(self, *, symbol):
            return None

    try:
        MT5PositionManager(
            BrokenOrdersMT5(), symbol="XAUUSD", magic=260926
        ).snapshot()
    except RuntimeError as exc:
        assert str(exc) == "MT5_ORDERS_UNAVAILABLE"
    else:
        raise AssertionError("expected unavailable orders to fail closed")
