"""Monte Carlo stress testing for closed-trade research.

This is an offline risk-analysis primitive. It does not create signals or
predict future market outcomes. Resampling is used to stress-test the observed
trade-return distribution and estimate drawdown/ruin frequencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import random


@dataclass(frozen=True)
class MonteCarloResult:
    simulations: int
    trades_per_simulation: int
    initial_equity: Decimal
    ruin_threshold: Decimal
    ruin_count: int
    ruin_frequency: Decimal
    average_final_equity: Decimal
    median_final_equity: Decimal
    worst_final_equity: Decimal
    average_max_drawdown: Decimal
    median_max_drawdown: Decimal
    worst_max_drawdown: Decimal


def _percentile(values: list[Decimal], fraction: Decimal) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    position = (len(ordered) - 1) * float(fraction)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = Decimal(str(position - lower))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def run_monte_carlo(
    trade_returns: tuple[Decimal, ...],
    *,
    simulations: int = 5000,
    trades_per_simulation: int | None = None,
    initial_equity: Decimal = Decimal("100"),
    ruin_threshold: Decimal = Decimal("50"),
    seed: int = 42,
) -> MonteCarloResult:
    """Bootstrap observed trade returns with replacement.

    trade_returns must use the same unit for every trade, such as account
    currency or a normalized R multiple. This function does not convert
    between those units.
    """
    if not trade_returns:
        raise ValueError("trade_returns cannot be empty")
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    if trades_per_simulation is None:
        trades_per_simulation = len(trade_returns)
    if trades_per_simulation <= 0:
        raise ValueError("trades_per_simulation must be positive")
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")
    if ruin_threshold < 0 or ruin_threshold >= initial_equity:
        raise ValueError("ruin_threshold must be >= 0 and below initial_equity")

    rng = random.Random(seed)
    finals: list[Decimal] = []
    drawdowns: list[Decimal] = []
    ruins = 0

    for _ in range(simulations):
        equity = initial_equity
        peak = equity
        max_drawdown = Decimal(0)
        ruined = False

        for _ in range(trades_per_simulation):
            equity += rng.choice(trade_returns)
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            if equity <= ruin_threshold:
                ruined = True
                break

        finals.append(equity)
        drawdowns.append(max_drawdown)
        ruins += int(ruined)

    return MonteCarloResult(
        simulations=simulations,
        trades_per_simulation=trades_per_simulation,
        initial_equity=initial_equity,
        ruin_threshold=ruin_threshold,
        ruin_count=ruins,
        ruin_frequency=Decimal(ruins) / Decimal(simulations),
        average_final_equity=sum(finals, Decimal(0)) / Decimal(simulations),
        median_final_equity=_percentile(finals, Decimal("0.50")),
        worst_final_equity=min(finals),
        average_max_drawdown=sum(drawdowns, Decimal(0)) / Decimal(simulations),
        median_max_drawdown=_percentile(drawdowns, Decimal("0.50")),
        worst_max_drawdown=max(drawdowns),
    )
