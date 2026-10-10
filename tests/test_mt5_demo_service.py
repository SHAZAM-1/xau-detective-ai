from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.demo_execution import TradeIntent, TradeSource
from xau_detective.environment import TradingEnvironment
from xau_detective.mt5_demo_service import MT5DemoTradingService
from xau_detective.models import Direction
from xau_detective.risk import RiskResult
from xau_detective.trade_journal import InMemoryTradeJournal, journal_entry_from_intent
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

    def __init__(self, trade_mode=0, deals=()):
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
        self.deals = deals

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

    def history_deals_get(self, **kwargs):
        return self.deals


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
        profile=TradingProfile(),
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=datetime(2026, 9, 26, 12, tzinfo=timezone.utc),
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
        profile=TradingProfile(),
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=datetime(2026, 9, 26, 12, tzinfo=timezone.utc),
        idempotency_key="broken-tick",
    )
    assert result.reason == "MT5_TICK_UNAVAILABLE"


def pending_intent(key="recovery-1"):
    return TradeIntent(
        symbol="XAUUSD",
        direction=Direction.BUY,
        volume=Decimal("0.02"),
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4020"),
        source=TradeSource.BOT_SUGGESTION,
        idempotency_key=key,
        risk=RiskResult(True, Decimal("0.02"), Decimal("1"), Decimal("1"), "OK"),
    )


def seed_pending(journal, key="recovery-1"):
    intent = pending_intent(key)
    journal.append(
        journal_entry_from_intent(
            intent=intent,
            status="PENDING_SUBMISSION",
            reason="BROKER_SUBMISSION_PENDING",
            timestamp=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        )
    )
    return intent


def test_recovery_records_open_position_without_resubmitting():
    mt5 = FakeMT5()
    mt5.positions_get = lambda *, symbol: (
        SimpleNamespace(
            ticket=777,
            symbol=symbol,
            volume=Decimal("0.02"),
            price_open=Decimal("4000"),
            sl=Decimal("3990"),
            tp=Decimal("4020"),
            magic=260926,
            comment="xau-detective-demo",
        ),
    )
    mt5.orders_get = lambda *, symbol: ()
    journal = InMemoryTradeJournal()
    seed_pending(journal)
    result = MT5DemoTradingService(mt5, journal=journal).recover_pending_submission(
        idempotency_key="recovery-1", position_id="777"
    )
    assert result.state.value == "POSITION_OPEN"
    assert mt5.sent == []
    assert journal.latest_for_idempotency_key("recovery-1").status == "RECOVERED_POSITION_OPEN"


def test_recovery_records_partial_fill():
    mt5 = FakeMT5()
    mt5.positions_get = lambda *, symbol: (
        SimpleNamespace(
            ticket=777,
            symbol=symbol,
            volume=Decimal("0.01"),
            price_open=Decimal("4000"),
            sl=Decimal("3990"),
            tp=Decimal("4020"),
            magic=260926,
            comment="xau-detective-demo",
        ),
    )
    mt5.orders_get = lambda *, symbol: ()
    journal = InMemoryTradeJournal()
    seed_pending(journal)
    result = MT5DemoTradingService(mt5, journal=journal).recover_pending_submission(
        idempotency_key="recovery-1", position_id="777"
    )
    assert result.state.value == "PARTIAL_FILL"
    assert journal.latest_for_idempotency_key("recovery-1").status == "RECOVERED_PARTIAL_FILL"


def test_recovery_records_pending_order():
    mt5 = FakeMT5()
    mt5.positions_get = lambda *, symbol: ()
    mt5.orders_get = lambda *, symbol: (
        SimpleNamespace(
            ticket=777,
            symbol=symbol,
            volume_current=Decimal("0.02"),
            price_open=Decimal("4000"),
            magic=260926,
            comment="xau-detective-demo",
            state="STARTED",
        ),
    )
    journal = InMemoryTradeJournal()
    seed_pending(journal)
    result = MT5DemoTradingService(mt5, journal=journal).recover_pending_submission(
        idempotency_key="recovery-1", order_id="777"
    )
    assert result.state.value == "PENDING_ORDER"
    assert journal.latest_for_idempotency_key("recovery-1").status == "RECOVERED_PENDING_ORDER"


