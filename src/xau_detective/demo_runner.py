"""Safe MT5 Demo runner boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
from .environment import AccountCapabilities, TradingEnvironment, environment_reason
from .models import AccountSnapshot, BrokerSpec, ExecutionSnapshot
from .mt5_market_hours import pepperstone_gold_gap_is_expected
from .pipeline import AnalysisConfig, MarketAnalysis, analyze_market
from .trading_profile import TradingProfile

class MT5Gateway(Protocol):
    def account_info(self) -> Any: ...
    def symbol_info(self, symbol: str) -> Any: ...
    def symbol_tick(self, symbol: str) -> Any: ...

@dataclass(frozen=True)
class DemoTradeProposal:
    allowed: bool
    reason: str
    analysis: MarketAnalysis | None
    account: AccountSnapshot | None = None
    broker: BrokerSpec | None = None
    execution: ExecutionSnapshot | None = None
    environment: AccountCapabilities | None = None

def build_demo_proposal(
    *,
    capabilities: AccountCapabilities,
    account: AccountSnapshot,
    broker: BrokerSpec,
    execution: ExecutionSnapshot,
    profile: TradingProfile,
    d1: tuple,
    h4: tuple,
    h1: tuple,
    m15: tuple,
    m5: tuple,
    now=None,
) -> DemoTradeProposal:
    profile.validate()
    if capabilities.environment is not TradingEnvironment.DEMO:
        return DemoTradeProposal(False, environment_reason(capabilities), None, account, broker, execution, capabilities)
    if not capabilities.connected or not capabilities.connection_healthy:
        return DemoTradeProposal(False, environment_reason(capabilities), None, account, broker, execution, capabilities)
    if not capabilities.symbol_available:
        return DemoTradeProposal(False, "SYMBOL_UNAVAILABLE", None, account, broker, execution, capabilities)
    analysis = analyze_market(
        d1=d1,
        h4=h4,
        h1=h1,
        m15=m15,
        m5=m5,
        account=account,
        broker=broker,
        execution=execution,
        config=AnalysisConfig.from_profile(profile),
        now=now,
        gap_is_expected_for_timeframe=lambda previous, current, timeframe: (
            pepperstone_gold_gap_is_expected(previous, current, timeframe)
        ),
    )
    return DemoTradeProposal(
        allowed=analysis.decision.direction.value != "NO_TRADE" and analysis.decision.risk is not None and analysis.decision.risk.executable,
        reason=analysis.decision.reason, analysis=analysis, account=account, broker=broker, execution=execution, environment=capabilities)
