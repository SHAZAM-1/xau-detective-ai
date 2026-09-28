"""Policy-bounded executor for engineering repair plans.

The executor is deliberately not a source-code editor. It dispatches approved
RepairChange objects to explicitly registered handlers. Registration is
controlled by the host application, while immutable trading policies remain
blocked at this layer as a second defense.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

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

    def __init__(self, handlers: Mapping[str, RepairHandler]) -> None:
        self._handlers = dict(handlers)

    @staticmethod
    def validate_change(change: RepairChange) -> bool:
        return (
            change.domain in SAFE_REPAIR_DOMAINS
            and change.target not in IMMUTABLE_PROJECT_POLICIES
        )

    def execute(self, plan: RepairPlan) -> RepairExecutionResult:
        if not plan.allowed:
            return RepairExecutionResult(False, 0, plan.rejection_reason)

        executed = 0
        for change in plan.changes:
            if not self.validate_change(change):
                return RepairExecutionResult(
                    False,
                    executed,
                    f"REPAIR_POLICY_BLOCKED:{change.target}",
                )
            handler = self._handlers.get(change.domain)
            if handler is None:
                return RepairExecutionResult(
                    False,
                    executed,
                    f"REPAIR_HANDLER_MISSING:{change.domain}",
                )
            if not handler(change):
                return RepairExecutionResult(
                    False,
                    executed,
                    f"REPAIR_HANDLER_FAILED:{change.domain}",
                )
            executed += 1

        return RepairExecutionResult(True, executed, "REPAIR_EXECUTED")
