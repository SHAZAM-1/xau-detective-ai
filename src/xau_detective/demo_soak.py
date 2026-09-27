"""Deterministic Demo soak-test harness.

The harness runs repeated service cycles against a scripted MT5 double. It is
test infrastructure only: it never connects to MetaTrader 5.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from .environment import TradingEnvironment
from .market import Candle
from .mt5_demo_service import MT5DemoTradingService
from .trading_profile import TradingProfile


@dataclass
class ScriptedMT5:
    """Minimal MT5 double with injectable connection/tick/order failures."""

    trade_mode: int = 0
    connected: bool = True
    tick_available: bool = True
    order_retcodes: tuple[int, ...] = (10009,)
    
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009

    def __post_init__(self) -> None:
        self.sent: list[object] = []
        self._order_index = 0
        self.account = SimpleNamespace(
            login=123,
            server="Demo",
            trade_mode=self.trade_mode,
            trade_allowed=True,
            balance=1000,
            equity=1000,
            margin_free=900,
        )

    def account_info(self):
        return self.account

    def terminal_info(self):
        return SimpleNamespace(connected=self.connected)

    def symbol_info(self, symbol):
        return SimpleNamespace(
            name=symbol,
            trade_contract_size=100,
            volume_min=Decimal("0.01"),
            volume_max=Decimal("100"),
            volume_step=Decimal("0.01"),
            trade_tick_size=Decimal("0.01"),
            trade_tick_value=Decimal("1"),
            point=Decimal("0.01"),
            trade_stops_level=0,
            filling_mode=1,
        )

    def symbol_info_tick(self, symbol):
        if not self.tick_available:
            return None
        return SimpleNamespace(bid=Decimal("4000"), ask=Decimal("4000.2"))

    def order_send(self, request):
        self.sent.append(request)
        retcode = self.order_retcodes[min(self._order_index, len(self.order_retcodes) - 1)]
        self._order_index += 1
        return SimpleNamespace(
            retcode=retcode,
            order=777 + self._order_index,
            comment="scripted",
        )

    def positions_get(self, symbol=None):
        return ()

    def orders_get(self, symbol=None):
        return ()


def valid_candles(now: datetime) -> dict[str, tuple]:
    def series(step: timedelta, count: int, age: timedelta) -> tuple:
        start = now - age - step * count
        return tuple(
            Candle(
                timestamp=start + step * i,
                open=Decimal("4000"),
                high=Decimal("4002"),
                low=Decimal("3998"),
                close=Decimal("4001"),
                volume=Decimal("100"),
            )
            for i in range(count)
        )

    return {
        "d1": series(timedelta(days=1), 30, timedelta(days=1)),
        "h4": series(timedelta(hours=4), 30, timedelta(hours=4)),
        "h1": series(timedelta(hours=1), 30, timedelta(hours=1)),
        "m15": series(timedelta(minutes=15), 30, timedelta(minutes=15)),
        "m5": series(timedelta(minutes=5), 30, timedelta(minutes=5)),
    }


@dataclass(frozen=True)
class SoakResult:
    cycles: int
    reasons: tuple[str, ...]
    orders_sent: int


def run_demo_soak(
    *,
    cycles: int = 20,
    failure_cycle: int | None = None,
    failure: str | None = None,
) -> SoakResult:
    """Run repeated fail-closed cycles against the scripted MT5 double."""
    if cycles <= 0:
        raise ValueError("cycles must be positive")
    if failure_cycle is not None and not 0 <= failure_cycle < cycles:
        raise ValueError("failure_cycle must be inside the cycle range")

    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    mt5 = ScriptedMT5()
    if failure == "LIVE":
        mt5.trade_mode = ScriptedMT5.ACCOUNT_TRADE_MODE_REAL
        mt5.account.trade_mode = mt5.trade_mode

    service = MT5DemoTradingService(mt5, execution_enabled=False)
    profile = TradingProfile(auto_analysis_enabled=failure in {"DISCONNECT", "TICK"})
    data = valid_candles(now)
    reasons: list[str] = []

    for index in range(cycles):
        if failure_cycle == index:
            if failure == "DISCONNECT":
                mt5.connected = False
            elif failure == "TICK":
                mt5.tick_available = False
        result = service.cycle(
            profile=profile,
            **data,
            now=now + timedelta(minutes=index),
            idempotency_key=f"soak-{index}",
        )
        reasons.append(result.reason)

    return SoakResult(cycles, tuple(reasons), len(mt5.sent))
