"""Net-R outcome labeling for leakage-safe trading research.

Labels are computed from closed-candle signals using the same explicit
execution frictions as the backtest/paper engine. They are research labels,
not live trade instructions.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .market import Candle
from .models import BrokerSpec, Direction


@dataclass(frozen=True)
class NetROutcomeConfig:
    spread: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    commission_per_lot_per_side: Decimal = Decimal("0")
    execution_delay_bars: int = 1


@dataclass(frozen=True)
class NetROutcome:
    signal_index: int
    entry_index: int
    exit_index: int
    direction: Direction
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
    initial_risk: Decimal
    gross_r: Decimal
    net_r: Decimal
    exit_reason: str


def _fill_entry(open_price: Decimal, direction: Direction, config: NetROutcomeConfig) -> Decimal:
    half = config.spread / Decimal(2)
    return open_price + half + config.slippage if direction is Direction.BUY else open_price - half - config.slippage


def _fill_exit(price: Decimal, direction: Direction, config: NetROutcomeConfig) -> Decimal:
    half = config.spread / Decimal(2)
    return price - half - config.slippage if direction is Direction.BUY else price + half + config.slippage


def _pnl(direction: Direction, entry: Decimal, exit_price: Decimal, volume: Decimal, broker: BrokerSpec) -> Decimal:
    movement = exit_price - entry if direction is Direction.BUY else entry - exit_price
    return movement / broker.tick_size * broker.tick_value * volume


def label_trade_outcome(
    candles: tuple[Candle, ...],
    *,
    signal_index: int,
    direction: Direction,
    stop_loss: Decimal,
    take_profit: Decimal,
    volume: Decimal,
    broker: BrokerSpec,
    config: NetROutcomeConfig = NetROutcomeConfig(),
) -> NetROutcome | None:
    """Label one closed-candle signal with friction-aware gross and net R."""
    if not (0 <= signal_index < len(candles)):
        raise IndexError("signal_index out of range")
    if direction not in (Direction.BUY, Direction.SELL):
        return None
    if volume <= 0 or stop_loss <= 0 or take_profit <= 0:
        return None
    if config.execution_delay_bars < 1:
        raise ValueError("execution_delay_bars must be >= 1")
    entry_index = signal_index + config.execution_delay_bars
    if entry_index >= len(candles):
        return None

    entry = _fill_entry(candles[entry_index].open, direction, config)
    if direction is Direction.BUY:
        if stop_loss >= entry or take_profit <= entry:
            return None
        risk_distance = entry - stop_loss
    else:
        if stop_loss <= entry or take_profit >= entry:
            return None
        risk_distance = stop_loss - entry

    initial_risk = _pnl(direction, entry, stop_loss, volume, broker) * Decimal("-1")
    if risk_distance <= 0 or initial_risk <= 0:
        return None

    exit_index = None
    raw_exit = None
    reason = None
    for j in range(entry_index, len(candles)):
        candle = candles[j]
        stop_hit = candle.low <= stop_loss if direction is Direction.BUY else candle.high >= stop_loss
        target_hit = candle.high >= take_profit if direction is Direction.BUY else candle.low <= take_profit
        if stop_hit:
            exit_index, raw_exit, reason = j, stop_loss, "STOP_LOSS"
            break
        if target_hit:
            exit_index, raw_exit, reason = j, take_profit, "TAKE_PROFIT"
            break

    if exit_index is None:
        exit_index, raw_exit, reason = len(candles) - 1, candles[-1].close, "END_OF_DATA"

    assert raw_exit is not None and reason is not None
    exit_price = _fill_exit(raw_exit, direction, config)
    gross = _pnl(direction, entry, exit_price, volume, broker)
    commission = config.commission_per_lot_per_side * volume * Decimal(2)
    net = gross - commission
    return NetROutcome(
        signal_index, entry_index, exit_index, direction, entry, exit_price,
        gross, commission, net, initial_risk, gross / initial_risk, net / initial_risk, reason,
    )
