"""Guarded engineering repair planning and validation.

The Repair Engine turns Project Guardian findings into bounded engineering
repair plans. It never authorizes strategy, risk, SL/TP, NO_TRADE, live
execution, or roadmap changes. Applying a repair is delegated to an injected
executor and must be followed by external project validation (tests, Ruff and
health/CI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .audit_log import AuditEvent, AuditLog
from .project_guardian import (
    IMMUTABLE_PROJECT_POLICIES,
    SAFE_REPAIR_DOMAINS,
    GuardianReport,
    RepairProposal,
)


@dataclass(frozen=True)
class RepairChange:
    domain: str
    target: str
    reason: str
    description: str


@dataclass(frozen=True)
class RepairPlan:
    trace_id: str
    changes: tuple[RepairChange, ...]
    requires_validation: bool
    allowed: bool
    rejection_reason: str = ""


@dataclass(frozen=True)
class RepairApplyResult:
    applied: bool
    validation_required: bool
    reason: str


RepairExecutor = Callable[[RepairChange], bool]


class RepairEngine:
    """Create and optionally apply only policy-safe engineering repairs."""

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit = audit_log

    def propose(
        self,
        *,
        guardian_report: GuardianReport,
        trace_id: str,
        now: datetime,
    ) -> RepairPlan:
        changes: list[RepairChange] = []
        rejection = ""

        if not guardian_report.safe:
            rejection = "GUARDIAN_REPORT_NOT_SAFE"
        else:
            for proposal in guardian_report.proposals:
                target = self._target_for_domain(proposal.domain)
                if not self.validate_change(
                    domain=proposal.domain,
                    target=target,
                ):
                    rejection = f"REPAIR_POLICY_BLOCKED:{target}"
                    break
                if not proposal.allowed:
                    rejection = f"REPAIR_DOMAIN_NOT_ALLOWED:{proposal.domain}"
                    break
                changes.append(
                    RepairChange(
                        domain=proposal.domain,
                        target=target,
                        reason=proposal.reason,
                        description=self._description_for(proposal),
                    )
                )

        plan = RepairPlan(
            trace_id=trace_id,
            changes=tuple(changes) if not rejection else (),
            requires_validation=True,
            allowed=not rejection,
            rejection_reason=rejection,
        )
        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="repair_plan",
                status="READY" if plan.allowed else "BLOCKED",
                reason="REPAIR_PLAN_CREATED" if plan.allowed else rejection,
                details={
                    "changes": [
                        {
                            "domain": change.domain,
                            "target": change.target,
                            "reason": change.reason,
                        }
                        for change in plan.changes
                    ],
                    "requires_validation": plan.requires_validation,
                    "blocked_policies": sorted(IMMUTABLE_PROJECT_POLICIES),
                },
            )
        )
        return plan

    def apply(
        self,
        *,
        plan: RepairPlan,
        executor: RepairExecutor,
        now: datetime,
    ) -> RepairApplyResult:
        if not plan.allowed:
            result = RepairApplyResult(False, True, plan.rejection_reason)
        else:
            for change in plan.changes:
                if not self.validate_change(
                    domain=change.domain,
                    target=change.target,
                ):
                    result = RepairApplyResult(
                        False,
                        True,
                        f"REPAIR_POLICY_BLOCKED:{change.target}",
                    )
                    break
                if not executor(change):
                    result = RepairApplyResult(
                        False,
                        True,
                        f"REPAIR_EXECUTION_FAILED:{change.target}",
                    )
                    break
            else:
                result = RepairApplyResult(
                    True,
                    True,
                    "REPAIR_APPLIED_REQUIRES_VALIDATION",
                )

        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=plan.trace_id,
                event="repair_apply",
                status="APPLIED" if result.applied else "BLOCKED",
                reason=result.reason,
                details={
                    "changes": len(plan.changes),
                    "validation_required": result.validation_required,
                },
            )
        )
        return result

    @staticmethod
    def validate_change(*, domain: str, target: str) -> bool:
        """Reject immutable project policies before an executor can run."""
        if domain not in SAFE_REPAIR_DOMAINS:
            return False
        if target in IMMUTABLE_PROJECT_POLICIES:
            return False
        return True

    @staticmethod
    def _target_for_domain(domain: str) -> str:
        return {
            "TESTS": "TESTS",
            "LINT": "LINT",
            "IMPORTS": "IMPORTS",
            "RUNTIME_GUARDS": "RUNTIME_GUARDS",
            "LOGGING": "LOGGING",
            "AUDIT_TRAIL": "AUDIT_TRAIL",
            "MT5_ADAPTER": "MT5_ADAPTER",
            "DATA_VALIDATION": "DATA_VALIDATION",
            "ERROR_HANDLING": "ERROR_HANDLING",
            "DOCUMENTATION": "DOCUMENTATION",
            "HEALTH_CHECK": "HEALTH_CHECK",
        }.get(domain, domain)

    @staticmethod
    def _description_for(proposal: RepairProposal) -> str:
        return (
            f"Repair {proposal.domain.lower().replace('_', ' ')} evidence for "
            f"{proposal.reason}; preserve all immutable trading policies."
        )
