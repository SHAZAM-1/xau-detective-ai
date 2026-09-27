from decimal import Decimal

import pytest

from xau_detective.pipeline import AnalysisConfig
from xau_detective.trading_profile import TradingProfile


def test_profile_maps_user_parameters_to_analysis_config():
    profile = TradingProfile(
        risk_fraction=Decimal("0.005"),
        min_reward_risk=Decimal("3.0"),
        max_spread=Decimal("0.30"),
        max_slippage=Decimal("0.10"),
        stop_atr_multiple=Decimal("1.8"),
        bot_suggestions_enabled=False,
        auto_execution_enabled=True,
    )
    config = AnalysisConfig.from_profile(profile)

    assert config.risk_fraction == Decimal("0.005")
    assert config.min_reward_risk == Decimal("3.0")
    assert config.max_spread == Decimal("0.30")
    assert config.max_slippage == Decimal("0.10")
    assert config.stop_atr_multiple == Decimal("1.8")
    assert profile.bot_suggestions_enabled is False
    assert profile.auto_execution_enabled is True


def test_profile_rejects_invalid_risk():
    with pytest.raises(ValueError, match="risk_fraction"):
        TradingProfile(risk_fraction=Decimal("1.0")).validate()


def test_profile_cannot_disable_safety_gates():
    profile = TradingProfile(auto_execution_enabled=True)
    overrides = profile.to_analysis_overrides()
    assert "max_spread" in overrides
    assert "max_slippage" in overrides
    assert "risk_fraction" in overrides
    assert "live_execution" not in overrides
