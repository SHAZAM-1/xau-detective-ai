"""Deterministic, look-ahead-safe market features for research."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .market import Candle, true_range


@dataclass(frozen=True)
class FeatureSnapshot:
    atr: Decimal | None
    ema_fast: Decimal | None
    ema_slow: Decimal | None
    return_pct: Decimal | None
    volatility_pct: Decimal | None
    momentum: Decimal | None


def _ema(values: tuple[Decimal, ...], period: int) -> Decimal | None:
    if period <= 0 or len(values) < period:
        return None
    alpha = Decimal(2) / Decimal(period + 1)
    value = sum(values[:period], Decimal(0)) / Decimal(period)
    for price in values[period:]:
        value = alpha * price + (Decimal(1) - alpha) * value
    return value


def atr(candles: tuple[Candle, ...], period: int = 14) -> Decimal | None:
    if period <= 0 or len(candles) < period:
        return None
    trs = tuple(
        true_range(c, candles[i - 1].close if i else None)
        for i, c in enumerate(candles)
    )
    return sum(trs[-period:], Decimal(0)) / Decimal(period)


def compute_features(
    candles: tuple[Candle, ...],
    *,
    atr_period: int = 14,
    ema_fast_period: int = 20,
    ema_slow_period: int = 50,
    return_lookback: int = 1,
    volatility_lookback: int = 20,
) -> FeatureSnapshot:
    closes = tuple(c.close for c in candles)
    current = closes[-1] if closes else None
    ret = None
    if current is not None and return_lookback > 0 and len(closes) > return_lookback:
        base = closes[-1 - return_lookback]
        if base != 0:
            ret = (current - base) / base * Decimal(100)

    volatility = None
    if volatility_lookback > 0 and len(candles) >= volatility_lookback:
        window = candles[-volatility_lookback:]
        base = window[0].close
        if base != 0:
            volatility = (
                max(c.high for c in window) - min(c.low for c in window)
            ) / base * Decimal(100)

    momentum = None
    if len(closes) >= 2 and closes[-2] != 0:
        momentum = (closes[-1] - closes[-2]) / closes[-2]

    return FeatureSnapshot(
        atr(candles, atr_period),
        _ema(closes, ema_fast_period),
        _ema(closes, ema_slow_period),
        ret,
        volatility,
        momentum,
    )
