"""Tests for bounded guardian-to-repair coordination."""
from datetime import UTC, datetime

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.guardian_repair_coordinator import (
    GuardianRepairCoordinator,
    RepairValidationResult,
)
from xau_detective.project_guardian import ProjectGuardian
from xau_detective.repair_engine import RepairChange, RepairEngine, RepairPlan


NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


class StubValidator:
    def __init__(self, result: RepairValidationResult) -> None:
        self.result = result
        self.calls = 0

    def validate(self) -> RepairValidationResult:
        self.calls += 1
        return self.result


def runtime_failure_audit() -> InMemoryAuditLog:
    audit = InMemoryAuditLog()
    for index in range(2):
        audit.append(
            AuditEvent(
                timestamp=NOW,
                trace_id=f"failure-{index}",
                event="runtime_failure",
                status="REJECTED",
                reason="MT5_TICK_UNAVAILABLE",
            )
        )
    return audit


def make_coordinator(audit: InMemoryAuditLog) -> GuardianRepairCoordinator:
    return GuardianRepairCoordinator(
        guardian=ProjectGuardian(audit),
        repair_engine=RepairEngine(audit),
        audit_log=audit,
    )


def test_inspect_and_plan_keeps_guardian_and_repair_engine_bounded() -> None:
    audit = runtime_failure_audit()
    coordinator = make_coordinator(audit)

    report, plan = coordinator.inspect_and_plan(
        trace_id="coordinator-plan",
        now=NOW,
    )

    assert report.safe is True
    assert report.proposals[0].domain == "MT5_ADAPTER"
    assert plan.allowed is True
    assert plan.changes[0].target == "MT5_ADAPTER"


def test_apply_and_validate_runs_executor_then_validation() -> None:
    audit = runtime_failure_audit()
    coordinator = make_coordinator(audit)
    _, plan = coordinator.inspect_and_plan(
        trace_id="coordinator-apply",
        now=NOW,
    )
    applied: list[str] = []
    validator = StubValidator(
        RepairValidationResult(True, True, True, True)
    )

    result = coordinator.apply_and_validate(
        plan=plan,
        executor=lambda change: applied.append(change.target) is None,
        validator=validator,
        now=NOW,
    )

    assert result.apply_result is not None
    assert result.apply_result.applied is True
    assert result.validation is not None
    assert result.validation.passed is True
    assert applied == ["MT5_ADAPTER"]
    assert validator.calls == 1


def test_validation_failure_is_not_marked_passed() -> None:
    audit = runtime_failure_audit()
    coordinator = make_coordinator(audit)
    _, plan = coordinator.inspect_and_plan(
        trace_id="coordinator-fail",
        now=NOW,
    )
    validator = StubValidator(
        RepairValidationResult(
            tests_passed=True,
            ruff_passed=False,
            health_passed=True,
            immutable_policy_passed=True,
        )
    )

    result = coordinator.apply_and_validate(
        plan=plan,
        executor=lambda _change: True,
        validator=validator,
        now=NOW,
    )

    assert result.validation is not None
    assert result.validation.passed is False
    assert audit.events()[-2].event == "repair_validation"
    assert audit.events()[-2].status == "FAILED"


def test_validation_result_requires_every_gate() -> None:
    assert RepairValidationResult(True, True, True, True).passed is True

    for failed_gate in range(4):
        values = [True, True, True, True]
        values[failed_gate] = False
        assert RepairValidationResult(*values).passed is False


def test_failed_executor_skips_validation() -> None:
    audit = runtime_failure_audit()
    coordinator = make_coordinator(audit)
    _, plan = coordinator.inspect_and_plan(
        trace_id="coordinator-executor-fail",
        now=NOW,
    )
    validator = StubValidator(
        RepairValidationResult(True, True, True, True)
    )

    result = coordinator.apply_and_validate(
        plan=plan,
        executor=lambda _change: False,
        validator=validator,
        now=NOW,
    )

    assert result.apply_result is not None
    assert result.apply_result.applied is False
    assert result.validation is None
    assert validator.calls == 0


def test_blocked_plan_never_calls_executor_or_validator() -> None:
    audit = InMemoryAuditLog()
    coordinator = make_coordinator(audit)
    plan = RepairPlan(
        trace_id="blocked",
        changes=(
            RepairChange(
                domain="STRATEGY",
                target="STRATEGY",
                reason="IMMUTABLE",
                description="must remain blocked",
            ),
        ),
        requires_validation=True,
        allowed=False,
        rejection_reason="REPAIR_POLICY_BLOCKED:STRATEGY",
    )
    called = False
    validator = StubValidator(
        RepairValidationResult(True, True, True, True)
    )

    def executor(_change):
        nonlocal called
        called = True
        return True

    result = coordinator.apply_and_validate(
        plan=plan,
        executor=executor,
        validator=validator,
        now=NOW,
    )

    assert result.apply_result is None
    assert result.validation is None
    assert called is False
    assert validator.calls == 0
