"""Session context features using explicit UTC windows.

These windows are research defaults, not a claim about broker/exchange session
boundaries. Production use should load broker timezone/session metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class SessionSnapshot:
    label: str
    overlap: str | None


# UTC research windows. They cover the full weekday trading cycle and overlap
# around the London/New York handoffs. ASIA crosses midnight.
_WINDOWS = (
    ("ASIA", time(21, 0), time(8, 0)),
    ("LONDON", time(7, 0), time(16, 0)),
    ("NEW_YORK", time(13, 0), time(21, 0)),
)


def _in_window(value: time, start: time, end: time) -> bool:
    if start < end:
        return start <= value < end
    return value >= start or value < end


def classify_session(timestamp: datetime) -> SessionSnapshot:
    hour_minute = timestamp.time().replace(second=0, microsecond=0)
    active = [
        name for name, start, end in _WINDOWS
        if _in_window(hour_minute, start, end)
    ]

    if len(active) == 0:
        return SessionSnapshot("OFF_SESSION", None)
    if len(active) == 1:
        return SessionSnapshot(active[0], None)
    return SessionSnapshot(active[0], "+".join(active))
