from decimal import Decimal

from xau_detective.demo_runner import build_demo_proposal, calculate_demo_risk_budget
from xau_detective.environment import AccountCapabilities, TradingEnvironment
from xau_detective.models import AccountSnapshot, BrokerSpec, ExecutionSnapshot
from xau_detective.trading_profile import TradingProfile


def _fixtures():
    account = AccountSnapshot(Decimal(1000), Decimal(1000), Decimal(900))
    broker = BrokerSpec(
        symbol="XAUUSD",
        contract_size=Decimal(100),
        volume_min=Decimal("0.01"),
        volume_max=Decimal(100),
        volume_step=Decimal("0.01"),
        tick_size=Decimal("0.01"),
        tick_value=Decimal(1),
        point=Decimal("0.01"),
    )
    execution = ExecutionSnapshot(Decimal(3000), Decimal("3000.10"))
    capabilities = AccountCapabilities(
        environment=TradingEnvironment.DEMO,
        connected=True,
        connection_healthy=True,
        trading_allowed=True,
        execution_enabled=True,
        symbol_available=True,
        symbol="XAUUSD",
        server="DemoServer",
    )
    return account, broker, execution, capabilities


def test_demo_runner_stops_when_execution_capability_is_missing():
    account, broker, execution, capabilities = _fixtures()
    blocked = AccountCapabilities(
        environment=capabilities.environment,
        connected=capabilities.connected,
        connection_healthy=capabilities.connection_healthy,
        trading_allowed=capabilities.trading_allowed,
        execution_enabled=False,
        symbol_available=capabilities.symbol_available,
        symbol=capabilities.symbol,
        server=capabilities.server,
    )
    result = build_demo_proposal(
        capabilities=blocked,
        account=account,
        broker=broker,
        execution=execution,
        profile=TradingProfile(),
        d1=(), h4=(), h1=(), m15=(), m5=(),
    )
    assert not result.allowed
    assert result.analysis is not None
    assert result.reason == "DATA_QUALITY:D1:NO_CANDLES"


def test_demo_risk_budget_uses_equity():
    account = AccountSnapshot(Decimal(900), Decimal(1000), Decimal(800))
    assert calculate_demo_risk_budget(account, Decimal("0.01")) == Decimal(10)


def test_demo_proposal_can_analyze_when_execution_is_disabled():
    account, broker, execution, capabilities = _fixtures()
    blocked = AccountCapabilities(
        environment=TradingEnvironment.DEMO, connected=True, connection_healthy=True,
        trading_allowed=True, execution_enabled=False, symbol_available=True, symbol="XAUUSD"
    )
    result = build_demo_proposal(
        capabilities=blocked, account=account, broker=broker, execution=execution,
        profile=TradingProfile(), d1=(), h4=(), h1=(), m15=(), m5=()
    )
    assert result.analysis is not None
    assert result.reason == "DATA_QUALITY:D1:NO_CANDLES"
