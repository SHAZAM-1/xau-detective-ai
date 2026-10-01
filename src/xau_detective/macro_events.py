"""Research-only macro event context for XAUUSD.

This module normalizes scheduled U.S. macro events without assigning a trading
direction. Event timing is explicit so future data pipelines can prevent
look-ahead leakage around FOMC, CPI, PCE and NFP releases.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MacroEventType(str, Enum):
    FOMC = "FOMC"
    CPI = "CPI"
    PCE = "PCE"
    NFP = "NFP"


@dataclass(frozen=True)
class MacroEvent:
    event_type: MacroEventType
    release_time: datetime
    actual: float | None = None
    consensus: float | None = None
    previous: float | None = None


@dataclass(frozen=True)
class MacroContext:
    event_type: MacroEventType
    state: str
    release_time: datetime
    surprise: float | None
    evidence: tuple[str, ...]


def classify_macro_event(event: MacroEvent, *, now: datetime) -> MacroContext:
    """Return descriptive event state using only information available at now."""
    if now < event.release_time:
        state = "UPCOMING"
    elif event.actual is None:
        state = "RELEASED_DATA_UNAVAILABLE"
    else:
        state = "RELEASED"

    surprise = None
    evidence: list[str] = [f"EVENT={event.event_type.value}", f"STATE={state}"]

    if state == "RELEASED" and event.consensus is not None:
        surprise = event.actual - event.consensus
        if surprise > 0:
            evidence.append("SURPRISE_ABOVE_CONSENSUS")
        elif surprise < 0:
            evidence.append("SURPRISE_BELOW_CONSENSUS")
        else:
            evidence.append("SURPRISE_IN_LINE")

    if event.previous is not None and event.actual is not None:
        if event.actual > event.previous:
            evidence.append("ACTUAL_ABOVE_PREVIOUS")
        elif event.actual < event.previous:
            evidence.append("ACTUAL_BELOW_PREVIOUS")
        else:
            evidence.append("ACTUAL_EQUALS_PREVIOUS")

    return MacroContext(
        event_type=event.event_type,
        state=state,
        release_time=event.release_time,
        surprise=surprise,
        evidence=tuple(evidence),
    )
