"""Event-driven OHLC backtesting with explicit trading frictions.

Signals are evaluated on a closed candle and entered on the next candle open.
Spread, slippage and commission are included so research results are not based
on frictionless fills. When stop and target are both touched in one candle,
the conservative assumption is that the stop is hit first.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from .market import Candle

from .models import Direction


@dataclass(frozen=True)
class TradePlan:
    direction: Direction
    stop_loss: Decimal
    take_profit: Decimal
    volume: Decimal


@dataclass(frozen=True)
class BacktestConfig:
    tick_size: Decimal
    tick_value: Decimal
    spread: Decimal = Decimal(0)
    slippage: Decimal = Decimal(0)
    commission_per_lot_per_side: Decimal = Decimal(0)


@dataclass(frozen=True)
class BacktestTrade:
    signal_index: int
    entry_index: int
    exit_index: int
    direction: Direction
    entry_price: Decimal
    exit_price: Decimal
    volume: Decimal
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[BacktestTrade, ...]
    net_pnl: Decimal
    wins: int
    losses: int
    breakevens: int
    max_drawdown: Decimal


SignalFunction = Callable[[int, tuple[Candle, ...]], TradePlan | None]


def _price_to_pnl(
    direction: Direction,
    entry: Decimal,
    exit: Decimal,
    volume: Decimal,
    tick_size: Decimal,
    tick_value: Decimal,
) -> Decimal:
    if tick_size <= 0 or tick_value <= 0:
        raise ValueError("tick_size and tick_value must be positive")
    movement = exit - entry if direction is Direction.BUY else entry - exit
    return movement / tick_size * tick_value * volume


def _fill_entry(open_price: Decimal, direction: Direction, config: BacktestConfig) -> Decimal:
    half_spread = config.spread / Decimal(2)
    if direction is Direction.BUY:
        return open_price + half_spread + config.slippage
    return open_price - half_spread - config.slippage


def _fill_exit(price: Decimal, direction: Direction, config: BacktestConfig) -> Decimal:
    half_spread = config.spread / Decimal(2)
    if direction is Direction.BUY:
        return price - half_spread - config.slippage
    return price + half_spread + config.slippage


def run_backtest(
    candles: tuple[Candle, ...],
    signal: SignalFunction,
    config: BacktestConfig,
) -> BacktestResult:
    if len(candles) < 2:
        return BacktestResult((), Decimal(0), 0, 0, 0, Decimal(0))
    if config.spread < 0 or config.slippage < 0 or config.commission_per_lot_per_side < 0:
        raise ValueError("trading frictions cannot be negative")

    trades: list[BacktestTrade] = []
    i = 0
    while i < len(candles) - 1:
        plan = signal(i, candles[: i + 1])
        if plan is None or plan.direction is Direction.NO_TRADE:
            i += 1
            continue
        if plan.direction not in (Direction.BUY, Direction.SELL) or plan.volume <= 0:
            i += 1
            continue
        if plan.stop_loss <= 0 or plan.take_profit <= 0:
            i += 1
            continue

        entry_index = i + 1
        entry = _fill_entry(candles[entry_index].open, plan.direction, config)
        exit_index = None
        raw_exit = None
        reason = None

        for j in range(entry_index, len(candles)):
            candle = candles[j]
            if plan.direction is Direction.BUY:
                stop_hit = candle.low <= plan.stop_loss
                target_hit = candle.high >= plan.take_profit
            else:
                stop_hit = candle.high >= plan.stop_loss
                target_hit = candle.low <= plan.take_profit

            if stop_hit:
                raw_exit, reason, exit_index = plan.stop_loss, "STOP_LOSS", j
                break
            if target_hit:
                raw_exit, reason, exit_index = plan.take_profit, "TAKE_PROFIT", j
                break

        if exit_index is None:
            exit_index = len(candles) - 1
            raw_exit = candles[-1].close
            reason = "END_OF_DATA"

        exit_price = _fill_exit(raw_exit, plan.direction, config)
        gross = _price_to_pnl(
            plan.direction,
            entry,
            exit_price,
            plan.volume,
            config.tick_size,
            config.tick_value,
        )
        commission = (
            config.commission_per_lot_per_side * plan.volume * Decimal(2)
        )
        net = gross - commission

        trades.append(
            BacktestTrade(
                i,
                entry_index,
                exit_index,
                plan.direction,
                entry,
                exit_price,
                plan.volume,
                gross,
                commission,
                net,
                reason,
            )
        )
        i = exit_index + 1

    net_pnl = sum((trade.net_pnl for trade in trades), Decimal(0))
    wins = sum(trade.net_pnl > 0 for trade in trades)
    losses = sum(trade.net_pnl < 0 for trade in trades)
    breakevens = len(trades) - wins - losses

    equity = Decimal(0)
    peak = Decimal(0)
    max_drawdown = Decimal(0)
    for trade in trades:
        equity += trade.net_pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return BacktestResult(
        tuple(trades),
        net_pnl,
        wins,
        losses,
        breakevens,
        max_drawdown,
    )
