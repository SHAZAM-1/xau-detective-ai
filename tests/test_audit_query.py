from datetime import UTC, datetime
from decimal import Decimal

from xau_detective.audit_log import AuditEvent, InMemoryAuditLog
from xau_detective.audit_query import filter_events, summarize_events


def make(trace, event, status, symbol="XAUUSD"):
    return AuditEvent(
        timestamp=datetime(2026, 9, 28, 1, tzinfo=UTC),
        trace_id=trace,
        event=event,
        status=status,
        symbol=symbol,
        volume=Decimal("0.02"),
    )


def test_filter_events_supports_trace_event_status_symbol():
    log = InMemoryAuditLog()
    log.append(make("a", "cycle_started", "STARTED"))
    log.append(make("a", "execution", "SUBMITTED"))
    log.append(make("b", "execution", "REJECTED"))
    log.append(make("c", "execution", "SUBMITTED", "EURUSD"))

    found = filter_events(log.events(), trace_id="a", event="execution", status="SUBMITTED")
    assert len(found) == 1
    assert found[0].trace_id == "a"

    assert len(filter_events(log.events(), symbol="EURUSD")) == 1


def test_summary_is_dashboard_friendly():
    events = (
        make("a", "cycle_started", "STARTED"),
        make("a", "trade_intent", "READY"),
        make("a", "execution", "SUBMITTED"),
        make("a", "cycle_finished", "SUCCESS"),
        make("b", "cycle_started", "STARTED"),
        make("b", "cycle_finished", "REJECTED"),
        make("b", "recovery", "REQUIRES_REVIEW"),
    )
    summary = summarize_events(events)
    assert summary.total_events == 7
    assert summary.started_cycles == 2
    assert summary.finished_cycles == 2
    assert summary.trade_intents == 1
    assert summary.submitted == 1
    assert summary.rejected == 1
    assert summary.recoveries == 1
    assert summary.recovery_reviews == 1
