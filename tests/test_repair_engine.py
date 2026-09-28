"""Tests for bounded engineering repair planning."""
from datetime import UTC, datetime

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.project_guardian import ProjectGuardian
from xau_detective.repair_engine import RepairEngine


NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def guardian_report_with_runtime_failure(audit: InMemoryAuditLog):
    audit.append(
        AuditEvent(
            timestamp=NOW,
            trace_id="failure-1",
            event="runtime_failure",
            status="REJECTED",
            reason="MT5_TICK_UNAVAILABLE",
        )
    )
    audit.append(
        AuditEvent(
            timestamp=NOW,
            trace_id="failure-2",
            event="runtime_failure",
            status="REJECTED",
            reason="MT5_TICK_UNAVAILABLE",
        )
    )
    return ProjectGuardian(audit).inspect(trace_id="repair-1", now=NOW)


def test_repair_engine_proposes_only_safe_domain_changes():
    audit = InMemoryAuditLog()
    report = guardian_report_with_runtime_failure(audit)
    engine = RepairEngine(audit)

    plan = engine.propose(
        guardian_report=report,
        trace_id="repair-1",
        now=NOW,
    )

    assert plan.allowed is True
    assert plan.requires_validation is True
    assert plan.changes[0].domain == "MT5_ADAPTER"
    assert plan.changes[0].target == "MT5_ADAPTER"
    assert audit.events()[-1].event == "repair_plan"


def test_repair_engine_blocks_immutable_targets():
    assert RepairEngine.validate_change(
        domain="MT5_ADAPTER",
        target="RISK_POLICY",
    ) is False
    assert RepairEngine.validate_change(
        domain="STRATEGY",
        target="STRATEGY",
    ) is False


def test_repair_engine_requires_guardian_safe_report():
    audit = InMemoryAuditLog()
    report = ProjectGuardian(audit).inspect(
        trace_id="clean",
        now=NOW,
    )
    engine = RepairEngine(audit)

    plan = engine.propose(
        guardian_report=report,
        trace_id="repair-clean",
        now=NOW,
    )

    assert plan.allowed is True
    assert plan.changes == ()


def test_repair_engine_apply_is_executor_bounded_and_audited():
    audit = InMemoryAuditLog()
    report = guardian_report_with_runtime_failure(audit)
    engine = RepairEngine(audit)
    plan = engine.propose(
        guardian_report=report,
        trace_id="repair-apply",
        now=NOW,
    )
    applied: list[str] = []

    result = engine.apply(
        plan=plan,
        executor=lambda change: applied.append(change.target) is None,
        now=NOW,
    )

    assert result.applied is True
    assert result.validation_required is True
    assert applied == ["MT5_ADAPTER"]
    assert audit.events()[-1].event == "repair_apply"


def test_repair_engine_does_not_apply_blocked_plan():
    audit = InMemoryAuditLog()
    engine = RepairEngine(audit)
    blocked = engine.propose(
        guardian_report=type(
            "BlockedReport",
            (),
            {"safe": False, "proposals": ()},
        )(),
        trace_id="repair-blocked",
        now=NOW,
    )

    called = False

    def executor(_change):
        nonlocal called
        called = True
        return True

    result = engine.apply(plan=blocked, executor=executor, now=NOW)

    assert result.applied is False
    assert called is False
