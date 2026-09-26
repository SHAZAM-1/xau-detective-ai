from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from xau_detective.environment import TradingEnvironment
from xau_detective.mt5_demo_service import MT5DemoTradingService
from xau_detective.trading_profile import TradingProfile


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009

    def __init__(self, trade_mode=0):
        self.account = SimpleNamespace(
            login=123,
            server="Demo",
            trade_mode=trade_mode,
            trade_allowed=True,
            balance=1000,
            equity=1000,
            margin_free=900,
        )
        self.sent = []

    def account_info(self):
        return self.account

    def terminal_info(self):
        return SimpleNamespace()

    def symbol_info(self, symbol):
        return SimpleNamespace(
            name=symbol,
            trade_contract_size=100,
            volume_min=Decimal("0.01"),
            volume_max=Decimal("100"),
            volume_step=Decimal("0.01"),
            trade_tick_size=Decimal("0.01"),
            trade_tick_value=Decimal("1"),
            point=Decimal("0.01"),
            trade_stops_level=0,
            filling_mode=1,
        )

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=Decimal("4000"), ask=Decimal("4000.2"))

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(retcode=10009, order=777, comment="done")


def candles():
    return tuple(
        SimpleNamespace(
            timestamp=datetime(2026, 9, 26, 10 + i, tzinfo=timezone.utc),
            open=Decimal("4000"),
            high=Decimal("4002"),
            low=Decimal("3998"),
            close=Decimal("4001"),
            volume=Decimal("100"),
        )
        for i in range(20)
    )


def test_service_detects_demo_and_rejects_live():
    mt5 = FakeMT5(trade_mode=2)
    service = MT5DemoTradingService(mt5, execution_enabled=True)
    result = service.cycle(
        profile=TradingProfile(),
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=datetime(2026, 9, 26, 12, tzinfo=timezone.utc),
        idempotency_key="live-1",
    )
    assert result.reason == "LIVE_EXECUTION_LOCKED_V1"
    assert mt5.sent == []


def test_service_session_tracks_demo_environment():
    mt5 = FakeMT5()
    service = MT5DemoTradingService(mt5, execution_enabled=False)
    state = service.session.refresh(
        mt5.account,
        connected=True,
        connection_healthy=True,
        execution_enabled=False,
        mt5_module=mt5,
    )
    assert state.capabilities.environment is TradingEnvironment.DEMO
    assert state.identity.login == "123"


def test_service_has_demo_executor_boundary():
    mt5 = FakeMT5()
    service = MT5DemoTradingService(mt5, execution_enabled=False)
    assert service.session.state is None
