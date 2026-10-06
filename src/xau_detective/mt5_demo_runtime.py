"""Live MT5 Demo runtime loop.

This is the operational boundary around the existing MT5DemoTradingService.
It fetches only closed multi-timeframe candles and evaluates once per newly
closed M5 candle. It never implements a second strategy or execution path.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from .ingestion import load_multi_timeframe
from .mt5_demo_service import DemoCycleResult, MT5DemoTradingService
from .mt5_market_hours import pepperstone_gold_gap_is_expected
from .mt5_source import MT5CandleSource
from .timeframes import Timeframe
from .trading_profile import TradingProfile


TIMEFRAMES = (Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15, Timeframe.M5)


class RuntimeService(Protocol):
    def cycle(
        self,
        *,
        profile: TradingProfile,
        d1: tuple,
        h4: tuple,
        h1: tuple,
        m15: tuple,
        m5: tuple,
        now: datetime,
        idempotency_key: str,
    ) -> DemoCycleResult: ...


@dataclass(frozen=True)
class RuntimeConfig:
    symbol: str = "XAUUSD"
    candle_count: int = 300
    poll_seconds: float = 5.0
    execution_enabled: bool = False
    auto_execution_enabled: bool = False
    risk_fraction: Decimal = Decimal("0.01")

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("SYMBOL_REQUIRED")
        if self.candle_count < 50:
            raise ValueError("CANDLE_COUNT_TOO_SMALL")
        if self.poll_seconds <= 0:
            raise ValueError("POLL_SECONDS_MUST_BE_POSITIVE")
        if self.execution_enabled != self.auto_execution_enabled:
            raise ValueError("EXECUTION_GATES_MUST_MATCH")
        if self.risk_fraction <= 0 or self.risk_fraction >= 1:
            raise ValueError("RISK_FRACTION_OUT_OF_RANGE")


def build_profile(config: RuntimeConfig) -> TradingProfile:
    config.validate()
    return TradingProfile(
        risk_fraction=config.risk_fraction,
        auto_analysis_enabled=True,
        auto_execution_enabled=config.auto_execution_enabled,
    )


def fetch_closed_snapshot(
    source: MT5CandleSource,
    *,
    symbol: str,
    count: int,
    now: datetime,
) -> dict[Timeframe, tuple]:
    snapshots = load_multi_timeframe(
        source,
        symbol,
        TIMEFRAMES,
        count,
        now=now,
        gap_is_expected=pepperstone_gold_gap_is_expected,
    )
    result = {snapshot.timeframe: snapshot for snapshot in snapshots}
    reasons = [
        f"{snapshot.timeframe.value}:{','.join(snapshot.quality.reasons)}"
        for snapshot in snapshots
        if not snapshot.quality.usable
    ]
    if reasons:
        raise RuntimeError("MARKET_DATA_REJECTED:" + "|".join(reasons))
    if any(not result[timeframe].candles for timeframe in TIMEFRAMES):
        raise RuntimeError("MARKET_DATA_EMPTY")
    return {timeframe: result[timeframe].candles for timeframe in TIMEFRAMES}


def run_once(
    *,
    source: MT5CandleSource,
    service: RuntimeService,
    profile: TradingProfile,
    symbol: str,
    candle_count: int,
    now: datetime | None = None,
    last_closed_m5: datetime | None = None,
) -> tuple[datetime, DemoCycleResult | None]:
    timestamp = now or datetime.now(UTC)
    data = fetch_closed_snapshot(
        source,
        symbol=symbol,
        count=candle_count,
        now=timestamp,
    )
    m5 = data[Timeframe.M5]
    closed_m5 = m5[-1].timestamp

    # Do not re-run analysis/execution while polling the same closed candle.
    if closed_m5 == last_closed_m5:
        return closed_m5, None

    key = f"{symbol}:M5:{closed_m5.isoformat()}"
    result = service.cycle(
        profile=profile,
        d1=data[Timeframe.D1],
        h4=data[Timeframe.H4],
        h1=data[Timeframe.H1],
        m15=data[Timeframe.M15],
        m5=m5,
        now=timestamp,
        idempotency_key=key,
    )
    return closed_m5, result


def run_demo_runtime(
    *,
    mt5_module: Any,
    config: RuntimeConfig,
    once: bool = False,
    sleep_fn=time.sleep,
    now_fn=lambda: datetime.now(UTC),
) -> None:
    config.validate()
    profile = build_profile(config)

    if config.execution_enabled and not config.auto_execution_enabled:
        raise ValueError("DEMO_EXECUTION_REQUIRES_AUTO_EXECUTION")

    if not mt5_module.initialize():
        raise RuntimeError(f"MT5_INITIALIZE_FAILED:{mt5_module.last_error()}")

    source = MT5CandleSource(mt5_module)
    resolved_symbol = source.resolve_symbol(config.symbol)
    service = MT5DemoTradingService(
        mt5_module,
        symbol=resolved_symbol,
        execution_enabled=config.execution_enabled,
    )
    last_closed_m5: datetime | None = None

    try:
        while True:
            now = source.market_time(resolved_symbol)
            try:
                closed_m5, result = run_once(
                    source=source,
                    service=service,
                    profile=profile,
                    symbol=resolved_symbol,
                    candle_count=config.candle_count,
                    now=now,
                    last_closed_m5=last_closed_m5,
                )

                if closed_m5 != last_closed_m5:
                    print(
                        f"{closed_m5.isoformat()} | "
                        f"{result.reason if result is not None else 'SKIPPED'}"
                    )
                    last_closed_m5 = closed_m5

                if once:
                    return
            except Exception as exc:
                print(f"RUNTIME_REJECTED | {type(exc).__name__}:{exc}")
                if once:
                    raise

            sleep_fn(config.poll_seconds)
    finally:
        mt5_module.shutdown()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="XAU Detective AI Pepperstone MT5 Demo runtime"
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--candle-count", type=int, default=300)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--risk-fraction", type=Decimal, default=Decimal("0.01"))
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one closed-candle cycle and exit.",
    )
    parser.add_argument(
        "--execute-demo",
        action="store_true",
        help=(
            "Explicitly enable automatic Demo execution. "
            "Live accounts remain locked by policy."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = RuntimeConfig(
        symbol=args.symbol,
        candle_count=args.candle_count,
        poll_seconds=args.poll_seconds,
        execution_enabled=args.execute_demo,
        auto_execution_enabled=args.execute_demo,
        risk_fraction=args.risk_fraction,
    )

    import MetaTrader5 as mt5

    run_demo_runtime(
        mt5_module=mt5,
        config=config,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