def test_recovery_records_closed_by_sl_and_tp():
    for reason, expected in ((4, "RECOVERED_CLOSED_BY_SL"), (5, "RECOVERED_CLOSED_BY_TP")):
        mt5 = FakeMT5(deals=(SimpleNamespace(entry=1, reason=reason),))
        mt5.positions_get = lambda *, symbol: ()
        mt5.orders_get = lambda *, symbol: ()
        journal = InMemoryTradeJournal()
        seed_pending(journal)
        result = MT5DemoTradingService(mt5, journal=journal).recover_pending_submission(
            idempotency_key="recovery-1", order_id="777", position_id="888"
        )
        assert result.state.value in {"CLOSED_BY_SL", "CLOSED_BY_TP"}
        assert journal.latest_for_idempotency_key("recovery-1").status == expected


def test_recovery_records_manual_close():
    mt5 = FakeMT5(deals=(SimpleNamespace(entry=1, reason=0),))
    mt5.positions_get = lambda *, symbol: ()
    mt5.orders_get = lambda *, symbol: ()
    journal = InMemoryTradeJournal()
    seed_pending(journal)
    result = MT5DemoTradingService(mt5, journal=journal).recover_pending_submission(
        idempotency_key="recovery-1", order_id="777", position_id="888"
    )
    assert result.state.value == "CLOSED_MANUALLY"
    assert journal.latest_for_idempotency_key("recovery-1").status == "RECOVERED_CLOSED_MANUALLY"


def test_recovery_requires_manual_reconciliation_when_broker_state_is_missing():
    mt5 = FakeMT5()
    mt5.positions_get = lambda *, symbol: ()
    mt5.orders_get = lambda *, symbol: ()
    journal = InMemoryTradeJournal()
    seed_pending(journal)
    result = MT5DemoTradingService(mt5, journal=journal).recover_pending_submission(
        idempotency_key="recovery-1", order_id="777"
    )
    assert result.state.value == "NOT_FOUND"
    entry = journal.latest_for_idempotency_key("recovery-1")
    assert entry.status == "RECOVERY_REQUIRED"
    assert entry.reason == "BROKER_STATE_NOT_FOUND_MANUAL_RECONCILIATION_REQUIRED"


def test_recovery_rejects_unknown_pending_submission():
    service = MT5DemoTradingService(FakeMT5())
    try:
        service.recover_pending_submission(idempotency_key="missing")
    except ValueError as exc:
        assert str(exc) == "PENDING_SUBMISSION_NOT_FOUND"
    else:
        raise AssertionError("expected missing pending submission to fail closed")


def test_service_audits_analysis_decision_and_no_trade():
    from xau_detective.audit_log import InMemoryAuditLog
    from xau_detective.models import Decision, Scenario
    from xau_detective.pipeline import MarketAnalysis

    audit = InMemoryAuditLog()
    service = MT5DemoTradingService(FakeMT5(), audit_log=audit)
    reason = "PATTERN_CONFLICT_LATEST_CANDLE"
    analysis = MarketAnalysis(
        decision=Decision(
            Direction.NO_TRADE,
            42,
            reason,
            Scenario(Direction.NO_TRADE, (reason,), reason),
            None,
        ),
        timestamp=datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
        entry=Decimal("4000"),
        stop_loss=None,
        take_profit=None,
        session="NEW_YORK",
        evidence_supporting=("TREND_BULLISH",),
        evidence_contradicting=("PATTERN_CONFLICT",),
        evidence_warnings=("LOW_LIQUIDITY",),
        reward_risk=None,
        candlestick_patterns=("ENGULFING",),
        price_action_moves=("LIQUIDITY_SWEEP",),
    )

    service._audit_analysis(
        trace_id="analysis-1", now=analysis.timestamp, analysis=analysis
    )

    events = audit.events()
    assert {event.event for event in events} == {
        "analysis_started",
        "evidence",
        "pattern_analysis",
        "decision",
        "no_trade",
    }
    assert all(event.trace_id == "analysis-1" for event in events)
    decision = next(event for event in events if event.event == "decision")
    assert decision.status == "NO_TRADE"
    assert decision.reason == reason
    assert decision.details["setup_score"] == 42
    no_trade = next(event for event in events if event.event == "no_trade")
    assert no_trade.reason == reason
    assert no_trade.details["evidence_contradicting"] == ["PATTERN_CONFLICT"]


