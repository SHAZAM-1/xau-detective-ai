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


def test_repair_engine_blocks_multi_change_apply_without_transaction():
    audit = InMemoryAuditLog()
    engine = RepairEngine(audit)
    report = guardian_report_with_runtime_failure(audit)
    single = engine.propose(
        guardian_report=report,
        trace_id="repair-multi",
        now=NOW,
    )
    multi = type(single)(
        trace_id=single.trace_id,
        changes=single.changes + (single.changes[0],),
        requires_validation=True,
        allowed=True,
    )
    called = False

    def executor(_change):
        nonlocal called
        called = True
        return True

    result = engine.apply(plan=multi, executor=executor, now=NOW)

    assert result.applied is False
    assert result.reason == "REPAIR_MULTI_CHANGE_REQUIRES_TRANSACTION"
    assert called is False

def test_repair_engine_blocks_scoped_immutable_policy_targets():
    assert RepairEngine.validate_change(
        domain="MT5_ADAPTER",
        target="STRATEGY:DETAIL",
    ) is False
    assert RepairEngine.validate_change(
        domain="MT5_ADAPTER",
        target="RISK_POLICY:DETAIL",
    ) is False

def test_repair_engine_does_not_mark_empty_plan_as_applied():
    audit = InMemoryAuditLog()
    engine = RepairEngine(audit)
    plan = type(
        "EmptyPlan",
        (),
        {
            "trace_id": "repair-empty",
            "changes": (),
            "requires_validation": True,
            "allowed": True,
            "rejection_reason": "",
        },
    )()
    called = False

    def executor(_change):
        nonlocal called
        called = True
        return True

    result = engine.apply(plan=plan, executor=executor, now=NOW)

    assert result.applied is False
    assert result.reason == "REPAIR_NO_CHANGES"
    assert called is False


def test_repair_engine_blocks_domain_target_mismatch():
    assert RepairEngine.validate_change(
        domain="TESTS",
        target="LINT",
    ) is False
    assert RepairEngine.validate_change(
        domain="TESTS",
        target=" tests : detail ",
    ) is False
