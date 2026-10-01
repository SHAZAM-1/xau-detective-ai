"""Query and summarize structured audit events for tracking and dashboards."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .audit_log import AuditEvent


@dataclass(frozen=True)
class AuditSummary:
    total_events: int
    started_cycles: int
    finished_cycles: int
    trade_intents: int
    submitted: int
    rejected: int
    recoveries: int
    recovery_reviews: int


def filter_events(
    events: Iterable[AuditEvent],
    *,
    trace_id: str | None = None,
    event: str | None = None,
    status: str | None = None,
    symbol: str | None = None,
    since: datetime | None = None,
) -> tuple[AuditEvent, ...]:
    """Return deterministic event filters without mutating the source log."""
    result = []
    for item in events:
        if trace_id is not None and item.trace_id != trace_id:
            continue
        if event is not None and item.event != event:
            continue
        if status is not None and item.status != status:
            continue
        if symbol is not None and item.symbol != symbol:
            continue
        if since is not None and item.timestamp < since:
            continue
        result.append(item)
    return tuple(result)


def summarize_events(events: Iterable[AuditEvent]) -> AuditSummary:
    """Build dashboard counters from the same append-only event stream."""
    items = tuple(events)
    return AuditSummary(
        total_events=len(items),
        started_cycles=sum(item.event == "cycle_started" for item in items),
        finished_cycles=sum(item.event == "cycle_finished" for item in items),
        trade_intents=sum(item.event == "trade_intent" for item in items),
        submitted=sum(item.event == "execution" and item.status == "SUBMITTED" for item in items),
        rejected=sum(item.status == "REJECTED" for item in items),
        recoveries=sum(item.event == "recovery" for item in items),
        recovery_reviews=sum(
            item.event == "recovery" and item.status == "REQUIRES_REVIEW" for item in items
        ),
    )