def test_service_integrates_adaptive_runtime_and_project_guardian():
    audit = InMemoryAuditLog()
    service = MT5DemoTradingService(FakeMT5(), audit_log=audit)
    result = service.cycle(
        profile=TradingProfile(auto_analysis_enabled=False),
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
        idempotency_key="guardian-healthy",
    )
    assert result.reason == "AUTO_ANALYSIS_DISABLED"
    events = audit.events()
    assert any(
        event.event == "adaptive_runtime"
        and event.status == "SAFE"
        and event.trace_id == "guardian-healthy"
        for event in events
    )
    assert any(
        event.event == "project_guardian"
        and event.status == "SAFE"
        and event.trace_id == "guardian-healthy"
        for event in events
    )


def test_service_blocks_after_repeated_operational_failures():
    audit = InMemoryAuditLog()
    for index in range(3):
        audit.append(
            AuditEvent(
                timestamp=datetime(2026, 9, 28, 11, index, tzinfo=timezone.utc),
                trace_id=f"old-{index}",
                event="failure",
                status="BLOCKED",
                reason="MT5_TICK_UNAVAILABLE",
                symbol="XAUUSD",
            )
        )
    service = MT5DemoTradingService(FakeMT5(), audit_log=audit)
    result = service.cycle(
        profile=TradingProfile(),
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
        idempotency_key="adaptive-block",
    )
    assert result.reason == "ADAPTIVE_RUNTIME_GUARD"
    assert not any(event.event == "project_guardian" and event.trace_id == "adaptive-block" for event in audit.events())
    guard = next(event for event in audit.events() if event.event == "adaptive_runtime_guard")
    assert guard.reason == "ADAPTIVE_RUNTIME_GUARD"
    assert guard.details["repeated_failures"] == ["MT5_TICK_UNAVAILABLE"]



def test_uncertain_order_submission_stays_pending_and_cannot_retry(monkeypatch):
    from types import SimpleNamespace

    mt5 = FakeMT5()
    mt5.terminal_info = lambda: SimpleNamespace(
        connected=True,
        trade_allowed=True,
    )
    journal = InMemoryTradeJournal()
    service = MT5DemoTradingService(
        mt5,
        execution_enabled=True,
        journal=journal,
        audit_log=InMemoryAuditLog(),
        adaptive_agent=SimpleNamespace(
            assess=lambda **kwargs: SimpleNamespace(
                safe=True,
                repeated_failures=(),
                blocked_changes=(),
            )
        ),
        project_guardian=SimpleNamespace(
            inspect=lambda **kwargs: SimpleNamespace(
                safe=True,
                findings=(),
                blocked_changes=(),
            )
        ),
    )
    service._positions = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(active=False)
    )
    service._execution_gate.validate = lambda **kwargs: SimpleNamespace(
        allowed=True,
        reason="OK",
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_service.run_production_preflight",
        lambda **kwargs: SimpleNamespace(ready=True, reason="OK"),
    )

    execute_calls = []

    def fail_after_possible_submission(**kwargs):
        execute_calls.append(True)
        raise RuntimeError("simulated response loss")

    service._executor.execute = fail_after_possible_submission
    intent = pending_intent("uncertain-submission-1")
    profile = TradingProfile(
        bot_suggestions_enabled=False,
        auto_execution_enabled=True,
    )
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)

    first = service.cycle(
        profile=profile,
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=now,
        idempotency_key=intent.idempotency_key,
        user_intent=intent,
    )

    assert first.reason.startswith("EXECUTION_ERROR_UNCERTAIN:")
    assert journal.latest_for_idempotency_key(
        intent.idempotency_key
    ).status == "PENDING_SUBMISSION"

    second = service.cycle(
        profile=profile,
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=now,
        idempotency_key=intent.idempotency_key,
        user_intent=intent,
    )

    assert second.reason == "UNRESOLVED_SUBMISSION_REQUIRES_RECONCILIATION"
    assert execute_calls == [True]

    journal.append(
        journal_entry_from_intent(
            intent=intent,
            status="RECOVERY_REQUIRED",
            reason="BROKER_STATE_NOT_FOUND_MANUAL_RECONCILIATION_REQUIRED",
            timestamp=now,
        )
    )
    third = service.cycle(
        profile=profile,
        d1=candles(),
        h4=candles(),
        h1=candles(),
        m15=candles(),
        m5=candles(),
        now=now,
        idempotency_key=intent.idempotency_key,
        user_intent=intent,
    )

    assert third.reason == "UNRESOLVED_SUBMISSION_REQUIRES_RECONCILIATION"
    assert execute_calls == [True]


