"""Project Guardian: bounded self-repair orchestration.

The guardian may diagnose and repair engineering/runtime defects, but every
change is constrained by immutable project policy and must pass validation.
It never changes trading strategy, risk policy, live-execution locks, or the
project roadmap automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .audit_log import AuditEvent, AuditLog
from .audit_query import filter_events


class GuardianAction(str, Enum):
    OBSERVE = "OBSERVE"
    DIAGNOSE = "DIAGNOSE"
    REPAIR = "REPAIR"
    VALIDATE = "VALIDATE"
    LEARN = "LEARN"
    BLOCK = "BLOCK"


IMMUTABLE_PROJECT_POLICIES = frozenset(
    {
        "STRATEGY",
        "RISK_POLICY",
        "SL_TP_MODEL",
        "NO_TRADE_POLICY",
        "LIVE_EXECUTION_LOCK",
        "ROADMAP",
    }
)

SAFE_REPAIR_DOMAINS = frozenset(
    {
        "TESTS",
        "LINT",
        "IMPORTS",
        "RUNTIME_GUARDS",
        "LOGGING",
        "AUDIT_TRAIL",
        "MT5_ADAPTER",
        "DATA_VALIDATION",
        "ERROR_HANDLING",
        "DOCUMENTATION",
        "HEALTH_CHECK",
    }
)


@dataclass(frozen=True)
class GuardianFinding:
    category: str
    reason: str
    evidence_count: int


@dataclass(frozen=True)
class RepairProposal:
    domain: str
    reason: str
    allowed: bool
    requires_validation: bool = True


@dataclass(frozen=True)
class GuardianReport:
    safe: bool
    findings: tuple[GuardianFinding, ...]
    proposals: tuple[RepairProposal, ...]
    blocked_changes: tuple[str, ...]


class ProjectGuardian:
    """Single bounded control layer for runtime and engineering adaptation."""

    def __init__(
        self,
        audit_log: AuditLog,
        *,
        history_window: int = 100,
    ) -> None:
        if history_window < 1:
            raise ValueError("history_window must be positive")
        self._audit = audit_log
        self._history_window = history_window

    def inspect(
        self,
        *,
        trace_id: str,
        now: datetime,
    ) -> GuardianReport:
        events = self._audit.events()[-self._history_window :]
        findings: list[GuardianFinding] = []
        failures: dict[str, int] = {}

        for event in events:
            if event.status in {"BLOCKED", "REJECTED", "ERROR"} and event.reason:
                failures[event.reason] = failures.get(event.reason, 0) + 1

        for reason, count in sorted(failures.items()):
            if count >= 2:
                findings.append(
                    GuardianFinding(
                        category="REPEATED_FAILURE",
                        reason=reason,
                        evidence_count=count,
                    )
                )

        proposals = tuple(
            RepairProposal(
                domain=self._domain_for_finding(finding),
                reason=finding.reason,
                allowed=self._domain_for_finding(finding) in SAFE_REPAIR_DOMAINS,
            )
            for finding in findings
        )

        blocked = tuple(sorted(IMMUTABLE_PROJECT_POLICIES))
        safe = all(proposal.allowed for proposal in proposals)

        self._audit.append(
            AuditEvent(
                timestamp=now,
                trace_id=trace_id,
                event="project_guardian",
                status="SAFE" if safe else "GUARDED",
                reason="PROJECT_GUARDIAN_INSPECTION",
                details={
                    "findings": [
                        {
                            "category": item.category,
                            "reason": item.reason,
                            "evidence_count": item.evidence_count,
                        }
                        for item in findings
                    ],
                    "repair_domains": [item.domain for item in proposals],
                    "blocked_changes": list(blocked),
                },
            )
        )
        return GuardianReport(
            safe=safe,
            findings=tuple(findings),
            proposals=proposals,
            blocked_changes=blocked,
        )

    @staticmethod
    def _domain_for_finding(finding: GuardianFinding) -> str:
        reason = finding.reason
        if reason.startswith(("MT5_", "SYMBOL_", "EXECUTION_")):
            return "MT5_ADAPTER"
        if "AUDIT" in reason or "LOG" in reason:
            return "AUDIT_TRAIL"
        if "HEALTH" in reason or "RUFF" in reason or "TEST" in reason:
            return "HEALTH_CHECK"
        if reason.startswith(("INVALID_", "DATA_")):
            return "DATA_VALIDATION"
        if reason.startswith("IMPORT"):
            return "IMPORTS"
        return "ERROR_HANDLING"

    @staticmethod
    def validate_repair_domain(domain: str) -> bool:
        return domain in SAFE_REPAIR_DOMAINS

    @staticmethod
    def is_immutable_change(target: str) -> bool:
        return target in IMMUTABLE_PROJECT_POLICIES

    def evidence_for_reason(self, reason: str) -> tuple[AuditEvent, ...]:
        return filter_events(
            self._audit.events()[-self._history_window :],
            status="BLOCKED",
        ) + filter_events(
            self._audit.events()[-self._history_window :],
            status="REJECTED",
        )
