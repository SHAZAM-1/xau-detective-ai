from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog, JsonlAuditLog


def event(trace="cycle-1", reason="TEST"):
    return AuditEvent(
        timestamp=datetime(2026, 9, 28, 1, tzinfo=timezone.utc),
        trace_id=trace,
        event="decision",
        status="REJECTED",
        reason=reason,
        symbol="XAUUSD",
        direction="BUY",
        volume=Decimal("0.02"),
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4020"),
        details={"regime": "TREND", "evidence_count": 5},
    )


def test_in_memory_audit_preserves_trace_and_trade_details():
    log = InMemoryAuditLog()
    log.append(event())
    saved = log.events()[0]
    assert saved.trace_id == "cycle-1"
    assert saved.symbol == "XAUUSD"
    assert saved.volume == Decimal("0.02")
    assert saved.details["evidence_count"] == 5


def test_jsonl_audit_survives_restart(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    log.append(event("restart-1", "BROKER_SUBMISSION_PENDING"))
    assert path.read_text(encoding="utf-8").count("\n") == 1

    reopened = JsonlAuditLog(path)
    saved = reopened.events()[0]
    assert saved.trace_id == "restart-1"
    assert saved.reason == "BROKER_SUBMISSION_PENDING"
    assert saved.volume == Decimal("0.02")


def test_jsonl_audit_is_append_only_and_rejects_corrupt_records(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    log.append(event())
    log.append(event("cycle-2", "SECOND"))
    assert [item.trace_id for item in log.events()] == ["cycle-1", "cycle-2"]

    path.write_text(path.read_text(encoding="utf-8") + '{"broken":true}\n', encoding="utf-8")
    try:
        JsonlAuditLog(path)
    except ValueError as exc:
        assert str(exc) == "INVALID_AUDIT_EVENT:3"
    else:
        raise AssertionError("corrupt audit records must fail closed")
