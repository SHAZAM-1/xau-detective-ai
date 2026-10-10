"""Deterministic production preflight for Demo analysis/execution.

The preflight is deliberately fail-closed. It validates the broker/account
boundary and every required closed-candle series before the strategy is
allowed to consume the snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .broker import validate_broker_spec
from .data_quality import validate_candles
from .environment import AccountCapabilities, TradingEnvironment
from .models import AccountSnapshot, BrokerSpec, ExecutionSnapshot
from .mt5_market_hours import pepperstone_gold_gap_is_expected
from .timeframes import Timeframe, expected_interval
from .trading_profile import TradingProfile


_MAX_STALENESS_BY_TIMEFRAME = {
    Timeframe.D1: timedelta(days=4),
    Timeframe.H4: timedelta(hours=16),
    Timeframe.H1: timedelta(hours=4),
    Timeframe.M15: timedelta(hours=1),
    Timeframe.M5: timedelta(minutes=20),
}


@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    reasons: tuple[str, ...]

    @property
    def reason(self) -> str:
        return "OK" if self.ready else self.reasons[0]


def _validate_series(
    name: str,
    candles: tuple,
    *,
    now: datetime,
    timeframe: Timeframe,
) -> list[str]:
    reasons: list[str] = []
    quality = validate_candles(
        candles,
        expected_interval(timeframe),
        timeframe=timeframe,
        gap_is_expected_for_timeframe=pepperstone_gold_gap_is_expected,
    )
    reasons.extend(f"{name}_{reason}" for reason in quality.reasons)
    if candles:
        latest = candles[-1]
        if (
            not isinstance(latest.timestamp, datetime)
            or latest.timestamp.tzinfo is None
            or latest.timestamp.utcoffset() is None
        ):
            reasons.append(f"{name}_TIMESTAMP_NOT_TIMEZONE_AWARE")
        elif now.tzinfo is None or now.utcoffset() is None:
            reasons.append("PREFLIGHT_TIME_NOT_TIMEZONE_AWARE")
        else:
            latest_utc = latest.timestamp.astimezone(UTC)
            now_utc = now.astimezone(UTC)
            if latest_utc + expected_interval(timeframe) > now_utc:
                reasons.append(f"{name}_LATEST_CANDLE_NOT_CLOSED")
            if now_utc - latest_utc > _MAX_STALENESS_BY_TIMEFRAME[timeframe]:
                reasons.append(f"{name}_STALE_DATA")
    return reasons


def run_production_preflight(
    *,
    capabilities: AccountCapabilities,
    account: AccountSnapshot,
    broker: BrokerSpec,
    execution: ExecutionSnapshot,
    profile: TradingProfile,
    d1: tuple,
    h4: tuple,
    h1: tuple,
    m15: tuple,
    m5: tuple,
    now: datetime,
) -> PreflightResult:
    """Validate the complete Demo input boundary before strategy execution."""
    reasons: list[str] = []

    try:
        profile.validate()
    except (AttributeError, TypeError, ValueError) as exc:
        return PreflightResult(False, (f"INVALID_TRADING_PROFILE:{exc}",))

    # This boundary must not let Decimal NaN/Infinity or malformed external
    # values reach comparisons below. Return a deterministic rejection instead
    # of allowing Decimal.InvalidOperation to escape or comparisons to mislead.
    raw_numeric_inputs = (
        account.balance,
        account.equity,
        account.free_margin,
        execution.bid,
        execution.ask,
        execution.estimated_slippage,
    )
    if any(not isinstance(value, Decimal) for value in raw_numeric_inputs):
        return PreflightResult(False, ("NUMERIC_INPUT_TYPE_INVALID",))
    try:
        numeric_inputs = tuple(Decimal(str(value)) for value in raw_numeric_inputs)
    except (InvalidOperation, TypeError, ValueError):
        return PreflightResult(False, ("INVALID_NUMERIC_INPUT",))
    if any(not value.is_finite() for value in numeric_inputs):
        return PreflightResult(False, ("NON_FINITE_NUMERIC_INPUT",))

    if capabilities.environment is not TradingEnvironment.DEMO:
        reasons.append("DEMO_ENVIRONMENT_REQUIRED")
    if not capabilities.connected:
        reasons.append("MT5_NOT_CONNECTED")
    if not capabilities.connection_healthy:
        reasons.append("MT5_CONNECTION_UNHEALTHY")
    if not capabilities.symbol_available:
        reasons.append("SYMBOL_UNAVAILABLE")
    if not capabilities.symbol:
        reasons.append("MISSING_SYMBOL")

    broker_ok, broker_reasons = validate_broker_spec(broker)
    if not broker_ok:
        reasons.extend(broker_reasons)

    if account.balance <= 0:
        reasons.append("INVALID_ACCOUNT_BALANCE")
    if account.equity <= 0:
        reasons.append("INVALID_ACCOUNT_EQUITY")
    if account.free_margin < 0:
        reasons.append("INVALID_FREE_MARGIN")

    if execution.bid <= 0 or execution.ask <= 0:
        reasons.append("INVALID_MARKET_PRICE")
    if execution.ask <= execution.bid:
        reasons.append("INVALID_BID_ASK")
    if execution.estimated_slippage < 0:
        reasons.append("INVALID_ESTIMATED_SLIPPAGE")
    if profile.max_spread is not None and execution.spread > profile.max_spread:
        reasons.append("SPREAD_ABOVE_PROFILE_LIMIT")
    if profile.max_slippage is not None and execution.estimated_slippage > profile.max_slippage:
        reasons.append("SLIPPAGE_ABOVE_PROFILE_LIMIT")

    if now.tzinfo is None or now.utcoffset() is None:
        reasons.append("PREFLIGHT_TIME_NOT_TIMEZONE_AWARE")

    series = (
        ("D1", d1, Timeframe.D1),
        ("H4", h4, Timeframe.H4),
        ("H1", h1, Timeframe.H1),
        ("M15", m15, Timeframe.M15),
        ("M5", m5, Timeframe.M5),
    )
    for name, candles, timeframe in series:
        reasons.extend(_validate_series(name, candles, now=now, timeframe=timeframe))

    # Keep the import-time contract explicit: no hidden float coercion belongs
    # in this safety boundary.
    if not isinstance(account.balance, Decimal) or not isinstance(account.equity, Decimal):
        reasons.append("ACCOUNT_DECIMAL_TYPE_INVALID")

    return PreflightResult(not reasons, tuple(dict.fromkeys(reasons)))
