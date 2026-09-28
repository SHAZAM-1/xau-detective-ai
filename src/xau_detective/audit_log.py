"""Structured append-only runtime audit logging for trading operations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class AuditEvent:
    timestamp: datetime
    trace_id: str
    event: str
    status: str
    reason: str = ""
    symbol: str | None = None
    direction: str | None = None
    volume: Decimal | None = None
    entry: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    order_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class AuditLog(Protocol):
    def append(self, event: AuditEvent) -> None: ...
    def events(self) -> tuple[AuditEvent, ...]: ...


def _normalize_timestamp(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _normalize_timestamp(value).isoformat()
    raise TypeError(f"UNSERIALIZABLE_AUDIT_VALUE:{type(value).__name__}")


def _serialize(event: AuditEvent) -> str:
    data = asdict(event)
    data["timestamp"] = _normalize_timestamp(event.timestamp).isoformat()
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_json_default)


def _deserialize(line: str) -> AuditEvent:
    try:
        data = json.loads(line)
        return AuditEvent(
            timestamp=_normalize_timestamp(datetime.fromisoformat(data["timestamp"])),
            trace_id=str(data["trace_id"]),
            event=str(data["event"]),
            status=str(data["status"]),
            reason=str(data.get("reason", "")),
            symbol=None if data.get("symbol") is None else str(data["symbol"]),
            direction=None if data.get("direction") is None else str(data["direction"]),
            volume=None if data.get("volume") is None else Decimal(str(data["volume"])),
            entry=None if data.get("entry") is None else Decimal(str(data["entry"])),
            stop_loss=None if data.get("stop_loss") is None else Decimal(str(data["stop_loss"])),
            take_profit=None if data.get("take_profit") is None else Decimal(str(data["take_profit"])),
            order_id=None if data.get("order_id") is None else str(data["order_id"]),
            details=dict(data.get("details") or {}),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_AUDIT_EVENT") from exc


class InMemoryAuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)


class JsonlAuditLog:
    """Durable append-only JSONL event stream suitable for dashboards and replay."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._events: list[AuditEvent] = []
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
                        self._events.append(_deserialize(line))
                    except ValueError as exc:
                        raise ValueError(f"INVALID_AUDIT_EVENT:{line_number}") from exc

    def append(self, event: AuditEvent) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(_serialize(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._events.append(event)

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