def test_recovery_required_can_be_reconciled_again_when_broker_state_appears():
    mt5 = FakeMT5()
    mt5.positions_get = lambda *, symbol: ()
    mt5.orders_get = lambda *, symbol: ()
    journal = InMemoryTradeJournal()
    seed_pending(journal)
    service = MT5DemoTradingService(mt5, journal=journal)

    first = service.recover_pending_submission(
        idempotency_key="recovery-1", order_id="777"
    )
    assert first.state.value == "NOT_FOUND"
    assert journal.latest_for_idempotency_key("recovery-1").status == "RECOVERY_REQUIRED"

    mt5.positions_get = lambda *, symbol: (
        SimpleNamespace(
            ticket=777,
            symbol=symbol,
            volume=Decimal("0.02"),
            price_open=Decimal("4000"),
            sl=Decimal("3990"),
            tp=Decimal("4020"),
            magic=260926,
            comment="xau-detective-demo",
        ),
    )
    second = service.recover_pending_submission(
        idempotency_key="recovery-1", position_id="777"
    )

    assert second.state.value == "POSITION_OPEN"
    assert journal.latest_for_idempotency_key("recovery-1").status == "RECOVERED_POSITION_OPEN"
    assert mt5.sent == []



def test_service_latches_execution_block_after_demo_account_switch():
    mt5 = FakeMT5()
    service = MT5DemoTradingService(mt5, execution_enabled=True)
    profile = TradingProfile(auto_analysis_enabled=False)
    cycle_args = {
        "profile": profile,
        "d1": candles(),
        "h4": candles(),
        "h1": candles(),
        "m15": candles(),
        "m5": candles(),
        "now": datetime(2026, 9, 26, 12, tzinfo=timezone.utc),
    }

    first = service.cycle(**cycle_args, idempotency_key="session-before-switch")
    assert first.reason == "AUTO_ANALYSIS_DISABLED"

    mt5.account.login = 456
    mt5.account.server = "Demo-Other"

    second = service.cycle(**cycle_args, idempotency_key="session-switch")
    third = service.cycle(**cycle_args, idempotency_key="session-switch-next-cycle")

    assert second.reason == "MT5_SESSION_CHANGED_EXECUTION_BLOCKED"
    assert third.reason == "MT5_SESSION_CHANGED_EXECUTION_BLOCKED"
    assert mt5.sent == []
    assert any(
        event.event == "session_switch_blocked"
        and event.reason == "MT5_SESSION_CHANGED_EXECUTION_BLOCKED"
        for event in service.audit_log.events()
    )
