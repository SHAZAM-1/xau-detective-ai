"""Deterministic validation metrics derived from backtest results.

Only metrics directly supported by the current backtest result contract are
computed here. Metrics requiring additional data, such as average R or
exposure, are intentionally not inferred from incomplete fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .backtest import BacktestResult


@dataclass(frozen=True)
class BacktestMetrics:
    """Validation metrics that can be calculated without extra assumptions."""

    trade_count: int
    net_pnl: Decimal
    expectancy: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    win_rate: Decimal
    max_loss_streak: int


def calculate_backtest_metrics(result: BacktestResult) -> BacktestMetrics:
    """Calculate deterministic summary metrics from a backtest result."""
    trade_count = len(result.trades)
    if trade_count == 0:
        return BacktestMetrics(
            trade_count=0,
            net_pnl=Decimal(0),
            expectancy=Decimal(0),
            profit_factor=None,
            max_drawdown=Decimal(0),
            win_rate=Decimal(0),
            max_loss_streak=0,
        )

    gross_profit = sum(
        (trade.net_pnl for trade in result.trades if trade.net_pnl > 0),
        Decimal(0),
    )
    gross_loss = sum(
        (-trade.net_pnl for trade in result.trades if trade.net_pnl < 0),
        Decimal(0),
    )

    profit_factor = None if gross_loss == 0 else gross_profit / gross_loss
    max_loss_streak = 0
    current_loss_streak = 0
    for trade in result.trades:
        if trade.net_pnl < 0:
            current_loss_streak += 1
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        else:
            current_loss_streak = 0

    return BacktestMetrics(
        trade_count=trade_count,
        net_pnl=result.net_pnl,
        expectancy=result.net_pnl / Decimal(trade_count),
        profit_factor=profit_factor,
        max_drawdown=result.max_drawdown,
        win_rate=Decimal(result.wins) / Decimal(trade_count),
        max_loss_streak=max_loss_streak,
    )
