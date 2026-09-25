"""Deterministic market-regime classification for research.

Regime labels are descriptive features, not trading commands. Thresholds should
be validated out-of-sample before they influence execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .features import compute_features
from .market import Candle


class TrendState(str, Enum):
    UP = "TREND_UP"
    DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    UNKNOWN = "TREND_UNKNOWN"


class VolatilityState(str, Enum):
    HIGH = "VOL_HIGH"
    NORMAL = "VOL_NORMAL"
    LOW = "VOL_LOW"
    UNKNOWN = "VOL_UNKNOWN"


@dataclass(frozen=True)
class RegimeSnapshot:
    trend: TrendState
    volatility: VolatilityState
    trend_strength: Decimal | None
    volatility_pct: Decimal | None
    ema_fast: Decimal | None
    ema_slow: Decimal | None
    ema_slope_pct: Decimal | None


def classify_regime(
    candles: tuple[Candle, ...],
    *,
    ema_fast_period: int = 20,
    ema_slow_period: int = 50,
    slope_lookback: int = 5,
    volatility_lookback: int = 20,
    low_volatility_pct: Decimal = Decimal("0.50"),
    high_volatility_pct: Decimal = Decimal("2.00"),
) -> RegimeSnapshot:
    if not candles:
        return RegimeSnapshot(
            TrendState.UNKNOWN, VolatilityState.UNKNOWN, None, None, None, None, None
        )

    features = compute_features(
        candles,
        ema_fast_period=ema_fast_period,
        ema_slow_period=ema_slow_period,
        volatility_lookback=volatility_lookback,
    )

    slope = None
    if len(candles) > slope_lookback and features.ema_fast is not None:
        earlier = compute_features(
            candles[:-slope_lookback],
            ema_fast_period=ema_fast_period,
            ema_slow_period=ema_slow_period,
        ).ema_fast
        if earlier is not None and earlier != 0:
            slope = (features.ema_fast - earlier) / earlier * Decimal(100)

    trend = TrendState.UNKNOWN
    if features.ema_fast is not None and features.ema_slow is not None and slope is not None:
        if features.ema_fast > features.ema_slow and slope > 0:
            trend = TrendState.UP
        elif features.ema_fast < features.ema_slow and slope < 0:
            trend = TrendState.DOWN
        else:
            trend = TrendState.RANGE

    volatility = VolatilityState.UNKNOWN
    if features.volatility_pct is not None:
        if features.volatility_pct >= high_volatility_pct:
            volatility = VolatilityState.HIGH
        elif features.volatility_pct <= low_volatility_pct:
            volatility = VolatilityState.LOW
        else:
            volatility = VolatilityState.NORMAL

    strength = None
    if features.ema_fast is not None and features.ema_slow is not None:
        base = abs(features.ema_slow)
        if base:
            strength = abs(features.ema_fast - features.ema_slow) / base * Decimal(100)

    return RegimeSnapshot(
        trend,
        volatility,
        strength,
        features.volatility_pct,
        features.ema_fast,
        features.ema_slow,
        slope,
    )
