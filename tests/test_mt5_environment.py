from types import SimpleNamespace

import pytest

from xau_detective.environment import TradingEnvironment
from xau_detective.mt5_environment import detect_environment_from_mt5


def test_detects_demo_account_from_mt5_trade_mode():
    account = SimpleNamespace(trade_mode=0)
    assert detect_environment_from_mt5(account) is TradingEnvironment.DEMO


def test_detects_live_account_from_mt5_trade_mode():
    account = SimpleNamespace(trade_mode=2)
    assert detect_environment_from_mt5(account) is TradingEnvironment.LIVE


def test_supports_broker_module_constants():
    account = SimpleNamespace(trade_mode=20)
    mt5 = SimpleNamespace(
        ACCOUNT_TRADE_MODE_DEMO=10,
        ACCOUNT_TRADE_MODE_REAL=20,
    )
    assert detect_environment_from_mt5(account, mt5_module=mt5) is TradingEnvironment.LIVE


def test_rejects_missing_trade_mode():
    with pytest.raises(ValueError, match="MT5_ACCOUNT_TRADE_MODE_UNAVAILABLE"):
        detect_environment_from_mt5(SimpleNamespace())


def test_rejects_unknown_trade_mode():
    with pytest.raises(ValueError, match="UNSUPPORTED_MT5_ACCOUNT_TRADE_MODE"):
        detect_environment_from_mt5(SimpleNamespace(trade_mode=99))
