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


def test_gate_rejects_without_explicit_execution_opt_in():
    caps = AccountCapabilities(
        environment=TradingEnvironment.DEMO, connected=True, connection_healthy=True,
        trading_allowed=True, execution_enabled=False, symbol_available=True, symbol="XAUUSD",
    )
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=caps, account_info=account(), symbol_info=symbol(), intent=intent(),
    )
    assert result.reason == "DEMO_EXECUTION_NOT_ENABLED"


def test_gate_rejects_non_finite_trade_intent_values_without_raising():
    invalid = TradeIntent(
        **{**intent().__dict__, "volume": Decimal("NaN")}
    )
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=symbol(), intent=invalid,
    )
    assert result.reason == "INVALID_EXECUTION_NUMERIC_VALUE"


def test_gate_rejects_non_finite_broker_prices_without_raising():
    s = symbol()
    s.ask = float("inf")
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(),
    )
    assert result.reason == "INVALID_EXECUTION_NUMERIC_VALUE"


def test_gate_rejects_non_finite_account_margin_without_raising():
    a = SimpleNamespace(margin_free=float("nan"))
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=a,
        symbol_info=symbol(), intent=intent(),
    )
    assert result.reason == "INVALID_EXECUTION_NUMERIC_VALUE"


def test_gate_rejects_non_finite_margin_calculation_output():
    class InvalidMargin(FakeMT5):
        def order_calc_margin(self, action, symbol, volume, price):
            return float("nan")

    result = BrokerExecutionGate().validate(
        mt5=InvalidMargin(), capabilities=capabilities(), account_info=account(),
        symbol_info=symbol(), intent=intent(),
    )
    assert result.reason == "MARGIN_CALCULATION_FAILED"


def test_gate_rejects_close_only_symbol_mode():
    s = symbol()
    s.trade_mode = 3
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(),
    )
    assert result.reason == "SYMBOL_CLOSE_ONLY"


def test_gate_rejects_sell_when_symbol_is_long_only():
    s = symbol()
    s.trade_mode = 1
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(Direction.SELL),
    )
    assert result.reason == "SYMBOL_DIRECTION_NOT_ALLOWED"


def test_gate_rejects_buy_when_symbol_is_short_only():
    s = symbol()
    s.trade_mode = 2
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(Direction.BUY),
    )
    assert result.reason == "SYMBOL_DIRECTION_NOT_ALLOWED"


def test_gate_rejects_unknown_symbol_trade_mode():
    s = symbol()
    s.trade_mode = 99
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(),
    )
    assert result.reason == "UNSUPPORTED_SYMBOL_TRADE_MODE"


def test_gate_fails_closed_when_symbol_order_mode_is_missing():
    s = symbol()
    del s.order_mode
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(),
    )
    assert result.reason == "SYMBOL_ORDER_MODE_UNAVAILABLE"


def test_gate_rejects_malformed_symbol_order_mode():
    s = symbol()
    s.order_mode = float("nan")
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(),
    )
    assert result.reason == "INVALID_SYMBOL_ORDER_MODE"


def test_gate_rejects_symbol_without_market_order_permission():
    s = symbol()
    s.order_mode = 2
    result = BrokerExecutionGate().validate(
        mt5=FakeMT5(), capabilities=capabilities(), account_info=account(),
        symbol_info=s, intent=intent(),
    )
    assert result.reason == "MARKET_ORDERS_NOT_ALLOWED"
