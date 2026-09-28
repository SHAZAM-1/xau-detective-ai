"""Tests for the policy-bounded repair executor."""
from datetime import UTC, datetime

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.controlled_repair_executor import ControlledRepairExecutor
from xau_detective.repair_engine import RepairChange, RepairPlan


def change(domain: str, target: str | None = None) -> RepairChange:
    return RepairChange(
        domain=domain,
        target=target or domain,
        reason="TEST_REASON",
        description="bounded test repair",
    )


def plan(*changes: RepairChange, allowed: bool = True) -> RepairPlan:
    return RepairPlan(
        trace_id="executor-test",
        changes=changes,
        requires_validation=True,
        allowed=allowed,
        rejection_reason="" if allowed else "GUARDIAN_BLOCKED",
    )


def test_dispatches_only_registered_safe_domain() -> None:
    seen: list[str] = []
    executor = ControlledRepairExecutor(
        {"TESTS": lambda item: seen.append(item.target) is None}
    )

    result = executor.execute(plan(change("TESTS")))

    assert result.applied is True
    assert result.executed == 1
    assert seen == ["TESTS"]


def test_immutable_policy_is_blocked_before_handler() -> None:
    called = False

    def handler(_item):
        nonlocal called
        called = True
        return True

    executor = ControlledRepairExecutor({"TESTS": handler})

    result = executor.execute(plan(change("TESTS", "STRATEGY")))

    assert result.applied is False
    assert result.reason == "REPAIR_POLICY_BLOCKED:STRATEGY"
    assert called is False


def test_missing_handler_fails_closed() -> None:
    executor = ControlledRepairExecutor({})

    result = executor.execute(plan(change("MT5_ADAPTER")))

    assert result.applied is False
    assert result.executed == 0
    assert result.reason == "REPAIR_HANDLER_MISSING:MT5_ADAPTER"


def test_handler_failure_stops_following_changes() -> None:
    seen: list[str] = []
    executor = ControlledRepairExecutor(
        {
            "TESTS": lambda item: seen.append(item.target) is None,
            "LINT": lambda _item: False,
        }
    )

    result = executor.execute(plan(change("TESTS"), change("LINT")))

    assert result.applied is False
    assert result.executed == 1
    assert result.reason == "REPAIR_HANDLER_FAILED:LINT"
    assert seen == ["TESTS"]


def test_blocked_plan_never_dispatches() -> None:
    called = False

    def handler(_item):
        nonlocal called
        called = True
        return True

    executor = ControlledRepairExecutor({"TESTS": handler})

    result = executor.execute(plan(change("TESTS"), allowed=False))

    assert result.applied is False
    assert result.executed == 0
    assert result.reason == "GUARDIAN_BLOCKED"
    assert called is False


def test_execution_is_audited() -> None:
    audit = InMemoryAuditLog()
    executor = ControlledRepairExecutor(
        {"TESTS": lambda _item: True},
        audit_log=audit,
    )

    result = executor.execute(plan(change("TESTS")))

    assert result.applied is True
    event = audit.events()[-1]
    assert isinstance(event, AuditEvent)
    assert event.event == "controlled_repair_execution"
    assert event.status == "APPLIED"
    assert event.reason == "REPAIR_EXECUTED"


def test_blocked_execution_is_audited() -> None:
    audit = InMemoryAuditLog()
    executor = ControlledRepairExecutor({}, audit_log=audit)

    result = executor.execute(plan(change("TESTS"), allowed=False))

    assert result.applied is False
    event = audit.events()[-1]
    assert event.status == "BLOCKED"
    assert event.reason == "GUARDIAN_BLOCKED"
