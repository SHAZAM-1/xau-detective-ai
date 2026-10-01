"""Automatic MT5 account environment detection."""
from __future__ import annotations

from typing import Any

from .environment import TradingEnvironment


def detect_environment_from_mt5(
    account_info: Any,
    *,
    mt5_module: Any | None = None,
) -> TradingEnvironment:
    """Detect DEMO or LIVE from MT5's explicit account trade mode."""
    trade_mode = getattr(account_info, "trade_mode", None)
    if trade_mode is None:
        raise ValueError("MT5_ACCOUNT_TRADE_MODE_UNAVAILABLE")

    demo_mode = getattr(mt5_module, "ACCOUNT_TRADE_MODE_DEMO", 0)
    real_mode = getattr(mt5_module, "ACCOUNT_TRADE_MODE_REAL", 2)

    if trade_mode == demo_mode:
        return TradingEnvironment.DEMO
    if trade_mode == real_mode:
        return TradingEnvironment.LIVE
    raise ValueError(f"UNSUPPORTED_MT5_ACCOUNT_TRADE_MODE:{trade_mode}")
