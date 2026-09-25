"""Broker specification validation and execution feasibility checks."""
from __future__ import annotations

from decimal import Decimal

from .models import BrokerSpec


def validate_broker_spec(spec: BrokerSpec) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if not spec.symbol:
        errors.append("MISSING_SYMBOL")
    if spec.contract_size <= 0:
        errors.append("INVALID_CONTRACT_SIZE")
    if spec.volume_min <= 0 or spec.volume_max < spec.volume_min:
        errors.append("INVALID_VOLUME_LIMITS")
    if spec.volume_step <= 0:
        errors.append("INVALID_VOLUME_STEP")
    if spec.tick_size <= 0 or spec.tick_value <= 0:
        errors.append("INVALID_TICK_SPEC")
    if spec.point <= 0:
        errors.append("INVALID_POINT")
    if spec.min_stop_distance < 0:
        errors.append("INVALID_MIN_STOP_DISTANCE")
    return not errors, tuple(errors)
