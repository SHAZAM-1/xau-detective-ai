"""Deterministic decision gate for V1."""
from __future__ import annotations

from .models import Decision, Direction, RiskResult, Scenario


def decide(scenario: Scenario, risk: RiskResult, setup_score: int) -> Decision:
    if not 0 <= setup_score <= 100:
        raise ValueError("setup_score must be between 0 and 100")
    if scenario.direction is Direction.NO_TRADE:
        return Decision(Direction.NO_TRADE, setup_score, "NO_TRADE_SCENARIO", scenario, risk)
    if not risk.executable:
        return Decision(Direction.NO_TRADE, setup_score, f"RISK_VETO:{risk.reason}", scenario, risk)
    return Decision(scenario.direction, setup_score, "TRADE_ALLOWED", scenario, risk)
