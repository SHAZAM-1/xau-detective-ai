"""Hard evidence gate between feature analysis and trade decision."""
from __future__ import annotations

from .evidence import EvidenceLedger
from .models import Decision, Direction, RiskResult, Scenario


def decide_from_evidence(
    scenario: Scenario,
    risk: RiskResult,
    ledger: EvidenceLedger,
    setup_score: int,
    *,
    min_independent_families: int = 3,
) -> Decision:
    if scenario.direction is Direction.NO_TRADE:
        return Decision(Direction.NO_TRADE, setup_score, "NO_TRADE_SCENARIO", scenario, risk)
    if ledger.direction is not scenario.direction:
        return Decision(Direction.NO_TRADE, setup_score, "EVIDENCE_DIRECTION_MISMATCH", scenario, risk)
    if ledger.has_conflict:
        return Decision(Direction.NO_TRADE, setup_score, "EVIDENCE_CONFLICT", scenario, risk)
    if ledger.independent_evidence_count < min_independent_families:
        return Decision(Direction.NO_TRADE, setup_score, "INSUFFICIENT_EVIDENCE", scenario, risk)
    if not risk.executable:
        return Decision(Direction.NO_TRADE, setup_score, f"RISK_VETO:{risk.reason}", scenario, risk)
    return Decision(scenario.direction, setup_score, "TRADE_ALLOWED", scenario, risk)
