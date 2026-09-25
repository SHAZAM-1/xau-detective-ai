"""Capital-aware position sizing and hard risk gates."""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from .models import RiskRequest, RiskResult


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("volume_step must be positive")
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def calculate_position_size(request: RiskRequest) -> RiskResult:
    b = request.broker
    a = request.account

    if request.risk_fraction <= 0 or request.risk_fraction > 1:
        return RiskResult(False, Decimal("0"), Decimal("0"), Decimal("0"), "INVALID_RISK_FRACTION")
    if request.entry <= 0 or request.stop_loss <= 0 or request.entry == request.stop_loss:
        return RiskResult(False, Decimal("0"), Decimal("0"), Decimal("0"), "INVALID_ENTRY_OR_STOP")
    if b.tick_size <= 0 or b.tick_value <= 0:
        return RiskResult(False, Decimal("0"), Decimal("0"), Decimal("0"), "MISSING_TICK_SPEC")
    if b.volume_min <= 0 or b.volume_max < b.volume_min:
        return RiskResult(False, Decimal("0"), Decimal("0"), Decimal("0"), "INVALID_VOLUME_LIMITS")

    stop_distance = abs(request.entry - request.stop_loss)
    if stop_distance < b.min_stop_distance:
        return RiskResult(False, Decimal("0"), Decimal("0"), Decimal("0"), "STOP_TOO_CLOSE")

    risk_budget = a.balance * request.risk_fraction
    ticks = stop_distance / b.tick_size
    loss_per_lot = ticks * b.tick_value
    if loss_per_lot <= 0:
        return RiskResult(False, Decimal("0"), risk_budget, Decimal("0"), "INVALID_LOSS_CALCULATION")

    raw_volume = (risk_budget * request.safety_margin) / loss_per_lot
    volume = min(_floor_to_step(raw_volume, b.volume_step), b.volume_max)
    if volume < b.volume_min:
        return RiskResult(False, Decimal("0"), risk_budget, Decimal("0"), "MIN_LOT_EXCEEDS_RISK_BUDGET")

    estimated_loss = volume * loss_per_lot
    if estimated_loss > risk_budget:
        return RiskResult(False, Decimal("0"), risk_budget, estimated_loss, "RISK_LIMIT_EXCEEDED")

    return RiskResult(True, volume, risk_budget, estimated_loss, "OK")
