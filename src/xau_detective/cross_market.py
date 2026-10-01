"""Research-only cross-market context for Gold.

This module defines a normalized interface for DXY and U.S. real-yield context
without fetching data or treating correlation as causation. It is intentionally
outside the production decision gate until historical incremental value is
validated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class CrossMarketObservation:
    """One timestamp-aligned external-market observation."""

    timestamp: datetime
    dxy_close: Decimal | None = None
    real_yield: Decimal | None = None
    dxy_return: Decimal | None = None
    real_yield_change: Decimal | None = None


@dataclass(frozen=True)
class CrossMarketContext:
    """Descriptive Gold context derived from aligned external observations."""

    dxy_state: str
    real_yield_state: str
    gold_context: str
    evidence: tuple[str, ...]


def classify_cross_market_context(
    observation: CrossMarketObservation,
) -> CrossMarketContext:
    """Classify observable direction only; no causal or predictive claim."""
    evidence: list[str] = []

    if observation.dxy_return is None:
        dxy_state = "UNKNOWN"
    elif observation.dxy_return > 0:
        dxy_state = "UP"
        evidence.append("DXY_UP")
    elif observation.dxy_return < 0:
        dxy_state = "DOWN"
        evidence.append("DXY_DOWN")
    else:
        dxy_state = "FLAT"

    if observation.real_yield_change is None:
        yield_state = "UNKNOWN"
    elif observation.real_yield_change > 0:
        yield_state = "UP"
        evidence.append("REAL_YIELD_UP")
    elif observation.real_yield_change < 0:
        yield_state = "DOWN"
        evidence.append("REAL_YIELD_DOWN")
    else:
        yield_state = "FLAT"

    if dxy_state == "DOWN" and yield_state == "DOWN":
        gold_context = "GOLD_SUPPORTIVE_CONTEXT"
    elif dxy_state == "UP" and yield_state == "UP":
        gold_context = "GOLD_HEADWIND_CONTEXT"
    elif "UNKNOWN" in (dxy_state, yield_state):
        gold_context = "INSUFFICIENT_CROSS_MARKET_DATA"
    else:
        gold_context = "MIXED_CROSS_MARKET_CONTEXT"

    evidence.append(f"DXY_STATE={dxy_state}")
    evidence.append(f"REAL_YIELD_STATE={yield_state}")
    evidence.append(f"GOLD_CONTEXT={gold_context}")

    return CrossMarketContext(
        dxy_state=dxy_state,
        real_yield_state=yield_state,
        gold_context=gold_context,
        evidence=tuple(evidence),
    )
