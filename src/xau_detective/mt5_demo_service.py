"""End-to-end MT5 Demo trading orchestration.

The service refreshes account/environment state, reads broker constraints and
market price, runs the deterministic analysis/risk gate, then sends only
validated Demo orders. Live execution is rejected by policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .demo_execution import DemoOrderExecutor, DemoOrderResult, TradeIntent, TradeSource
from .environment import TradingEnvironment
from .mt5_adapter import (
    account_snapshot_from_mt5,
    broker_spec_from_mt5,
    execution_snapshot_from_mt5,
)
from .mt5_execution import MetaTrader5DemoGateway
from .mt5_session import MT5SessionMonitor
from .pipeline import MarketAnalysis
from .trading_profile import TradingProfile


@dataclass(frozen=True)
class DemoCycleResult:
    session_changed: bool
    analysis: MarketAnalysis | None
    order: DemoOrderResult | None
    reason: str


class MT5DemoTradingService:
    """Connects session detection, analysis, risk gating and Demo execution."""

    def __init__(
        self,
        mt5_module: Any,
        *,
        symbol: str = "XAUUSD",
        execution_enabled: bool = False,
        magic: int = 260926,
    ) -> None:
        self._mt5 = mt5_module
        self._symbol = symbol
        self._execution_enabled = execution_enabled
        self._session = MT5SessionMonitor()
        self._executor = DemoOrderExecutor(
            MetaTrader5DemoGateway(mt5_module, magic=magic)
        )

    @property
    def session(self) -> MT5SessionMonitor:
        return self._session

    def cycle(
        self,
        *,
        profile: TradingProfile,
        d1: tuple,
        h4: tuple,
        h1: tuple,
        m15: tuple,
        m5: tuple,
        now=None,
        idempotency_key: str,
        user_intent: TradeIntent | None = None,
    ) -> DemoCycleResult:
        account_info = self._mt5.account_info()
        if account_info is None:
            return DemoCycleResult(False, None, None, "MT5_ACCOUNT_INFO_UNAVAILABLE")

        terminal_info = getattr(self._mt5, "terminal_info", lambda: None)()
        connected = terminal_info is not None
        session_before = self._session.state.identity if self._session.state else None

        symbol_info = self._mt5.symbol_info(self._symbol)
        symbol_available = symbol_info is not None
        tick = self._mt5.symbol_info_tick(self._symbol) if symbol_available else None
        if tick is None:
            return DemoCycleResult(False, None, None, "MT5_TICK_UNAVAILABLE")

        state = self._session.refresh(
            account_info,
            connected=connected,
            connection_healthy=connected,
            execution_enabled=self._execution_enabled,
            symbol=self._symbol,
            symbol_available=symbol_available,
            mt5_module=self._mt5,
        )
        changed = session_before != state.identity

        if state.capabilities.environment is not TradingEnvironment.DEMO:
            return DemoCycleResult(changed, None, None, "LIVE_EXECUTION_LOCKED_V1")

        account = account_snapshot_from_mt5(account_info)
        broker = broker_spec_from_mt5(symbol_info)
        execution = execution_snapshot_from_mt5(tick)

        from .demo_runner import build_demo_proposal

        proposal = build_demo_proposal(
            capabilities=state.capabilities,
            account=account,
            broker=broker,
            execution=execution,
            profile=profile,
            d1=d1,
            h4=h4,
            h1=h1,
            m15=m15,
            m5=m5,
            now=now,
        )
        if not proposal.allowed or proposal.analysis is None:
            return DemoCycleResult(changed, proposal.analysis, None, proposal.reason)

        analysis = proposal.analysis
        decision = analysis.decision
        if decision.scenario is None or decision.risk is None:
            return DemoCycleResult(changed, analysis, None, "NO_EXECUTABLE_SCENARIO")

        if user_intent is None:
            direction = decision.direction
            source = TradeSource.BOT_SUGGESTION
            intent = TradeIntent(
                symbol=self._symbol,
                direction=direction,
                volume=decision.risk.volume,
                entry=execution.ask if direction.value == "BUY" else execution.bid,
                stop_loss=analysis.stop_loss,
                take_profit=analysis.take_profit,
                source=source,
                idempotency_key=idempotency_key,
                risk=decision.risk,
            )
        else:
            intent = user_intent

        order = self._executor.execute(
            capabilities=state.capabilities,
            profile=profile,
            intent=intent,
        )
        return DemoCycleResult(changed, analysis, order, order.reason)
