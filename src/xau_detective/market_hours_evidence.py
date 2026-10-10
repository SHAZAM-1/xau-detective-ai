"""Collect read-only MT5 candle-gap evidence for broker session/DST audits.

This diagnostic never sends, modifies, or closes orders. It refuses to run unless
the connected account is explicitly identified by MT5 as a Demo account.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .broker_clock import infer_broker_offset
from .mt5_adapter import candle_from_mt5
from .timeframes import Timeframe, expected_interval


EVIDENCE_WINDOWS = (
    (
        "ordinary_weekday_rollover",
        datetime(2026, 9, 28, 18, tzinfo=UTC),
        datetime(2026, 9, 30, 6, tzinfo=UTC),
    ),
    (
        "friday_sunday_weekend",
        datetime(2026, 10, 2, 18, tzinfo=UTC),
        datetime(2026, 10, 5, 8, tzinfo=UTC),
    ),
    (
        "dst_spring_2025",
        datetime(2025, 3, 28, tzinfo=UTC),
        datetime(2025, 4, 1, tzinfo=UTC),
    ),
    (
        "dst_autumn_2025",
        datetime(2025, 10, 24, tzinfo=UTC),
        datetime(2025, 10, 28, tzinfo=UTC),
    ),
    (
        "dst_spring_2026",
        datetime(2026, 3, 27, tzinfo=UTC),
        datetime(2026, 3, 31, tzinfo=UTC),
    ),
    (
        "good_friday_2026",
        datetime(2026, 4, 2, tzinfo=UTC),
        datetime(2026, 4, 7, tzinfo=UTC),
    ),
)

_TIMEFRAME_CONSTANTS = (
    (Timeframe.D1, "TIMEFRAME_D1"),
    (Timeframe.H4, "TIMEFRAME_H4"),
    (Timeframe.H1, "TIMEFRAME_H1"),
    (Timeframe.M15, "TIMEFRAME_M15"),
    (Timeframe.M5, "TIMEFRAME_M5"),
)


def resolve_symbol_read_only(mt5: Any, requested: str) -> str:
    """Resolve an exact/suffixed symbol without changing Market Watch state."""
    if not requested:
        raise ValueError("SYMBOL_REQUIRED")
    if mt5.symbol_info(requested) is not None:
        return requested

    symbols_get = getattr(mt5, "symbols_get", None)
    if not callable(symbols_get):
        raise RuntimeError(f"MT5_SYMBOL_NOT_FOUND:{requested}")
    candidates = sorted(
        {
            str(getattr(item, "name", ""))
            for item in (symbols_get() or ())
            if str(getattr(item, "name", "")).startswith(
                (requested + ".", requested + "#")
            )
        }
    )
    if len(candidates) != 1:
        reason = "AMBIGUOUS" if candidates else "NOT_FOUND"
        raise RuntimeError(f"MT5_SYMBOL_{reason}:{requested}:{candidates}")
    return candidates[0]


def collect_market_hours_evidence(mt5: Any, symbol: str) -> dict[str, Any]:
    """Return observed candle-open timestamps and gaps without trade actions."""
    evidence: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "symbol": symbol,
        "read_only": True,
        "account_mode": "DEMO",
        "windows": {},
    }

    for timeframe, constant_name in _TIMEFRAME_CONSTANTS:
        timeframe_value = getattr(mt5, constant_name, None)
        if timeframe_value is None:
            raise RuntimeError(f"MT5_TIMEFRAME_UNAVAILABLE:{timeframe.value}")
        interval = expected_interval(timeframe)
        for label, start, end in EVIDENCE_WINDOWS:
            rates = mt5.copy_rates_range(symbol, timeframe_value, start, end)
            if rates is None:
                error = getattr(mt5, "last_error", lambda: "UNKNOWN")()
                raise RuntimeError(
                    f"MT5_RANGE_REQUEST_FAILED:{label}:{timeframe.value}:{error}"
                )

            candles = sorted(
                (candle_from_mt5(rate) for rate in rates),
                key=lambda candle: candle.timestamp,
            )
            timestamps = [candle.timestamp for candle in candles]
            gaps = []
            duplicates = []
            for previous, current in zip(timestamps, timestamps[1:]):
                elapsed = current - previous
                if elapsed == 0:
                    duplicates.append(current.isoformat())
                elif elapsed > interval * 2:
                    gaps.append(
                        {
                            "previous_open_utc": previous.isoformat(),
                            "current_open_utc": current.isoformat(),
                            "elapsed_seconds": int(elapsed.total_seconds()),
                            "previous_utc_weekday": previous.strftime("%A"),
                            "current_utc_weekday": current.strftime("%A"),
                        }
                    )

            item: dict[str, Any] = {
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "candle_count": len(timestamps),
                "first_open_utc": timestamps[0].isoformat() if timestamps else None,
                "last_open_utc": timestamps[-1].isoformat() if timestamps else None,
                "gaps_over_two_intervals": gaps,
                "duplicate_opens_utc": duplicates,
            }
            if timeframe is Timeframe.D1:
                offsets = []
                for timestamp in timestamps:
                    try:
                        offset = infer_broker_offset((timestamp,))
                        offsets.append(
                            {
                                "d1_open_utc": timestamp.isoformat(),
                                "inferred_utc_offset_minutes": int(
                                    offset.total_seconds() / 60
                                ),
                            }
                        )
                    except ValueError as exc:
                        offsets.append(
                            {
                                "d1_open_utc": timestamp.isoformat(),
                                "inference_error": str(exc),
                            }
                        )
                item["d1_open_offset_samples"] = offsets
            evidence["windows"].setdefault(label, {})[timeframe.value] = item

    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect read-only Pepperstone MT5 Demo candle-gap evidence"
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("var/xau-detective-ai/market-hours-evidence.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise RuntimeError(f"MT5_INITIALIZE_FAILED:{mt5.last_error()}")

    try:
        account = mt5.account_info()
        if account is None:
            raise RuntimeError("MT5_ACCOUNT_INFO_UNAVAILABLE")
        demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        if getattr(account, "trade_mode", None) != demo_mode:
            raise RuntimeError("DEMO_ACCOUNT_REQUIRED_FOR_READ_ONLY_EVIDENCE")

        symbol = resolve_symbol_read_only(mt5, args.symbol)
        evidence = collect_market_hours_evidence(mt5, symbol)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"MARKET_HOURS_EVIDENCE_WRITTEN | symbol={symbol} "
            f"| windows={len(EVIDENCE_WINDOWS)} | output={args.output}"
        )
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
