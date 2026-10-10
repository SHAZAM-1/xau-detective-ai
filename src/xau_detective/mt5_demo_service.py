"""End-to-end MT5 Demo trading orchestration.

The service refreshes account/environment state, reads broker constraints and
market price, runs the deterministic analysis/risk gate, then sends only
validated Demo orders. Live execution is rejected by policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .adaptive_runtime_agent import AdaptiveRuntimeAgent, MT5RuntimeObservation
from .audit_log import AuditEvent, AuditLog, InMemoryAuditLog
from .broker_execution_gate import BrokerExecutionGate
from .demo_execution import DemoOrderExecutor, DemoOrderResult, TradeIntent, TradeSource
from .environment import TradingEnvironment
from .mt5_adapter import (
    account_snapshot_from_mt5,
    broker_spec_from_mt5,
    execution_snapshot_from_mt5,
)
from .mt5_execution import MetaTrader5DemoGateway
from .mt5_position_manager import LifecycleSnapshot, MT5PositionManager
from .mt5_reconciliation import MT5TradeReconciler, ReconciliationResult, TradeLifecycleState
from .mt5_session import MT5SessionMonitor
from .pipeline import MarketAnalysis
from .models import Direction
from .project_guardian import ProjectGuardian
from .production_preflight import run_production_preflight
from .runtime_health import RuntimeHealthTracker
from .trade_journal import InMemoryTradeJournal, TradeJournal, TradeJournalEntry, journal_entry_from_intent
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
        journal: TradeJournal | None = None,
        audit_log: AuditLog | None = None,
        adaptive_agent: AdaptiveRuntimeAgent | None = None,
        project_guardian: ProjectGuardian | None = None,
    ) -> None:
        self._mt5 = mt5_module
        self._symbol = symbol
        self._execution_enabled = execution_enabled
        self._magic = magic
        self._session = MT5SessionMonitor()
        self._executor = DemoOrderExecutor(
            MetaTrader5DemoGateway(mt5_module, magic=magic)
        )
        self._execution_gate = BrokerExecutionGate()
        self._journal = journal or InMemoryTradeJournal()
        self._audit = audit_log or InMemoryAuditLog()
        self._adaptive = adaptive_agent or AdaptiveRuntimeAgent(self._audit)
        self._guardian = project_guardian or ProjectGuardian(self._audit)
        self._positions = MT5PositionManager(mt5_module, symbol=symbol, magic=magic)
        self._health = RuntimeHealthTracker()

    @property
    def audit_log(self) -> AuditLog:
        """Return the structured audit stream for this service."""
        return self._audit

    def _finish(
        self,
        *,
        trace_id: str,
        now: datetime,
        result: DemoCycleResult,
        details: dict[str, Any] | None = None,
    ) -> DemoCycleResult:
        order = result.order
        intent = order.intent if order is not None else None
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="cycle_finished",
                status="SUCCESS" if result.reason in {"DEMO_ORDER_SUBMITTED", "AUTO_ANALYSIS_DISABLED"} else "REJECTED",
                reason=result.reason,
                symbol=intent.symbol if intent else self._symbol,
                direction=intent.direction.value if intent else None,
                volume=intent.volume if intent else None,
                entry=intent.entry if intent else None,
                stop_loss=intent.stop_loss if intent else None,
                take_profit=intent.take_profit if intent else None,
                order_id=order.order_id if order else None,
                details=details or {},
            )
        )
        return result

    def _audit_analysis(self, *, trace_id: str, now: datetime, analysis: MarketAnalysis) -> None:
        """Record the analysis trail that explains a trade or NO_TRADE decision."""
        decision = analysis.decision
        scenario = decision.scenario
        risk = decision.risk
        self._audit.append(AuditEvent(timestamp=now, trace_id=trace_id, event="analysis_started", status="COMPLETED", symbol=self._symbol, details={"session": analysis.session}))
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="evidence",
                status="RECORDED",
                symbol=self._symbol,
                details={
                    "supporting": list(analysis.evidence_supporting),
                    "contradicting": list(analysis.evidence_contradicting),
                    "warnings": list(analysis.evidence_warnings),
                },
            )
        )
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="pattern_analysis",
                status="RECORDED",
                symbol=self._symbol,
                details={
                    "candlestick_patterns": list(analysis.candlestick_patterns),
                    "price_action_moves": list(analysis.price_action_moves),
                },
            )
        )
        if risk is not None:
            self._audit.append(
                AuditEvent(
                    timestamp=now,
                    trace_id=trace_id,
                    event="risk_assessment",
                    status="EXECUTABLE" if risk.executable else "VETOED",
                    symbol=self._symbol,
                    direction=decision.direction.value,
                    volume=risk.volume,
                    details={
                        "risk_amount": risk.risk_amount,
                        "estimated_loss": risk.estimated_loss,
                        "reason": risk.reason,
                    },
                )
            )
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="decision",
                status=decision.direction.value,
                reason=decision.reason,
                symbol=self._symbol,
                direction=decision.direction.value,
                entry=analysis.entry,
                stop_loss=analysis.stop_loss,
                take_profit=analysis.take_profit,
                details={
                    "setup_score": decision.setup_score,
                    "scenario_direction": scenario.direction.value if scenario else None,
                    "scenario_evidence": list(scenario.evidence) if scenario else [],
                    "scenario_invalidation": scenario.invalidation if scenario else None,
                    "scenario_target": scenario.target if scenario else None,
                    "reward_risk": analysis.reward_risk,
                },
            )
        )
        if decision.direction is Direction.NO_TRADE:
            self._audit.append(
                AuditEvent(
                    timestamp=now,
                    trace_id=trace_id,
                    event="no_trade",
                    status="BLOCKED",
                    reason=decision.reason,
                    symbol=self._symbol,
                    details={
                        "setup_score": decision.setup_score,
                        "evidence_supporting": list(analysis.evidence_supporting),
                        "evidence_contradicting": list(analysis.evidence_contradicting),
                        "evidence_warnings": list(analysis.evidence_warnings),
                    },
                )
            )

    def _audit_rejection(
        self,
        *,
        trace_id: str,
        now: datetime,
        reason: str,
        event: str = "rejection",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record every cycle gate that prevents execution."""
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event=event,
                status="BLOCKED",
                reason=reason,
                symbol=self._symbol,
                details=details or {},
            )
        )

    @property
    def session(self) -> MT5SessionMonitor:
        return self._session

    def lifecycle(self) -> LifecycleSnapshot:
        """Return the latest broker-reported orders and positions for this bot."""
        snapshot = self._positions.snapshot()
        self._health.reconciliation_checked(datetime.now(UTC), active_exposure=snapshot.active)
        return snapshot

    def recover_pending_submission(
        self,
        *,
        idempotency_key: str,
        order_id: str | None = None,
        position_id: str | None = None,
        requested_volume: str | None = None,
        now: datetime | None = None,
    ) -> ReconciliationResult:
        """Reconcile a durable pending submission without sending a new order."""
        timestamp = now or datetime.now(UTC)
        pending = self._journal.latest_for_idempotency_key(idempotency_key)
        if pending is None or pending.status != "PENDING_SUBMISSION":
            raise ValueError("PENDING_SUBMISSION_NOT_FOUND")

        reconciler = MT5TradeReconciler(
            self._mt5, symbol=pending.symbol, magic=self._magic
        )
        result = reconciler.reconcile(
            order_id=order_id or pending.order_id,
            position_id=position_id,
            requested_volume=requested_volume or str(pending.volume),
        )

        if result.state is TradeLifecycleState.NOT_FOUND:
            status = "RECOVERY_REQUIRED"
            reason = "BROKER_STATE_NOT_FOUND_MANUAL_RECONCILIATION_REQUIRED"
        else:
            status = f"RECOVERED_{result.state.value}"
            reason = result.reason

        self._journal.append(
            TradeJournalEntry(
                timestamp=timestamp,
                idempotency_key=pending.idempotency_key,
                symbol=pending.symbol,
                direction=pending.direction,
                volume=pending.volume,
                entry=pending.entry,
                stop_loss=pending.stop_loss,
                take_profit=pending.take_profit,
                source=pending.source,
                status=status,
                reason=reason,
                order_id=result.order_id or pending.order_id,
            )
        )
        self._health.reconciliation_checked(timestamp, active_exposure=self._positions.snapshot().active)
        self._health.reason(reason)
        self._audit.append(
            AuditEvent(
                timestamp=timestamp,
                trace_id=idempotency_key,
                event="recovery",
                status="RECOVERED" if result.state is not TradeLifecycleState.NOT_FOUND else "REQUIRES_REVIEW",
                reason=reason,
                symbol=pending.symbol,
                direction=pending.direction,
                volume=pending.volume,
                entry=pending.entry,
                stop_loss=pending.stop_loss,
                take_profit=pending.take_profit,
                order_id=result.order_id or pending.order_id,
            )
        )
        return result

    @property
    def health(self) -> RuntimeHealthTracker:
        """Return operational telemetry; it does not influence trading decisions."""
        return self._health

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
        if now is None:
            now = datetime.now(UTC)
        self._health.cycle_started(now)
        self._audit.append(AuditEvent(timestamp=now, trace_id=idempotency_key, event="cycle_started", status="STARTED", symbol=self._symbol))

        try:
            account_info = self._mt5.account_info()
        except Exception:
            reason = "MT5_ACCOUNT_INFO_UNAVAILABLE"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="failure")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(False, None, None, reason))
        if account_info is None:
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(False, None, None, "MT5_ACCOUNT_INFO_UNAVAILABLE"))

        try:
            terminal_info = getattr(self._mt5, "terminal_info", lambda: None)()
        except Exception:
            reason = "MT5_CONNECTION_UNHEALTHY"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="failure")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(False, None, None, reason))
        connected = terminal_info is not None and bool(
            getattr(terminal_info, "connected", True)
        )
        session_before = self._session.state.identity if self._session.state else None

        try:
            symbol_info = self._mt5.symbol_info(self._symbol)
        except Exception:
            reason = "MT5_SYMBOL_INFO_UNAVAILABLE"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="failure")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(False, None, None, reason))
        symbol_available = symbol_info is not None
        try:
            tick = self._mt5.symbol_info_tick(self._symbol) if symbol_available else None
        except Exception:
            reason = "MT5_TICK_UNAVAILABLE"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="failure")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(False, None, None, reason))
        if tick is None:
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(False, None, None, "MT5_TICK_UNAVAILABLE"))

        terminal_trade_allowed = bool(
            getattr(terminal_info, "trade_allowed", False)
        )
        state = self._session.refresh(
            account_info,
            connected=connected,
            connection_healthy=connected,
            execution_enabled=self._execution_enabled,
            symbol=self._symbol,
            symbol_available=symbol_available,
            mt5_module=self._mt5,
            terminal_trade_allowed=terminal_trade_allowed,
        )
        changed = session_before != state.identity

        if state.capabilities.environment is not TradingEnvironment.DEMO:
            reason = "LIVE_EXECUTION_LOCKED_V1"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason)
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, None, None, reason))

        try:
            account = account_snapshot_from_mt5(account_info)
            broker = broker_spec_from_mt5(symbol_info)
            execution = execution_snapshot_from_mt5(tick)
        except (AttributeError, TypeError, ValueError):
            reason = "MT5_SNAPSHOT_INVALID"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="failure")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, None, None, reason))

        adaptive_report = self._adaptive.assess(
            observation=MT5RuntimeObservation(
                capabilities=state.capabilities,
                broker=broker,
                execution=execution,
            ),
            profile=profile,
            trace_id=idempotency_key,
            now=now,
        )
        if not adaptive_report.safe:
            reason = "ADAPTIVE_RUNTIME_GUARD"
            self._health.rejected(reason)
            self._audit_rejection(
                trace_id=idempotency_key,
                now=now,
                reason=reason,
                event="adaptive_runtime_guard",
                details={
                    "repeated_failures": list(adaptive_report.repeated_failures),
                    "blocked_changes": list(adaptive_report.blocked_changes),
                },
            )
            return self._finish(
                trace_id=idempotency_key,
                now=now,
                result=DemoCycleResult(changed, None, None, reason),
            )

        guardian_report = self._guardian.inspect(
            trace_id=idempotency_key,
            now=now,
        )
        if not guardian_report.safe:
            reason = "PROJECT_GUARDIAN_GUARD"
            self._health.rejected(reason)
            self._audit_rejection(
                trace_id=idempotency_key,
                now=now,
                reason=reason,
                event="project_guardian_guard",
                details={
                    "findings": [item.reason for item in guardian_report.findings],
                    "blocked_changes": list(guardian_report.blocked_changes),
                },
            )
            return self._finish(
                trace_id=idempotency_key,
                now=now,
                result=DemoCycleResult(changed, None, None, reason),
            )

        if user_intent is None and not profile.auto_analysis_enabled:
            reason = "AUTO_ANALYSIS_DISABLED"
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason)
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, None, None, reason))

        preflight = run_production_preflight(
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
        if not preflight.ready:
            self._health.rejected(preflight.reason)
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=preflight.reason, event="preflight_rejection")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, None, None, preflight.reason))
        self._health.preflight_passed()

        analysis = None

        if user_intent is None:
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
            if proposal.analysis is None:
                return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, None, None, proposal.reason))

            self._health.analysis_attempted(now)
            analysis = proposal.analysis
            self._audit_analysis(trace_id=idempotency_key, now=now, analysis=analysis)
            if not proposal.allowed:
                self._audit_rejection(trace_id=idempotency_key, now=now, reason=proposal.reason, event="analysis_rejection")
                return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, None, proposal.reason))
            decision = analysis.decision
            if decision.scenario is None or decision.risk is None:
                reason = "NO_EXECUTABLE_SCENARIO"
                self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="execution_rejection")
                return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, None, reason))
            if analysis.stop_loss is None or analysis.take_profit is None:
                reason = "ANALYSIS_MISSING_EXECUTION_LEVELS"
                self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="execution_rejection")
                return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, None, reason))

            direction = decision.direction
            intent = TradeIntent(
                symbol=self._symbol,
                direction=direction,
                volume=decision.risk.volume,
                entry=execution.ask if direction.value == "BUY" else execution.bid,
                stop_loss=analysis.stop_loss,
                take_profit=analysis.take_profit,
                source=TradeSource.BOT_SUGGESTION,
                idempotency_key=idempotency_key,
                risk=decision.risk,
            )
        else:
            if profile.bot_suggestions_enabled:
                reason = "USER_DEFINED_REQUIRES_SUGGESTIONS_OFF"
                self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason)
                return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, None, None, reason))
            intent = user_intent

        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=idempotency_key,
                event="trade_intent",
                status="READY",
                reason="VALIDATED_INTENT",
                symbol=intent.symbol,
                direction=intent.direction.value,
                volume=intent.volume,
                entry=intent.entry,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
                details={
                    "source": intent.source.value,
                    "risk_executable": intent.risk.executable,
                    "risk_reason": intent.risk.reason,
                },
            )
        )

        # V1 keeps one active broker-side exposure per bot symbol/magic.
        # Broker state remains the source of truth after process restarts.
        lifecycle = self._positions.snapshot()
        self._health.reconciliation_checked(now, active_exposure=lifecycle.active)
        if lifecycle.active:
            reason = "ACTIVE_BOT_EXPOSURE_EXISTS"
            self._journal.append(
                journal_entry_from_intent(
                    intent=intent,
                    status="REJECTED",
                    reason=reason,
                    timestamp=now,
                )
            )
            self._health.rejected(reason)
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="exposure_rejection")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, None, reason))

        gate = self._execution_gate.validate(
            mt5=self._mt5,
            capabilities=state.capabilities,
            account_info=account_info,
            symbol_info=symbol_info,
            intent=intent,
            max_spread=profile.max_spread,
            max_slippage=profile.max_slippage,
            estimated_slippage=execution.estimated_slippage,
        )
        if not gate.allowed:
            self._journal.append(
                journal_entry_from_intent(
                    intent=intent,
                    status="REJECTED",
                    reason=gate.reason,
                    timestamp=now,
                )
            )
            self._health.rejected(gate.reason)
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=gate.reason, event="execution_gate_rejection")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, None, gate.reason))

        previous = self._journal.latest_for_idempotency_key(intent.idempotency_key)
        if previous is not None and previous.status in {"SUBMITTED", "PENDING_SUBMISSION"}:
            reason = "UNRESOLVED_SUBMISSION_REQUIRES_RECONCILIATION"
            self._health.rejected(reason)
            self._audit_rejection(trace_id=idempotency_key, now=now, reason=reason, event="idempotency_rejection")
            return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, None, reason))

        self._journal.append(
            journal_entry_from_intent(
                intent=intent,
                status="PENDING_SUBMISSION",
                reason="BROKER_SUBMISSION_PENDING",
                timestamp=now,
            )
        )
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=idempotency_key,
                event="execution",
                status="PENDING",
                reason="BROKER_SUBMISSION_PENDING",
                symbol=intent.symbol,
                direction=intent.direction.value,
                volume=intent.volume,
                entry=intent.entry,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
            )
        )
        self._health.execution_attempted(now)
        try:
            order = self._executor.execute(
                capabilities=state.capabilities,
                profile=profile,
                intent=intent,
            )
        except Exception as exc:
            # order_send may have reached the broker before the response failed.
            # Keep the durable pending state so a restart cannot blindly retry
            # the same candle; recovery must reconcile broker state first.
            reason = f"EXECUTION_ERROR_UNCERTAIN:{type(exc).__name__}:{exc}"
            self._journal.append(
                journal_entry_from_intent(
                    intent=intent,
                    status="PENDING_SUBMISSION",
                    reason=reason,
                    timestamp=now,
                )
            )
            self._health.errored(reason)
            self._audit_rejection(
                trace_id=idempotency_key,
                now=now,
                reason=reason,
                event="execution_failure",
                details={"submission_state": "UNCERTAIN"},
            )
            return self._finish(
                trace_id=idempotency_key,
                now=now,
                result=DemoCycleResult(changed, analysis, None, reason),
            )
        self._journal.append(
            journal_entry_from_intent(
                intent=intent,
                status="SUBMITTED" if order.submitted else "REJECTED",
                reason=order.reason,
                order_id=order.order_id,
                timestamp=now,
            )
        )
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=idempotency_key,
                event="execution",
                status="SUBMITTED" if order.submitted else "REJECTED",
                reason=order.reason,
                symbol=intent.symbol,
                direction=intent.direction.value,
                volume=intent.volume,
                entry=intent.entry,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
                order_id=order.order_id,
            )
        )
        if order.submitted:
            self._health.execution_succeeded()
        else:
            self._health.rejected(order.reason)
        self._health.reason(order.reason)
        return self._finish(trace_id=idempotency_key, now=now, result=DemoCycleResult(changed, analysis, order, order.reason))
