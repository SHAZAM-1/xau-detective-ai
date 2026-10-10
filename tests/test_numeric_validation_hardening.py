from datetime import UTC, datetime, tzinfo
from decimal import Decimal

import pytest

from xau_detective.mt5_demo_runtime import RuntimeConfig, run_demo_runtime
from xau_detective.trading_profile import TradingProfile


@pytest.mark.parametrize(
    "field",
    ["risk_fraction", "min_reward_risk", "stop_atr_multiple", "max_spread", "max_slippage"],
)
@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_profile_rejects_non_finite_numeric_parameters(field, value):
    with pytest.raises(ValueError, match=field):
        TradingProfile(**{field: value}).validate()


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_runtime_config_rejects_non_finite_risk_fraction(value):
    with pytest.raises(ValueError, match="RISK_FRACTION_OUT_OF_RANGE"):
        RuntimeConfig(risk_fraction=value).validate()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_runtime_config_rejects_non_finite_poll_interval(value):
    with pytest.raises(ValueError, match="POLL_SECONDS_MUST_BE_POSITIVE"):
        RuntimeConfig(poll_seconds=value).validate()


def test_valid_finite_runtime_config_remains_accepted():
    RuntimeConfig(
        poll_seconds=5.0,
        risk_fraction=Decimal("0.01"),
    ).validate()


def test_valid_finite_profile_remains_accepted():
    TradingProfile(
        risk_fraction=Decimal("0.01"),
        min_reward_risk=Decimal("2.0"),
        stop_atr_multiple=Decimal("1.5"),
        max_spread=Decimal("0.3"),
        max_slippage=Decimal("0.1"),
    ).validate()


class MissingOffsetTimezone(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None

    def tzname(self, dt):
        return "missing-offset"


@pytest.mark.parametrize(
    ("invalid_clock", "expected_reason"),
    [
        ("wall", "RUNTIME_CLOCK_NOT_TIMEZONE_AWARE"),
        ("market", "MT5_MARKET_TIME_NOT_TIMEZONE_AWARE"),
    ],
)
def test_runtime_rejects_timezone_object_without_utc_offset(
    invalid_clock, expected_reason, monkeypatch, tmp_path
):
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    invalid_time = datetime(2026, 10, 6, 12, tzinfo=MissingOffsetTimezone())
    shutdown_calls = []
    cycle_calls = []

    class FakeMT5:
        def initialize(self):
            return True

        def shutdown(self):
            shutdown_calls.append(True)

    class FakeSource:
        def __init__(self, mt5_module):
            pass

        def resolve_symbol(self, symbol):
            return symbol

        def market_time(self, symbol):
            return invalid_time if invalid_clock == "market" else now

    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5CandleSource",
        FakeSource,
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5DemoTradingService",
        lambda mt5_module, **kwargs: object(),
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.run_once",
        lambda **kwargs: cycle_calls.append(True),
    )

    with pytest.raises(RuntimeError, match=expected_reason):
        run_demo_runtime(
            mt5_module=FakeMT5(),
            config=RuntimeConfig(log_dir=tmp_path),
            once=True,
            now_fn=lambda: invalid_time if invalid_clock == "wall" else now,
        )

    assert cycle_calls == []
    assert shutdown_calls == [True]


@pytest.mark.parametrize("field", ["risk_fraction", "min_reward_risk", "stop_atr_multiple", "max_spread", "max_slippage"])
@pytest.mark.parametrize("value", ["0.01", 0.01, 1])
def test_profile_rejects_non_decimal_numeric_types(field, value):
    with pytest.raises(ValueError, match=field):
        TradingProfile(**{field: value}).validate()


@pytest.mark.parametrize("field", ["bot_suggestions_enabled", "auto_analysis_enabled", "auto_execution_enabled"])
def test_profile_rejects_non_boolean_control_flags(field):
    with pytest.raises(ValueError, match=f"{field} must be boolean"):
        TradingProfile(**{field: "false"}).validate()
