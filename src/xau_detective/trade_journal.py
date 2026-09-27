"""Deterministic trade audit journal.

The journal records decisions and execution outcomes without making trading
decisions. Persistence is intentionally abstract so a database/file adapter
can be added later without changing the execution engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .demo_execution import TradeIntent


@dataclass(frozen=True)


class TradeJournalEntry:
    timestamp: datetime
    idempotency_key: str
    symbol: str
    direction: str
    volume: Decimal
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    source: str
    status: str
    reason: str
    order_id: str | None = None


class TradeJournal(Protocol):
    def append(self, entry: TradeJournalEntry) -> None: ...
    def entries(self) -> tuple[TradeJournalEntry, ...]: ...


class InMemoryTradeJournal:
    """Reference journal used by tests and local Demo sessions."""

    def __init__(self) -> None:
        self._entries: list[TradeJournalEntry] = []

    def append(self, entry: TradeJournalEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> tuple[TradeJournalEntry, ...]:
        return tuple(self._entries)


def journal_entry_from_intent(
    *,
    intent: TradeIntent,
    status: str,
    reason: str,
    order_id: str | None = None,
    timestamp: datetime,
) -> TradeJournalEntry:
    return TradeJournalEntry(
        timestamp=timestamp,
        idempotency_key=intent.idempotency_key,
        symbol=intent.symbol,
        direction=intent.direction.value,
        volume=intent.volume,
        entry=intent.entry,
        stop_loss=intent.stop_loss,
        take_profit=intent.take_profit,
        source=intent.source.value,
        status=status,
        reason=reason,
        order_id=order_id,
    )
