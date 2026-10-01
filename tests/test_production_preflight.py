from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from xau_detective.environment import AccountCapabilities, TradingEnvironment
from xau_detective.models import AccountSnapshot, BrokerSpec, ExecutionSnapshot
from xau_detective.production_preflight import run_production_preflight
from xau_detective.trading_profile import TradingProfile


def _series(start: datetime, step: timedelta) -> tuple:
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


def _inputs():
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    capabilities = AccountCapabilities(
        environment=TradingEnvironment.DEMO,
        connected=True,
        connection_healthy=True,
        trading_allowed=True,
        execution_enabled=False,
        symbol_available=True,
        symbol="XAUUSD",
        server="Demo",
    )
    account = AccountSnapshot(Decimal("1000"), Decimal("1000"), Decimal("900"))
    broker = BrokerSpec(
        symbol="XAUUSD",
        contract_size=Decimal("100"),
        volume_min=Decimal("0.01"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.01"),
        tick_size=Decimal("0.01"),
        tick_value=Decimal("1"),
        point=Decimal("0.01"),
    )
    execution = ExecutionSnapshot(Decimal("4000"), Decimal("4000.2"))
    return now, capabilities, account, broker, execution


def test_production_preflight_accepts_valid_demo_snapshot():
    now, capabilities, account, broker, execution = _inputs()
    result = run_production_preflight(
        capabilities=capabilities,
        account=account,
        broker=broker,
        execution=execution,
        profile=TradingProfile(),
        d1=_series(now - timedelta(days=20), timedelta(days=1)),
        h4=_series(now - timedelta(hours=20), timedelta(hours=1)),
        h1=_series(now - timedelta(hours=20), timedelta(hours=1)),
        m15=_series(now - timedelta(hours=5), timedelta(minutes=15)),
        m5=_series(now - timedelta(hours=2), timedelta(minutes=5)),
        now=now,
    )
    assert result.ready


def test_production_preflight_fails_closed_on_live_or_bad_prices():
    now, capabilities, account, broker, execution = _inputs()
    capabilities = AccountCapabilities(
        **{**capabilities.__dict__, "environment": TradingEnvironment.LIVE}
    )
    bad_execution = ExecutionSnapshot(Decimal("0"), Decimal("0"))
    result = run_production_preflight(
        capabilities=capabilities,
        account=account,
        broker=broker,
        execution=bad_execution,
        profile=TradingProfile(),
        d1=_series(now - timedelta(days=20), timedelta(days=1)),
        h4=_series(now - timedelta(hours=20), timedelta(hours=1)),
        h1=_series(now - timedelta(hours=20), timedelta(hours=1)),
        m15=_series(now - timedelta(hours=5), timedelta(minutes=15)),
        m5=_series(now - timedelta(hours=2), timedelta(minutes=5)),
        now=now,
    )
    assert not result.ready
    assert "DEMO_ENVIRONMENT_REQUIRED" in result.reasons
    assert "INVALID_MARKET_PRICE" in result.reasons


def test_production_preflight_rejects_open_or_future_candles():
    now, capabilities, account, broker, execution = _inputs()
    open_m5 = _series(now - timedelta(hours=2), timedelta(minutes=5)) + (
        SimpleNamespace(
            timestamp=now,
            open=Decimal("4000"),
            high=Decimal("4002"),
            low=Decimal("3998"),
            close=Decimal("4001"),
            volume=Decimal("100"),
        ),
    )
    result = run_production_preflight(
        capabilities=capabilities,
        account=account,
        broker=broker,
        execution=execution,
        profile=TradingProfile(),
        d1=_series(now - timedelta(days=20), timedelta(days=1)),
        h4=_series(now - timedelta(hours=20), timedelta(hours=1)),
        h1=_series(now - timedelta(hours=20), timedelta(hours=1)),
        m15=_series(now - timedelta(hours=5), timedelta(minutes=15)),
        m5=open_m5,
        now=now,
    )
    assert not result.ready
    assert "M5_LATEST_CANDLE_NOT_CLOSED" in result.reasons
