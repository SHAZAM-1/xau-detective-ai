"""Guardian-to-repair orchestration with mandatory validation gates.

This module coordinates diagnosis evidence into a bounded repair plan. It does
not mutate source code itself. Any executor remains injected and policy-safe;
a repair is not considered valid until tests, Ruff, project health, and the
immutable-policy gate all pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from .audit_log import AuditEvent, AuditLog
from .project_guardian import GuardianReport, ProjectGuardian
from .repair_engine import RepairApplyResult, RepairEngine, RepairPlan


class RepairValidator(Protocol):
    def validate(self) -> "RepairValidationResult": ...


@dataclass(frozen=True)
class RepairValidationResult:
    tests_passed: bool
    ruff_passed: bool
    health_passed: bool
    immutable_policy_passed: bool

    @property
    def passed(self) -> bool:
        return (
            self.tests_passed
            and self.ruff_passed
            and self.health_passed
            and self.immutable_policy_passed
        )


@dataclass(frozen=True)
class RepairCycleResult:
    guardian_report: GuardianReport
    plan: RepairPlan
    apply_result: RepairApplyResult | None
    validation: RepairValidationResult | None


class GuardianRepairCoordinator:
    """Run one bounded diagnose -> propose -> apply -> validate cycle."""

    def __init__(
        self,
        guardian: ProjectGuardian,
        repair_engine: RepairEngine,
        audit_log: AuditLog,
    ) -> None:
        self._guardian = guardian
        self._repair_engine = repair_engine
        self._audit = audit_log

    def inspect_and_plan(
        self,
        *,
        trace_id: str,
        now: datetime,
    ) -> tuple[GuardianReport, RepairPlan]:
        report = self._guardian.inspect(trace_id=trace_id, now=now)
        plan = self._repair_engine.propose(
            guardian_report=report,
            trace_id=trace_id,
            now=now,
        )
        return report, plan

    def apply_and_validate(
        self,
        *,
        plan: RepairPlan,
        executor: Callable,
        validator: RepairValidator,
        now: datetime,
    ) -> RepairCycleResult:
        if not plan.allowed:
            return RepairCycleResult(
                guardian_report=self._guardian.inspect(
                    trace_id=plan.trace_id,
                    now=now,
                ),
                plan=plan,
                apply_result=None,
                validation=None,
            )

        apply_result = self._repair_engine.apply(
            plan=plan,
            executor=executor,
            now=now,
        )
        if not apply_result.applied:
            return RepairCycleResult(
                guardian_report=self._guardian.inspect(
                    trace_id=plan.trace_id,
                    now=now,
                ),
                plan=plan,
                apply_result=apply_result,
                validation=None,
            )

        validation = validator.validate()
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=plan.trace_id,
                event="repair_validation",
                status="PASSED" if validation.passed else "FAILED",
                reason=(
                    "REPAIR_VALIDATION_PASSED"
                    if validation.passed
                    else "REPAIR_VALIDATION_FAILED"
                ),
                details={
                    "tests": validation.tests_passed,
                    "ruff": validation.ruff_passed,
                    "project_health": validation.health_passed,
                    "immutable_policy": validation.immutable_policy_passed,
                },
            )
        )
        return RepairCycleResult(
            guardian_report=self._guardian.inspect(
                trace_id=plan.trace_id,
                now=now,
            ),
            plan=plan,
            apply_result=apply_result,
            validation=validation,
        )
