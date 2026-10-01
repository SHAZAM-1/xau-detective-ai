"""Deterministic paper-trading and broker-aware execution simulation.

This module never sends orders to a broker. It simulates the execution boundary
using closed-candle signals plus explicit broker constraints and trading
frictions so research can measure whether a strategy remains executable.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Callable

from .broker import validate_broker_spec
from .market import Candle
from .models import BrokerSpec, Direction


@dataclass(frozen=True)
class PaperTradingConfig:
    spread: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    commission_per_lot_per_side: Decimal = Decimal("0")
    execution_delay_bars: int = 1
    initial_equity: Decimal = Decimal("0")


@dataclass(frozen=True)
class PaperTradePlan:
    direction: Direction
    stop_loss: Decimal
    take_profit: Decimal
    volume: Decimal


@dataclass(frozen=True)
class PaperTrade:
    signal_index: int
    entry_index: int
    exit_index: int
    direction: Direction
    requested_volume: Decimal
    filled_volume: Decimal
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
    exit_reason: str


@dataclass(frozen=True)
class PaperTradingResult:
    trades: tuple[PaperTrade, ...]
    final_equity: Decimal
    net_pnl: Decimal
    rejected_signals: int
    rejection_reasons: tuple[str, ...]
    max_drawdown: Decimal


SignalFunction = Callable[[int, tuple[Candle, ...]], PaperTradePlan | None]


def _quantize_volume(volume: Decimal, spec: BrokerSpec) -> Decimal:
    if volume <= 0:
        return Decimal(0)
    if volume < spec.volume_min:
        return Decimal(0)
    steps = ((volume - spec.volume_min) / spec.volume_step).to_integral_value(
        rounding=ROUND_DOWN
    )
    result = spec.volume_min + steps * spec.volume_step
    return min(result, spec.volume_max)


def _validate_plan(
    plan: PaperTradePlan,
    entry: Decimal,
    spec: BrokerSpec,
) -> tuple[bool, str, Decimal]:
    if plan.direction not in (Direction.BUY, Direction.SELL):
        return False, "NO_TRADE_DIRECTION", Decimal(0)
    if plan.stop_loss <= 0 or plan.take_profit <= 0:
        return False, "INVALID_STOPS_OR_TARGET", Decimal(0)
    if plan.volume <= 0:
        return False, "INVALID_VOLUME", Decimal(0)

    volume = _quantize_volume(plan.volume, spec)
    if volume <= 0:
        return False, "VOLUME_BELOW_BROKER_MINIMUM", Decimal(0)

    if plan.direction is Direction.BUY:
        if plan.stop_loss >= entry or plan.take_profit <= entry:
            return False, "INVALID_BUY_LEVELS", Decimal(0)
        stop_distance = entry - plan.stop_loss
    else:
        if plan.stop_loss <= entry or plan.take_profit >= entry:
            return False, "INVALID_SELL_LEVELS", Decimal(0)
        stop_distance = plan.stop_loss - entry

    if stop_distance < spec.min_stop_distance:
        return False, "STOP_DISTANCE_BELOW_BROKER_MINIMUM", Decimal(0)

    return True, "OK", volume


def _pnl(
    direction: Direction,
    entry: Decimal,
    exit_price: Decimal,
    volume: Decimal,
    spec: BrokerSpec,
) -> Decimal:
    movement = (
        exit_price - entry
        if direction is Direction.BUY
        else entry - exit_price
    )
    return movement / spec.tick_size * spec.tick_value * volume


def _entry_fill(open_price: Decimal, direction: Direction, config: PaperTradingConfig) -> Decimal:
    half_spread = config.spread / Decimal(2)
    if direction is Direction.BUY:
        return open_price + half_spread + config.slippage
    return open_price - half_spread - config.slippage


def _exit_fill(raw_price: Decimal, direction: Direction, config: PaperTradingConfig) -> Decimal:
    half_spread = config.spread / Decimal(2)
    if direction is Direction.BUY:
        return raw_price - half_spread - config.slippage
    return raw_price + half_spread + config.slippage


def run_paper_trading(
    candles: tuple[Candle, ...],
    signal: SignalFunction,
    broker: BrokerSpec,
    config: PaperTradingConfig,
) -> PaperTradingResult:
    """Run a closed-candle signal through a deterministic simulated execution path.

    A signal observed at candle i is filled at the open of candle
    i + execution_delay_bars. Once filled, the position remains open until its
    stop, target, or end of data. If stop and target are touched in one candle,
    stop wins conservatively. No live MT5 API is called.
    """
    valid_broker, errors = validate_broker_spec(broker)
    if not valid_broker:
        raise ValueError("invalid broker spec: " + ",".join(errors))
    if len(candles) < 2:
        return PaperTradingResult(
            (), config.initial_equity, Decimal(0), 0, (), Decimal(0)
        )
    if config.spread < 0 or config.slippage < 0 or config.commission_per_lot_per_side < 0:
        raise ValueError("trading frictions cannot be negative")
    if config.execution_delay_bars < 1:
        raise ValueError("execution_delay_bars must be >= 1")

    trades: list[PaperTrade] = []
    rejection_reasons: list[str] = []
    i = 0

    while i < len(candles) - config.execution_delay_bars:
        plan = signal(i, candles[: i + 1])
        if plan is None or plan.direction is Direction.NO_TRADE:
            i += 1
            continue

        entry_index = i + config.execution_delay_bars
        entry = _entry_fill(candles[entry_index].open, plan.direction, config)
        executable, reason, volume = _validate_plan(plan, entry, broker)
        if not executable:
            rejection_reasons.append(reason)
            i += 1
            continue

        exit_index: int | None = None
        raw_exit: Decimal | None = None
        exit_reason: str | None = None

        for j in range(entry_index, len(candles)):
            candle = candles[j]
            if plan.direction is Direction.BUY:
                stop_hit = candle.low <= plan.stop_loss
                target_hit = candle.high >= plan.take_profit
            else:
                stop_hit = candle.high >= plan.stop_loss
                target_hit = candle.low <= plan.take_profit

            if stop_hit:
                exit_index, raw_exit, exit_reason = j, plan.stop_loss, "STOP_LOSS"
                break
            if target_hit:
                exit_index, raw_exit, exit_reason = j, plan.take_profit, "TAKE_PROFIT"
                break

        if exit_index is None:
            exit_index = len(candles) - 1
            raw_exit = candles[-1].close
            exit_reason = "END_OF_DATA"

        assert raw_exit is not None and exit_reason is not None
        exit_price = _exit_fill(raw_exit, plan.direction, config)
        gross = _pnl(plan.direction, entry, exit_price, volume, broker)
        commission = config.commission_per_lot_per_side * volume * Decimal(2)
        net = gross - commission

        trades.append(
            PaperTrade(
                signal_index=i,
                entry_index=entry_index,
                exit_index=exit_index,
                direction=plan.direction,
                requested_volume=plan.volume,
                filled_volume=volume,
                entry_price=entry,
                exit_price=exit_price,
                gross_pnl=gross,
                commission=commission,
                net_pnl=net,
                exit_reason=exit_reason,
            )
        )
        i = exit_index + 1

    net_pnl = sum((trade.net_pnl for trade in trades), Decimal(0))
    equity = config.initial_equity + net_pnl
    running = config.initial_equity
    peak = running
    max_drawdown = Decimal(0)
    for trade in trades:
        running += trade.net_pnl
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)

    return PaperTradingResult(
        tuple(trades),
        equity,
        net_pnl,
        len(rejection_reasons),
        tuple(rejection_reasons),
        max_drawdown,
    )
