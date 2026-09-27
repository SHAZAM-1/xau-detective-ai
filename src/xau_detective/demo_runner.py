"""Safe MT5 Demo runner boundary.

This module deliberately stops at a broker-validated trade proposal in the
first implementation. Sending an order is a separate, explicit capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from .environment import AccountCapabilities, can_execute_orders, environment_reason
from .models import AccountSnapshot, BrokerSpec, ExecutionSnapshot
from .pipeline import AnalysisConfig, MarketAnalysis, analyze_market
from .trading_profile import TradingProfile


class MT5Gateway(Protocol):
    """Minimal gateway contract required by the Demo runner."""

    def account_info(self) -> Any: ...

    def symbol_info(self, symbol: str) -> Any: ...

    def symbol_tick(self, symbol: str) -> Any: ...


@dataclass(frozen=True)


class DemoTradeProposal:
    """Auditable proposal returned before any Demo order is sent."""

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
    """Analyze a live Demo snapshot without placing an order."""
    profile.validate()
    if not can_execute_orders(capabilities):
        return DemoTradeProposal(
            allowed=False,
            reason=environment_reason(capabilities),
            analysis=None,
            account=account,
            broker=broker,
            execution=execution,
            environment=capabilities,
        )

    config = AnalysisConfig.from_profile(profile)
    analysis = analyze_market(
        d1=d1,
        h4=h4,
        h1=h1,
        m15=m15,
        m5=m5,
        account=account,
        broker=broker,
        execution=execution,
        config=config,
        now=now,
    )
    return DemoTradeProposal(
        allowed=analysis.decision.direction.value != "NO_TRADE"
        and analysis.decision.risk is not None
        and analysis.decision.risk.executable,
        reason=analysis.decision.reason,
        analysis=analysis,
        account=account,
        broker=broker,
        execution=execution,
        environment=capabilities,
    )


def calculate_demo_risk_budget(account: AccountSnapshot, risk_fraction: Decimal) -> Decimal:
    """Expose the user's monetary risk budget for the Demo UI/audit log."""
    if risk_fraction <= 0 or risk_fraction >= 1:
        raise ValueError("risk_fraction must be greater than 0 and below 1")
    return account.equity * risk_fraction
