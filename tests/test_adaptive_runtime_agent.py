from datetime import UTC, datetime
from decimal import Decimal

from xau_detective.adaptive_runtime_agent import AdaptiveRuntimeAgent, MT5RuntimeObservation
from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.environment import AccountCapabilities, TradingEnvironment
from xau_detective.models import BrokerSpec, ExecutionSnapshot
from xau_detective.trading_profile import TradingProfile


def observation(environment=TradingEnvironment.DEMO):
    return MT5RuntimeObservation(
        capabilities=AccountCapabilities(
            environment=environment,
            connected=True,
            connection_healthy=True,
            trading_allowed=True,
            execution_enabled=True,
            symbol_available=True,
            symbol="XAUUSD",
            server="Demo",
        ),
        broker=BrokerSpec(
            symbol="XAUUSD",
            contract_size=Decimal("100"),
            volume_min=Decimal("0.01"),
            volume_max=Decimal("100"),
            volume_step=Decimal("0.01"),
            tick_size=Decimal("0.01"),
            tick_value=Decimal("1"),
            point=Decimal("0.01"),
            min_stop_distance=Decimal("0.10"),
        ),
        execution=ExecutionSnapshot(
            bid=Decimal("4000"),
            ask=Decimal("4000.20"),
        ),
    )


def test_agent_refreshes_constraints_without_mutating_profile():
    audit = InMemoryAuditLog()
    profile = TradingProfile(risk_fraction=Decimal("0.01"))
    agent = AdaptiveRuntimeAgent(audit)

    report = agent.assess(
        observation=observation(),
        profile=profile,
        trace_id="adaptive-1",
        now=datetime(2026, 9, 28, 12, tzinfo=UTC),
    )

    assert report.safe is True
    assert "BROKER_SPEC_REFRESH" in agent.adaptation_actions(report)
    assert "CHANGE_RISK_FRACTION" in report.blocked_changes
    assert profile.risk_fraction == Decimal("0.01")
    assert audit.events()[-1].event == "adaptive_runtime"
    assert audit.events()[-1].trace_id == "adaptive-1"


def test_agent_fails_closed_for_non_demo_environment():
    audit = InMemoryAuditLog()
    agent = AdaptiveRuntimeAgent(audit)

    report = agent.assess(
        observation=observation(TradingEnvironment.LIVE),
        profile=TradingProfile(),
        trace_id="adaptive-live",
        now=datetime(2026, 9, 28, 12, tzinfo=UTC),
    )

    assert report.safe is False
    assert "EXECUTION_ENVIRONMENT_GUARD" in agent.adaptation_actions(report)


def test_agent_blocks_repeated_runtime_failures():
    audit = InMemoryAuditLog()
    for index in range(3):
        audit.append(
            AuditEvent(
                timestamp=datetime(2026, 9, 28, 12, index, tzinfo=UTC),
                trace_id=f"failure-{index}",
                event="runtime_failure",
                status="BLOCKED",
                reason="MT5_TICK_UNAVAILABLE",
            )
        )

    agent = AdaptiveRuntimeAgent(audit, repeated_failure_threshold=3)
    report = agent.assess(
        observation=observation(),
        profile=TradingProfile(),
        trace_id="adaptive-failure",
        now=datetime(2026, 9, 28, 12, 5, tzinfo=UTC),
    )

    assert report.safe is False
    assert report.repeated_failures == ("MT5_TICK_UNAVAILABLE",)



def test_forbidden_adaptation_action_check_is_case_and_whitespace_insensitive():
    assert AdaptiveRuntimeAgent.is_strategy_change("enable_live_execution")
    assert AdaptiveRuntimeAgent.is_strategy_change(" ENABLE LIVE EXECUTION ")
    assert AdaptiveRuntimeAgent.is_strategy_change("Change_Risk_Fraction")
    assert not AdaptiveRuntimeAgent.is_strategy_change("BROKER_SPEC_REFRESH")
    assert not AdaptiveRuntimeAgent.is_strategy_change(None)
