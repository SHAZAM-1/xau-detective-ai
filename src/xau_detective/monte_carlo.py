"""Monte Carlo stress testing for closed-trade research.

This is an offline risk-analysis primitive. It does not create signals or
predict future market outcomes. Resampling is used to stress-test the observed
trade-return distribution and estimate drawdown/ruin frequencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import random

from .backtest import BacktestResult


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
    average_max_loss_streak: Decimal
    median_max_loss_streak: Decimal
    worst_max_loss_streak: int
    average_r: Decimal | None
    median_r: Decimal | None
    worst_r: Decimal | None


def _percentile(values: list[Decimal], fraction: Decimal) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    position = (len(ordered) - 1) * float(fraction)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = Decimal(str(position - lower))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _max_loss_streak(returns: list[Decimal]) -> int:
    maximum = 0
    current = 0
    for value in returns:
        if value < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def run_monte_carlo(
    trade_returns: tuple[Decimal, ...],
    *,
    simulations: int = 5000,
    trades_per_simulation: int | None = None,
    initial_equity: Decimal = Decimal("100"),
    ruin_threshold: Decimal = Decimal("50"),
    seed: int = 42,
    trade_r_multiples: tuple[Decimal, ...] | None = None,
) -> MonteCarloResult:
    """Bootstrap observed closed trades with replacement.

    trade_returns must use the same unit for every trade, such as account
    currency. If trade_r_multiples is supplied, it must contain the
    risk-normalized R result for each corresponding trade. The paired trade
    observations are resampled together so the return/R relationship is not
    broken by independent shuffling.

    Monte Carlo is downstream of the observed trade set: it must not be used
    to select strategy parameters or turn in-sample performance into an
    out-of-sample claim.
    """
    try:
        trade_returns = tuple(Decimal(str(value)) for value in trade_returns)
        initial_equity = Decimal(str(initial_equity))
        ruin_threshold = Decimal(str(ruin_threshold))
        if trade_r_multiples is not None:
            trade_r_multiples = tuple(
                Decimal(str(value)) for value in trade_r_multiples
            )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Monte Carlo inputs must be finite numeric values") from exc

    numeric_inputs = (*trade_returns, initial_equity, ruin_threshold)
    if trade_r_multiples is not None:
        numeric_inputs += trade_r_multiples
    if any(not value.is_finite() for value in numeric_inputs):
        raise ValueError("Monte Carlo inputs must be finite numeric values")

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
    if trade_r_multiples is not None and len(trade_r_multiples) != len(trade_returns):
        raise ValueError("trade_r_multiples must match trade_returns length")

    rng = random.Random(seed)
    finals: list[Decimal] = []
    drawdowns: list[Decimal] = []
    loss_streaks: list[Decimal] = []
    r_averages: list[Decimal] = []
    ruins = 0

    observations = tuple(zip(trade_returns, trade_r_multiples or ()))
    for _ in range(simulations):
        equity = initial_equity
        peak = equity
        max_drawdown = Decimal(0)
        sampled_returns: list[Decimal] = []
        sampled_r: list[Decimal] = []
        ruined = False

        for _ in range(trades_per_simulation):
            if trade_r_multiples is None:
                trade_return = rng.choice(trade_returns)
            else:
                trade_return, trade_r = rng.choice(observations)
                sampled_r.append(trade_r)

            sampled_returns.append(trade_return)
            equity += trade_return
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            if equity <= ruin_threshold:
                ruined = True
                break

        finals.append(equity)
        drawdowns.append(max_drawdown)
        loss_streaks.append(Decimal(_max_loss_streak(sampled_returns)))
        if sampled_r:
            r_averages.append(
                sum(sampled_r, Decimal(0)) / Decimal(len(sampled_r))
            )
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
        average_max_loss_streak=sum(loss_streaks, Decimal(0)) / Decimal(simulations),
        median_max_loss_streak=_percentile(loss_streaks, Decimal("0.50")),
        worst_max_loss_streak=int(max(loss_streaks)),
        average_r=(
            sum(r_averages, Decimal(0)) / Decimal(len(r_averages))
            if r_averages
            else None
        ),
        median_r=_percentile(r_averages, Decimal("0.50")) if r_averages else None,
        worst_r=min(r_averages) if r_averages else None,
    )


def run_backtest_monte_carlo(
    result: BacktestResult,
    *,
    simulations: int = 5000,
    trades_per_simulation: int | None = None,
    initial_equity: Decimal = Decimal("100"),
    ruin_threshold: Decimal = Decimal("50"),
    seed: int = 42,
) -> MonteCarloResult:
    """Run Monte Carlo stress testing directly from a closed backtest result.

    The backtest trade list is treated as a fixed research observation set.
    Net PnL and risk-normalized R are resampled as paired observations; no
    strategy parameters, signals, or policy definitions are changed.
    """
    if not result.trades:
        raise ValueError("backtest result must contain at least one trade")

    returns = tuple(trade.net_pnl for trade in result.trades)
    r_multiples = tuple(
        trade.net_pnl / trade.risk_amount
        for trade in result.trades
        if trade.risk_amount > 0
    )
    if len(r_multiples) != len(returns):
        raise ValueError("all backtest trades must have positive risk_amount")

    return run_monte_carlo(
        returns,
        simulations=simulations,
        trades_per_simulation=trades_per_simulation,
        initial_equity=initial_equity,
        ruin_threshold=ruin_threshold,
        seed=seed,
        trade_r_multiples=r_multiples,
    )
