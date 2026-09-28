"""Policy-bounded executor for engineering repair plans.

The executor is deliberately not a source-code editor. It dispatches approved
RepairChange objects to explicitly registered handlers. Registration is
controlled by the host application, while immutable trading policies remain
blocked at this layer as a second defense.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Mapping

from .audit_log import AuditEvent, AuditLog
from .project_guardian import IMMUTABLE_PROJECT_POLICIES, SAFE_REPAIR_DOMAINS
from .repair_engine import RepairChange, RepairPlan


RepairHandler = Callable[[RepairChange], bool]


@dataclass(frozen=True)
class RepairExecutionResult:
    applied: bool
    executed: int
    reason: str


class ControlledRepairExecutor:
    """Dispatch only policy-approved engineering repairs."""

    def __init__(
        self,
        handlers: Mapping[str, RepairHandler],
        audit_log: AuditLog | None = None,
    ) -> None:
        self._handlers = dict(handlers)
        self._audit = audit_log

    @staticmethod
    def validate_change(change: RepairChange) -> bool:
        return (
            change.domain in SAFE_REPAIR_DOMAINS
            and change.target not in IMMUTABLE_PROJECT_POLICIES
        )

    def _record(
        self,
        *,
        plan: RepairPlan,
        status: str,
        reason: str,
        details: dict[str, object],
    ) -> None:
        if self._audit is None:
            return
        self._audit.append(
            AuditEvent(
                timestamp=datetime.now(UTC),
                trace_id=plan.trace_id,
                event="controlled_repair_execution",
                status=status,
                reason=reason,
                details=details,
            )
        )

    def execute(self, plan: RepairPlan) -> RepairExecutionResult:
        if not plan.allowed:
            result = RepairExecutionResult(False, 0, plan.rejection_reason)
            self._record(
                plan=plan,
                status="BLOCKED",
                reason=result.reason,
                details={"executed": 0},
            )
            return result

        executed = 0
        for change in plan.changes:
            if not self.validate_change(change):
                result = RepairExecutionResult(
                    False,
                    executed,
                    f"REPAIR_POLICY_BLOCKED:{change.target}",
                )
                self._record(
                    plan=plan,
                    status="BLOCKED",
                    reason=result.reason,
                    details={"executed": executed, "target": change.target},
                )
                return result
            handler = self._handlers.get(change.domain)
            if handler is None:
                result = RepairExecutionResult(
                    False,
                    executed,
                    f"REPAIR_HANDLER_MISSING:{change.domain}",
                )
                self._record(
                    plan=plan,
                    status="FAILED",
                    reason=result.reason,
                    details={"executed": executed, "domain": change.domain},
                )
                return result
            if not handler(change):
                result = RepairExecutionResult(
                    False,
                    executed,
                    f"REPAIR_HANDLER_FAILED:{change.domain}",
                )
                self._record(
                    plan=plan,
                    status="FAILED",
                    reason=result.reason,
                    details={"executed": executed, "domain": change.domain},
                )
                return result
            executed += 1

        result = RepairExecutionResult(True, executed, "REPAIR_EXECUTED")
        self._record(
            plan=plan,
            status="APPLIED",
            reason=result.reason,
            details={"executed": executed},
        )
        return result
