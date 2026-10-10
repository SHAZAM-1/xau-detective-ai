"""Broker specification validation and execution feasibility checks."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .models import BrokerSpec


def validate_broker_spec(spec: BrokerSpec) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if not spec.symbol:
        errors.append("MISSING_SYMBOL")

    try:
        numeric = {
            name: Decimal(str(getattr(spec, name)))
            for name in (
                "contract_size",
                "volume_min",
                "volume_max",
                "volume_step",
                "tick_size",
                "tick_value",
                "point",
                "min_stop_distance",
            )
        }
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        errors.append("INVALID_NUMERIC_BROKER_SPEC")
        return False, tuple(errors)

    if any(not value.is_finite() for value in numeric.values()):
        errors.append("NON_FINITE_BROKER_SPEC")
        return False, tuple(errors)

    if numeric["contract_size"] <= 0:
        errors.append("INVALID_CONTRACT_SIZE")
    if (
        numeric["volume_min"] <= 0
        or numeric["volume_max"] < numeric["volume_min"]
    ):
        errors.append("INVALID_VOLUME_LIMITS")
    if numeric["volume_step"] <= 0:
        errors.append("INVALID_VOLUME_STEP")
    if numeric["tick_size"] <= 0 or numeric["tick_value"] <= 0:
        errors.append("INVALID_TICK_SPEC")
    if numeric["point"] <= 0:
        errors.append("INVALID_POINT")
    if numeric["min_stop_distance"] < 0:
        errors.append("INVALID_MIN_STOP_DISTANCE")
    return not errors, tuple(errors)
