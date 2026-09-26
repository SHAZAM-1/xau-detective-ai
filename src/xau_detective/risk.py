"""Capital-aware position sizing and hard risk gates."""
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from .models import RiskRequest, RiskResult


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("volume_step must be positive")
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def _veto(reason: str, risk_amount: Decimal = Decimal(0)) -> RiskResult:
    return RiskResult(False, Decimal(0), risk_amount, Decimal(0), reason)


def calculate_position_size(request: RiskRequest) -> RiskResult:
    b = request.broker
    a = request.account
    if request.risk_fraction <= 0 or request.risk_fraction > 1:
        return _veto("INVALID_RISK_FRACTION")
    if request.entry <= 0 or request.stop_loss <= 0 or request.entry == request.stop_loss:
        return _veto("INVALID_ENTRY_OR_STOP")
    if b.tick_size <= 0 or b.tick_value <= 0:
        return _veto("MISSING_TICK_SPEC")
    if b.volume_min <= 0 or b.volume_max < b.volume_min:
        return _veto("INVALID_VOLUME_LIMITS")
    if a.equity <= 0 or a.free_margin <= 0:
        return _veto("INSUFFICIENT_ACCOUNT_EQUITY_OR_MARGIN")
    risk_budget = a.equity * request.risk_fraction
    if request.execution is not None:
        spread = request.execution.spread
        if spread < 0:
            return _veto("INVALID_BID_ASK", risk_budget)
        if request.max_spread is not None:
            if request.max_spread < 0:
                return _veto("INVALID_MAX_SPREAD", risk_budget)
            if spread > request.max_spread:
                return _veto("SPREAD_TOO_WIDE", risk_budget)
        if request.execution.estimated_slippage < 0:
            return _veto("INVALID_ESTIMATED_SLIPPAGE", risk_budget)
        if request.max_slippage is not None:
            if request.max_slippage < 0:
                return _veto("INVALID_MAX_SLIPPAGE", risk_budget)
            if request.execution.estimated_slippage > request.max_slippage:
                return _veto("SLIPPAGE_TOO_HIGH", risk_budget)
    elif request.max_spread is not None or request.max_slippage is not None:
        return _veto("EXECUTION_SNAPSHOT_REQUIRED", risk_budget)
    stop_distance = abs(request.entry - request.stop_loss)
    if stop_distance < b.min_stop_distance:
        return _veto("STOP_TOO_CLOSE", risk_budget)
    expected_slippage = request.execution.estimated_slippage if request.execution is not None else Decimal(0)
    effective_stop_distance = stop_distance + expected_slippage
    ticks = effective_stop_distance / b.tick_size
    loss_per_lot = ticks * b.tick_value
    if loss_per_lot <= 0:
        return _veto("INVALID_LOSS_CALCULATION", risk_budget)
    raw_volume = (risk_budget * request.safety_margin) / loss_per_lot
    volume = min(_floor_to_step(raw_volume, b.volume_step), b.volume_max)
    if volume < b.volume_min:
        return _veto("MIN_LOT_EXCEEDS_RISK_BUDGET", risk_budget)
    estimated_loss = volume * loss_per_lot
    if estimated_loss > risk_budget:
        return RiskResult(False, Decimal(0), risk_budget, estimated_loss, "RISK_LIMIT_EXCEEDED")
    if request.execution is not None and request.execution.margin_per_lot is not None:
        margin_per_lot = request.execution.margin_per_lot
        if margin_per_lot <= 0:
            return RiskResult(False, Decimal(0), risk_budget, estimated_loss, "INVALID_MARGIN_SPEC")
        if volume * margin_per_lot > a.free_margin:
            return RiskResult(False, Decimal(0), risk_budget, estimated_loss, "INSUFFICIENT_FREE_MARGIN")
    if request.daily_risk is not None:
        limit = request.max_daily_loss_fraction
        if limit is None or not (Decimal(0) < limit <= Decimal(1)):
            return RiskResult(False, Decimal(0), risk_budget, estimated_loss, "INVALID_DAILY_LOSS_LIMIT")
        current_daily_pnl = request.daily_risk.realized_pnl_today + request.daily_risk.unrealized_pnl_today
        projected_daily_loss = max(Decimal(0), -current_daily_pnl) + estimated_loss
        daily_loss_limit = a.equity * limit
        if projected_daily_loss > daily_loss_limit:
            return RiskResult(False, Decimal(0), risk_budget, estimated_loss, "DAILY_LOSS_LIMIT")
    return RiskResult(True, volume, risk_budget, estimated_loss, "OK")
