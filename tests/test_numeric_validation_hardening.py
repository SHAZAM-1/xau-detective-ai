from decimal import Decimal

import pytest

from xau_detective.mt5_demo_runtime import RuntimeConfig
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
