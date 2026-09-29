"""Tests for the bounded Project Guardian."""
from datetime import UTC, datetime

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.project_guardian import (
    IMMUTABLE_PROJECT_POLICIES,
    ProjectGuardian,
    SAFE_REPAIR_DOMAINS,
)


def test_guardian_detects_repeated_runtime_failure_and_preserves_policy():
    audit = InMemoryAuditLog()
    for index in range(2):
        audit.append(
            AuditEvent(
                timestamp=datetime(2026, 9, 28, 12, index, tzinfo=UTC),
                trace_id=f"t-{index}",
                event="runtime_failure",
                status="REJECTED",
                reason="MT5_TICK_UNAVAILABLE",
            )
        )

    report = ProjectGuardian(audit).inspect(
        trace_id="guardian-1",
        now=datetime(2026, 9, 28, 12, 5, tzinfo=UTC),
    )

    assert report.safe is True
    assert report.findings[0].reason == "MT5_TICK_UNAVAILABLE"
    assert report.proposals[0].domain == "MT5_ADAPTER"
    assert IMMUTABLE_PROJECT_POLICIES.issubset(report.blocked_changes)
    assert audit.events()[-1].event == "project_guardian"


def test_guardian_blocks_unknown_repair_domains():
    assert ProjectGuardian.validate_repair_domain("STRATEGY") is False
    assert ProjectGuardian.is_immutable_change("STRATEGY") is True
    assert "TESTS" in SAFE_REPAIR_DOMAINS


def test_guardian_immutable_namespace_blocks_scoped_policy_targets():
    for policy in IMMUTABLE_PROJECT_POLICIES:
        assert ProjectGuardian.is_immutable_change(f"{policy}:DETAIL") is True


def test_guardian_does_not_treat_safe_domain_prefix_as_immutable():
    assert ProjectGuardian.is_immutable_change("TESTS:DETAIL") is False


def test_guardian_clean_history_is_safe():
    audit = InMemoryAuditLog()
    report = ProjectGuardian(audit).inspect(
        trace_id="guardian-clean",
        now=datetime(2026, 9, 28, 12, tzinfo=UTC),
    )
    assert report.safe is True
    assert report.findings == ()
    assert report.proposals == ()
