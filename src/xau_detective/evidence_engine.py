"""Translate independent feature families into an auditable evidence ledger."""
from __future__ import annotations

from .evidence import EvidenceLedger
from .models import Direction
from .regime import RegimeSnapshot, TrendState, VolatilityState
from .structure import StructureSnapshot


def build_evidence(
    direction: Direction,
    regime: RegimeSnapshot,
    structure: StructureSnapshot,
    *,
    momentum: float | None = None,
    min_independent_families: int = 3,
) -> EvidenceLedger:
    ledger = EvidenceLedger(direction)

    if direction is Direction.NO_TRADE:
        ledger.add_warning("NO_TRADE_DIRECTION")
        return ledger

    # Family 1: regime/trend
    if direction is Direction.BUY and regime.trend is TrendState.UP:
        ledger.add_support("regime_trend_up")
    elif direction is Direction.SELL and regime.trend is TrendState.DOWN:
        ledger.add_support("regime_trend_down")
    elif regime.trend in (TrendState.UP, TrendState.DOWN):
        ledger.add_contradiction("regime_trend_conflict")
    else:
        ledger.add_warning("regime_not_directional")

    # Family 2: market structure
    if structure.direction is direction:
        ledger.add_support("structure_breakout_alignment")
    elif structure.direction is not Direction.NO_TRADE:
        ledger.add_contradiction("structure_opposes_direction")
    else:
        ledger.add_warning("structure_not_confirmed")

    # Family 3: momentum
    if momentum is not None:
        if direction is Direction.BUY and momentum > 0:
            ledger.add_support("momentum_positive")
        elif direction is Direction.SELL and momentum < 0:
            ledger.add_support("momentum_negative")
        else:
            ledger.add_contradiction("momentum_opposes_direction")
    else:
        ledger.add_warning("momentum_missing")

    # Volatility is a context filter, not directional evidence.
    if regime.volatility is VolatilityState.HIGH:
        ledger.add_warning("high_volatility_execution_risk")
    elif regime.volatility is VolatilityState.UNKNOWN:
        ledger.add_warning("volatility_unknown")

    if ledger.independent_evidence_count < min_independent_families:
        ledger.add_warning("INSUFFICIENT_INDEPENDENT_EVIDENCE")

    return ledger
