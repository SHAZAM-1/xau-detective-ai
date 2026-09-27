from decimal import Decimal
from types import SimpleNamespace

from xau_detective.broker_execution_gate import BrokerExecutionGate
from xau_detective.demo_execution import TradeIntent, TradeSource
from xau_detective.environment import AccountCapabilities, TradingEnvironment
from xau_detective.models import Direction, RiskResult


class FakeMT5:
    SYMBOL_ORDER_MARKET = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def order_calc_margin(self, action, symbol, volume, price):
        return 5.0


def intent(direction=Direction.BUY):
    return TradeIntent(
        symbol="XAUUSD",
        direction=direction,
        volume=Decimal("0.01"),
        entry=Decimal("4000.10") if direction is Direction.BUY else Decimal("4000.00"),
        stop_loss=Decimal("3995.10") if direction is Direction.BUY else Decimal("4005.00"),
        take_profit=Decimal("4010.10") if direction is Direction.BUY else Decimal("3990.00"),
        source=TradeSource.BOT_SUGGESTION,
        idempotency_key="gate-test",
        risk=RiskResult(True, Decimal("0.01"), Decimal("1"), Decimal("0.95"), "OK"),
    )


def capabilities():
    return AccountCapabilities(
        environment=TradingEnvironment.DEMO,
        connected=True,
        connection_healthy=True,
        trading_allowed=True,
        execution_enabled=True,
        symbol_available=True,
        symbol="XAUUSD",
    )


def symbol():
    return SimpleNamespace(
        trade_mode=4,
        order_mode=1,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        bid=4000.0,
        ask=4000.1,
        point=0.01,
        trade_stops_level=10,
        trade_freeze_level=0,
    )


def account():
    return SimpleNamespace(margin_free=100.0)


def test_gate_accepts_valid_demo_market_order():
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(),
        capabilities=capabilities(),
        account_info=account(),
        symbol_info=symbol(),
        intent=intent(),
    )
    assert result == type(result)(True, "OK")


def test_gate_rejects_wrong_entry_side():
    i = intent()
    i = TradeIntent(**{**i.__dict__, "entry": Decimal("3999.0")})
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=symbol(), intent=i,
    )
    assert result.reason == "STALE_OR_WRONG_SIDE_ENTRY"


def test_gate_rejects_spread_limit():
    s = symbol()
    s.ask = 4001.0
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(), max_spread=Decimal("0.20"),
    )
    assert result.reason == "SPREAD_LIMIT_EXCEEDED"


def test_gate_rejects_invalid_buy_sl_tp():
    i = intent()
    i = TradeIntent(**{**i.__dict__, "stop_loss": Decimal("4001.0")})
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=symbol(), intent=i,
    )
    assert result.reason == "INVALID_BUY_SL_TP"


def test_gate_rejects_insufficient_margin():
    class TightMargin(FakeMT5):
        def order_calc_margin(self, action, symbol, volume, price):
            return 100.0

    result = BrokerExecutionGate().validate(
        mt5=TightMargin(), capabilities=capabilities(), account_info=account(),
        symbol_info=symbol(), intent=intent(),
    )
    assert result.reason == "INSUFFICIENT_FREE_MARGIN"
