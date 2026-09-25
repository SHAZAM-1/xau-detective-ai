"""Minimal scenario engine; indicators remain inputs, not trading truth."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import Direction, Scenario


@dataclass(frozen=True)
class ScenarioInput:
    trend: Direction
    structure: Direction
    momentum: Direction
    volatility_ok: bool
    reward_risk: Decimal
    min_reward_risk: Decimal = Decimal("2.0")


def generate_scenarios(data: ScenarioInput) -> tuple[Scenario, ...]:
    scenarios: list[Scenario] = []
    if data.reward_risk < data.min_reward_risk or not data.volatility_ok:
        return (Scenario(Direction.NO_TRADE, ("risk_filter",), "conditions_not_satisfied"),)

    for direction in (Direction.BUY, Direction.SELL):
        aligned = sum(x == direction for x in (data.trend, data.structure, data.momentum))
        if aligned >= 2:
            scenarios.append(
                Scenario(
                    direction,
                    evidence=("trend", "structure", "momentum"),
                    invalidation=f"{direction.value}_thesis_invalidated",
                )
            )

    return tuple(scenarios) or (Scenario(Direction.NO_TRADE, ("conflicting_evidence",), "no_aligned_scenario"),)
