from types import SimpleNamespace
from decimal import Decimal

import pytest

from xau_detective.demo_execution import TradeIntent, TradeSource
from xau_detective.models import Direction, RiskResult
from xau_detective.mt5_execution import MetaTrader5DemoGateway


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self, result):
        self.result = result
        self.requests = []

    def symbol_info(self, symbol):
        return SimpleNamespace(filling_mode=2)

    def order_check(self, request):
        return SimpleNamespace(retcode=0, comment="check passed")

    def order_send(self, request):
        self.requests.append(request)
        return self.result


def intent(direction=Direction.BUY):
    return TradeIntent(
        symbol="XAUUSD",
        direction=direction,
        volume=Decimal("0.01"),
        entry=Decimal("4000.10"),
        stop_loss=Decimal("3995.10"),
        take_profit=Decimal("4010.10"),
        source=TradeSource.BOT_SUGGESTION,
        idempotency_key="test-1",
        risk=RiskResult(
            executable=True,
            volume=Decimal("0.01"),
            risk_amount=Decimal("1"),
            estimated_loss=Decimal("0.95"),
            reason="OK",
        ),
    )


def test_build_buy_request_maps_trade_intent():
    mt5 = FakeMT5(SimpleNamespace(retcode=10009, order=123, comment="done"))
    gateway = MetaTrader5DemoGateway(mt5, magic=42, deviation=7)
    request = gateway.build_request(intent())

    assert request["action"] == mt5.TRADE_ACTION_DEAL
    assert request["symbol"] == "XAUUSD"
    assert request["type"] == mt5.ORDER_TYPE_BUY
    assert request["volume"] == 0.01
    assert request["price"] == 4000.10
    assert request["sl"] == 3995.10
    assert request["tp"] == 4010.10
    assert request["magic"] == 42
    assert request["deviation"] == 7
    assert request["type_filling"] == mt5.ORDER_FILLING_IOC


def test_send_order_returns_mt5_order_id():
    mt5 = FakeMT5(SimpleNamespace(retcode=10009, order=123, comment="done"))
    gateway = MetaTrader5DemoGateway(mt5)
    assert gateway.send_order(intent()) == "123"
    assert len(mt5.requests) == 1


def test_send_order_rejects_broker_retcode():
    mt5 = FakeMT5(SimpleNamespace(retcode=10030, order=0, comment="invalid stops"))
    gateway = MetaTrader5DemoGateway(mt5)
    with pytest.raises(RuntimeError, match="MT5_ORDER_REJECTED:10030"):
        gateway.send_order(intent())


def test_send_order_rejects_missing_symbol_info():
    class NoSymbolMT5(FakeMT5):
        def symbol_info(self, symbol):
            return None

    mt5 = NoSymbolMT5(SimpleNamespace(retcode=10009, order=123))
    gateway = MetaTrader5DemoGateway(mt5)
    with pytest.raises(ValueError, match="SYMBOL_INFO_UNAVAILABLE"):
        gateway.send_order(intent())


def test_no_trade_cannot_build_request():
    mt5 = FakeMT5(SimpleNamespace(retcode=10009, order=123))
    gateway = MetaTrader5DemoGateway(mt5)
    with pytest.raises(ValueError, match="NO_TRADE_DIRECTION"):
        gateway.build_request(intent(Direction.NO_TRADE))


def test_send_order_detailed_exposes_order_deal_volume_and_price():
    mt5 = FakeMT5(
        SimpleNamespace(
            retcode=10009,
            order=123,
            deal=456,
            volume=0.01,
            price=4000.25,
            comment="done",
        )
    )
    response = MetaTrader5DemoGateway(mt5).send_order_detailed(intent())

    assert response.accepted is True
    assert response.order_id == "123"
    assert response.deal_id == "456"
    assert response.filled_volume == Decimal("0.01")
    assert response.price == Decimal("4000.25")
    assert response.retcode == 10009


def test_build_request_maps_filling_bitmask_to_fok_enum():
    class FokMT5(FakeMT5):
        def symbol_info(self, symbol):
            return SimpleNamespace(filling_mode=self.SYMBOL_FILLING_FOK)

    mt5 = FokMT5(SimpleNamespace(retcode=10009, order=123))
    request = MetaTrader5DemoGateway(mt5).build_request(intent())
    assert request["type_filling"] == mt5.ORDER_FILLING_FOK


def test_build_request_rejects_unsupported_filling_mode():
    class UnsupportedMT5(FakeMT5):
        def symbol_info(self, symbol):
            return SimpleNamespace(filling_mode=8)

    mt5 = UnsupportedMT5(SimpleNamespace(retcode=10009, order=123))
    with pytest.raises(ValueError, match="NO_SUPPORTED_MARKET_FILLING_MODE"):
        MetaTrader5DemoGateway(mt5).build_request(intent())



def test_send_order_rejects_zero_order_and_deal_tickets():
    mt5 = FakeMT5(
        SimpleNamespace(retcode=10009, order=0, deal=0, comment="done")
    )
    gateway = MetaTrader5DemoGateway(mt5)
    with pytest.raises(RuntimeError, match="MT5_ORDER_ACCEPTED_WITHOUT_ID"):
        gateway.send_order(intent())


def test_send_order_uses_valid_deal_ticket_when_order_ticket_is_zero():
    mt5 = FakeMT5(
        SimpleNamespace(retcode=10009, order=0, deal=456, comment="done")
    )
    response = MetaTrader5DemoGateway(mt5).send_order_detailed(intent())
    assert response.order_id is None
    assert response.deal_id == "456"



def test_build_request_fails_closed_when_filling_mode_is_missing():
    class MissingFillingModeMT5(FakeMT5):
        def symbol_info(self, symbol):
            return SimpleNamespace()

    mt5 = MissingFillingModeMT5(SimpleNamespace(retcode=10009, order=123))
    with pytest.raises(ValueError, match="SYMBOL_FILLING_MODE_UNAVAILABLE"):
        MetaTrader5DemoGateway(mt5).build_request(intent())


def test_send_order_fails_closed_when_order_check_api_is_missing():
    class NoOrderCheckMT5(FakeMT5):
        order_check = None

    mt5 = NoOrderCheckMT5(SimpleNamespace(retcode=10009, order=123))
    with pytest.raises(RuntimeError, match="MT5_ORDER_CHECK_UNAVAILABLE"):
        MetaTrader5DemoGateway(mt5).send_order(intent())
    assert mt5.requests == []


def test_order_check_rejection_prevents_order_send():
    class RejectOrderCheckMT5(FakeMT5):
        def order_check(self, request):
            return SimpleNamespace(retcode=10016, comment="invalid stops")

    mt5 = RejectOrderCheckMT5(SimpleNamespace(retcode=10009, order=123))
    with pytest.raises(RuntimeError, match="MT5_ORDER_CHECK_REJECTED:10016"):
        MetaTrader5DemoGateway(mt5).send_order(intent())
    assert mt5.requests == []
