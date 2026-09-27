from datetime import datetime, timedelta, timezone
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


def candles(step=timedelta(hours=1)):
    start = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)
    return tuple(
        SimpleNamespace(
            timestamp=start + step * i,
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


def test_service_respects_auto_analysis_disabled():
    mt5 = FakeMT5()
    service = MT5DemoTradingService(mt5, execution_enabled=True)
    result = service.cycle(
        profile=TradingProfile(auto_analysis_enabled=False),
        d1=candles(timedelta(days=1)),
        h4=candles(timedelta(hours=4)),
        h1=candles(timedelta(hours=1)),
        m15=candles(timedelta(minutes=15)),
        m5=candles(timedelta(minutes=5)),
        now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        idempotency_key="auto-analysis-off",
    )
    assert result.reason == "AUTO_ANALYSIS_DISABLED"
    assert mt5.sent == []


def test_service_handles_mt5_account_exception():
    mt5 = FakeMT5()
    def broken_account_info():
        raise RuntimeError("connection lost")
    mt5.account_info = broken_account_info
    service = MT5DemoTradingService(mt5)
    result = service.cycle(
        profile=TradingProfile(), d1=candles(), h4=candles(), h1=candles(),
        m15=candles(), m5=candles(), now=datetime(2026, 9, 26, 12, tzinfo=timezone.utc),
        idempotency_key="broken-account",
    )
    assert result.reason == "MT5_ACCOUNT_INFO_UNAVAILABLE"


def test_service_handles_mt5_tick_exception():
    mt5 = FakeMT5()
    def broken_tick(symbol):
        raise RuntimeError("tick unavailable")
    mt5.symbol_info_tick = broken_tick
    service = MT5DemoTradingService(mt5)
    result = service.cycle(
        profile=TradingProfile(), d1=candles(), h4=candles(), h1=candles(),
        m15=candles(), m5=candles(), now=datetime(2026, 9, 26, 12, tzinfo=timezone.utc),
        idempotency_key="broken-tick",
    )
    assert result.reason == "MT5_TICK_UNAVAILABLE"
