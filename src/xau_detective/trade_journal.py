"""Deterministic append-only trade audit journals."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
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

def _normalize_timestamp(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

def _serialize(entry: TradeJournalEntry) -> str:
    data = asdict(entry)
    data["timestamp"] = _normalize_timestamp(entry.timestamp).isoformat()
    for field in ("volume", "entry", "stop_loss", "take_profit"):
        data[field] = str(data[field])
    return json.dumps(data, sort_keys=True, separators=(",", ":"))

def _deserialize(line: str) -> TradeJournalEntry:
    try:
        data = json.loads(line)
        return TradeJournalEntry(
            timestamp=_normalize_timestamp(datetime.fromisoformat(data["timestamp"])),
            idempotency_key=str(data["idempotency_key"]),
            symbol=str(data["symbol"]),
            direction=str(data["direction"]),
            volume=Decimal(str(data["volume"])),
            entry=Decimal(str(data["entry"])),
            stop_loss=Decimal(str(data["stop_loss"])),
            take_profit=Decimal(str(data["take_profit"])),
            source=str(data["source"]),
            status=str(data["status"]),
            reason=str(data["reason"]),
            order_id=None if data.get("order_id") is None else str(data["order_id"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_TRADE_JOURNAL_RECORD") from exc

class InMemoryTradeJournal:
    def __init__(self) -> None:
        self._entries: list[TradeJournalEntry] = []
    def append(self, entry: TradeJournalEntry) -> None:
        self._entries.append(entry)
    def entries(self) -> tuple[TradeJournalEntry, ...]:
        return tuple(self._entries)

class JsonlTradeJournal:
    """Durable append-only JSONL journal."""
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._entries: list[TradeJournalEntry] = []
        self._load()
    @property
    def path(self) -> Path:
        return self._path
    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    try:
                        self._entries.append(_deserialize(line))
                    except ValueError as exc:
                        raise ValueError(f"INVALID_TRADE_JOURNAL_RECORD:{line_number}") from exc
    def append(self, entry: TradeJournalEntry) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(_serialize(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._entries.append(entry)
    def entries(self) -> tuple[TradeJournalEntry, ...]:
        return tuple(self._entries)

def journal_entry_from_intent(*, intent: TradeIntent, status: str, reason: str, order_id: str | None = None, timestamp: datetime) -> TradeJournalEntry:
    return TradeJournalEntry(
        timestamp=timestamp, idempotency_key=intent.idempotency_key,
        symbol=intent.symbol, direction=intent.direction.value, volume=intent.volume,
        entry=intent.entry, stop_loss=intent.stop_loss, take_profit=intent.take_profit,
        source=intent.source.value, status=status, reason=reason, order_id=order_id,
    )
