"""Research-only volume analysis for normalized OHLCV candles.

The engine deliberately avoids claiming that candle volume represents executed
buy/sell volume. Unless the upstream source identifies the volume type, the
result is descriptive only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import mean

from .market import Candle


@dataclass(frozen=True)
class VolumeAnalysis:
    volume_kind: str
    current_volume: Decimal
    baseline_volume: Decimal
    relative_volume: Decimal
    state: str
    directional_pressure: str
    evidence: tuple[str, ...]


def analyze_volume(
    candles: tuple[Candle, ...],
    *,
    lookback: int = 20,
    expansion_ratio: Decimal = Decimal("1.5"),
    contraction_ratio: Decimal = Decimal("0.7"),
    volume_kind: str = "UNSPECIFIED",
) -> VolumeAnalysis | None:
    """Describe current volume versus a historical rolling baseline.

    ``directional_pressure`` is a candle-direction proxy only. It is never
    presented as true buy/sell order flow.
    """
    if lookback < 1 or expansion_ratio <= Decimal("1") or not (
        Decimal("0") < contraction_ratio < Decimal("1")
    ):
        return None
    if volume_kind not in {"UNSPECIFIED", "TICK", "REAL"}:
        return None
    if len(candles) < lookback + 1:
        return None

    current = candles[-1]
    baseline_values = tuple(c.volume for c in candles[-lookback - 1 : -1])
    if any(value < 0 for value in baseline_values) or current.volume < 0:
        return None

    baseline = Decimal(str(mean(float(value) for value in baseline_values)))
    if baseline <= 0:
        return None

    relative = current.volume / baseline
    if relative >= expansion_ratio:
        state = "EXPANSION"
    elif relative <= contraction_ratio:
        state = "CONTRACTION"
    else:
        state = "NORMAL"

    if current.bullish:
        pressure = "BULLISH_PROXY"
    elif current.bearish:
        pressure = "BEARISH_PROXY"
    else:
        pressure = "NEUTRAL_PROXY"

    kind_note = (
        "VOLUME_TYPE_UNSPECIFIED"
        if volume_kind == "UNSPECIFIED"
        else f"VOLUME_TYPE_{volume_kind}"
    )
    evidence = (
        kind_note,
        f"RELATIVE_VOLUME={relative}",
        f"VOLUME_STATE={state}",
        f"DIRECTIONAL_PRESSURE_PROXY={pressure}",
    )
    return VolumeAnalysis(
        volume_kind=volume_kind,
        current_volume=current.volume,
        baseline_volume=baseline,
        relative_volume=relative,
        state=state,
        directional_pressure=pressure,
        evidence=evidence,
    )
