from decimal import Decimal

import pytest

from xau_detective.demo_execution import (
    DemoOrderExecutor,
    TradeSource,
    TradeIntent,
    build_user_defined_intent,
)
from xau_detective.environment import AccountCapabilities, TradingEnvironment
from xau_detective.models import Direction, RiskResult
from xau_detective.trading_profile import TradingProfile


class FakeGateway:
    def __init__(self):
        self.calls = []

    def send_order(self, intent):
        self.calls.append(intent)
        return "DEMO-123"


def _capabilities(environment=TradingEnvironment.DEMO, enabled=True, symbol=True):
    return AccountCapabilities(environment, True, True, True, enabled, symbol, "XAUUSD", "DemoServer")


def _intent(source=TradeSource.BOT_SUGGESTION, key="order-1", executable=True):
    return TradeIntent(
        symbol="XAUUSD", direction=Direction.BUY, volume=Decimal("0.01"),
        entry=Decimal("3000"), stop_loss=Decimal("2990"), take_profit=Decimal("3020"),
        source=source, idempotency_key=key,
        risk=RiskResult(executable, Decimal("0.01"), Decimal("10"), Decimal("10"), "OK"),
    )


def test_live_is_always_rejected():
    gateway = FakeGateway()
    result = DemoOrderExecutor(gateway).execute(
        capabilities=_capabilities(TradingEnvironment.LIVE),
        profile=TradingProfile(auto_execution_enabled=True), intent=_intent())
    assert not result.submitted
    assert result.reason == "LIVE_EXECUTION_LOCKED_V1"
    assert not gateway.calls


def test_auto_execution_must_be_enabled():
    gateway = FakeGateway()
    result = DemoOrderExecutor(gateway).execute(
        capabilities=_capabilities(), profile=TradingProfile(), intent=_intent())
    assert not result.submitted
    assert result.reason == "AUTO_EXECUTION_DISABLED"


def test_non_executable_risk_is_rejected():
    gateway = FakeGateway()
    result = DemoOrderExecutor(gateway).execute(
        capabilities=_capabilities(), profile=TradingProfile(auto_execution_enabled=True),
        intent=_intent(executable=False))
    assert not result.submitted
    assert result.reason == "RISK_RESULT_NOT_EXECUTABLE"
    assert not gateway.calls


def test_duplicate_idempotency_key_is_rejected():
    gateway = FakeGateway()
    executor = DemoOrderExecutor(gateway)
    profile = TradingProfile(auto_execution_enabled=True)
    assert executor.execute(capabilities=_capabilities(), profile=profile, intent=_intent()).submitted
    duplicate = executor.execute(capabilities=_capabilities(), profile=profile, intent=_intent())
    assert not duplicate.submitted
    assert duplicate.reason == "DUPLICATE_ORDER"
    assert len(gateway.calls) == 1


def test_successful_demo_order_reaches_gateway():
    gateway = FakeGateway()
    result = DemoOrderExecutor(gateway).execute(
        capabilities=_capabilities(), profile=TradingProfile(auto_execution_enabled=True), intent=_intent())
    assert result.submitted
    assert result.order_id == "DEMO-123"
    assert gateway.calls[0].source is TradeSource.BOT_SUGGESTION


def test_user_defined_trade_requires_suggestions_off():
    risk = RiskResult(True, Decimal("0.01"), Decimal("10"), Decimal("10"), "OK")
    profile = TradingProfile(bot_suggestions_enabled=False)
    intent = build_user_defined_intent(
        symbol="XAUUSD", direction=Direction.SELL, volume=Decimal("0.01"),
        entry=Decimal("3000"), stop_loss=Decimal("3010"), take_profit=Decimal("2980"),
        risk=risk, idempotency_key="user-1", profile=profile)
    assert intent.source is TradeSource.USER_DEFINED


def test_user_defined_trade_is_not_allowed_when_suggestions_are_on():
    risk = RiskResult(True, Decimal("0.01"), Decimal("10"), Decimal("10"), "OK")
    with pytest.raises(ValueError, match="SUGGESTIONS_OFF"):
        build_user_defined_intent(
            symbol="XAUUSD", direction=Direction.BUY, volume=Decimal("0.01"),
            entry=Decimal("3000"), stop_loss=Decimal("2990"), take_profit=Decimal("3020"),
            risk=risk, idempotency_key="user-2", profile=TradingProfile())
