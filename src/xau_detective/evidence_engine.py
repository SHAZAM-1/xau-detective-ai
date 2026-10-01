"""Translate independent feature families into an auditable evidence ledger."""
from __future__ import annotations

from decimal import Decimal

from .evidence import EvidenceLedger
from .liquidity import LiquiditySnapshot
from .mean_reversion import MeanReversionSignal
from .models import Direction
from .regime import RegimeSnapshot, TrendState, VolatilityState
from .structure import StructureSnapshot
from .volume import VolumeAnalysis
from .zones import ZoneAnalysis


def build_evidence(
    direction: Direction,
    regime: RegimeSnapshot,
    structure: StructureSnapshot,
    *,
    momentum: Decimal | None = None,
    min_independent_families: int = 3,
    mean_reversion: MeanReversionSignal | None = None,
    liquidity: LiquiditySnapshot | None = None,
    volume: VolumeAnalysis | None = None,
    zones: ZoneAnalysis | None = None,
    current_price: Decimal | None = None,
) -> EvidenceLedger:
    ledger = EvidenceLedger(direction)

    if direction is Direction.NO_TRADE:
        ledger.add_warning("NO_TRADE_DIRECTION")
        return ledger

    # Family 1: regime/trend
    if direction is Direction.BUY and regime.trend is TrendState.UP:
        ledger.add_support("regime_trend_up")
    elif direction is Direction.SELL and regime.trend is TrendState.DOWN:
        ledger.add_support("regime_trend_down")
    elif regime.trend in (TrendState.UP, TrendState.DOWN):
        ledger.add_contradiction("regime_trend_conflict")
    else:
        ledger.add_warning("regime_not_directional")

    # Family 2: market structure
    if structure.direction is direction:
        ledger.add_support("structure_breakout_alignment")
    elif structure.direction is not Direction.NO_TRADE:
        ledger.add_contradiction("structure_opposes_direction")
    else:
        ledger.add_warning("structure_not_confirmed")

    # Family 3: momentum
    if momentum is not None:
        if direction is Direction.BUY and momentum > 0:
            ledger.add_support("momentum_positive")
        elif direction is Direction.SELL and momentum < 0:
            ledger.add_support("momentum_negative")
        else:
            ledger.add_contradiction("momentum_opposes_direction")
    else:
        ledger.add_warning("momentum_missing")

    # Research family: mean reversion. Optional so existing production callers
    # retain their exact behavior until this family is explicitly supplied.
    if mean_reversion is not None:
        if mean_reversion.direction == direction.value:
            ledger.add_support("mean_reversion_alignment")
        elif mean_reversion.direction in (Direction.BUY.value, Direction.SELL.value):
            ledger.add_contradiction("mean_reversion_conflict")
        else:
            ledger.add_warning("mean_reversion_neutral")

    # Research family: liquidity behavior. A swept high/low is treated as
    # directional evidence only when it matches the requested direction.
    if liquidity is not None:
        if direction is Direction.BUY and liquidity.swept_low:
            ledger.add_support("liquidity_sweep_low")
        elif direction is Direction.SELL and liquidity.swept_high:
            ledger.add_support("liquidity_sweep_high")
        if direction is Direction.BUY and liquidity.swept_high:
            ledger.add_contradiction("liquidity_sweep_high_conflict")
        elif direction is Direction.SELL and liquidity.swept_low:
            ledger.add_contradiction("liquidity_sweep_low_conflict")

    # Research family: volume. Directional pressure is explicitly a proxy
    # for candle direction, never an invented order-flow measurement.
    if volume is not None:
        if direction is Direction.BUY and volume.directional_pressure == "BULLISH_PROXY":
            ledger.add_support("volume_bullish_proxy")
        elif direction is Direction.SELL and volume.directional_pressure == "BEARISH_PROXY":
            ledger.add_support("volume_bearish_proxy")
        elif volume.directional_pressure in ("BULLISH_PROXY", "BEARISH_PROXY"):
            ledger.add_contradiction("volume_pressure_conflict")
        else:
            ledger.add_warning("volume_pressure_neutral")

    # Research family: support/resistance location. It is only directional
    # when a supplied current price is actually inside a detected zone.
    if zones is not None and current_price is not None:
        near_support = any(zone.low <= current_price <= zone.high for zone in zones.support)
        near_resistance = any(zone.low <= current_price <= zone.high for zone in zones.resistance)
        if direction is Direction.BUY and near_support:
            ledger.add_support("support_zone_location")
        elif direction is Direction.SELL and near_resistance:
            ledger.add_support("resistance_zone_location")
        if direction is Direction.BUY and near_resistance:
            ledger.add_contradiction("resistance_zone_conflict")
        elif direction is Direction.SELL and near_support:
            ledger.add_contradiction("support_zone_conflict")
    elif zones is not None:
        ledger.add_warning("zone_location_price_missing")

    # Volatility is a context filter, not directional evidence.
    if regime.volatility is VolatilityState.HIGH:
        ledger.add_warning("high_volatility_execution_risk")
    elif regime.volatility is VolatilityState.UNKNOWN:
        ledger.add_warning("volatility_unknown")

    if ledger.independent_evidence_count < min_independent_families:
        ledger.add_warning("INSUFFICIENT_INDEPENDENT_EVIDENCE")

    return ledger
