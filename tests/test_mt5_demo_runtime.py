from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from xau_detective.market import Candle
from xau_detective.mt5_demo_runtime import RuntimeConfig, build_profile, fetch_closed_snapshot, run_once
from xau_detective.timeframes import Timeframe


NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def make_candles(timeframe: Timeframe, count: int = 50) -> tuple[Candle, ...]:
    intervals = {
        Timeframe.M5: timedelta(minutes=5),
        Timeframe.M15: timedelta(minutes=15),
        Timeframe.H1: timedelta(hours=1),
        Timeframe.H4: timedelta(hours=4),
        Timeframe.D1: timedelta(days=1),
    }
    step = intervals[timeframe]
    start = NOW - step * (count + 2)
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


class FakeSource:
    def fetch(self, symbol, timeframe, count):
        assert symbol == "XAUUSD"
        assert count == 50
        return make_candles(timeframe, count)


class FakeService:
    def __init__(self):
        self.calls = []

    def cycle(self, **kwargs):
        self.calls.append(kwargs)
        return type("Result", (), {"reason": "NO_TRADE"})()


def test_runtime_requires_execution_gates_to_match():
    with pytest.raises(ValueError, match="EXECUTION_GATES_MUST_MATCH"):
        RuntimeConfig(execution_enabled=True, auto_execution_enabled=False).validate()


def test_build_profile_keeps_execution_disabled_by_default():
    profile = build_profile(RuntimeConfig())
    assert profile.auto_execution_enabled is False
    assert profile.auto_analysis_enabled is True


def test_fetch_closed_snapshot_excludes_forming_candle():
    source = FakeSource()
    data = fetch_closed_snapshot(source, symbol="XAUUSD", count=50, now=NOW)
    for candles in data.values():
        assert candles
        assert candles[-1].timestamp + {
            Timeframe.D1: timedelta(days=1),
            Timeframe.H4: timedelta(hours=4),
            Timeframe.H1: timedelta(hours=1),
            Timeframe.M15: timedelta(minutes=15),
            Timeframe.M5: timedelta(minutes=5),
        }[next(tf for tf, values in data.items() if values is candles)] <= NOW


def test_run_once_uses_newly_closed_m5_candle_as_idempotency_key():
    source = FakeSource()
    service = FakeService()
    closed_m5, result = run_once(
        source=source,
        service=service,
        profile=build_profile(RuntimeConfig()),
        symbol="XAUUSD",
        candle_count=50,
        now=NOW,
    )
    assert result.reason == "NO_TRADE"
    assert len(service.calls) == 1
    assert service.calls[0]["idempotency_key"] == f"XAUUSD:M5:{closed_m5.isoformat()}"
    assert service.calls[0]["m5"][-1].timestamp + timedelta(minutes=5) <= NOW
\n\ndef test_run_once_skips_same_closed_m5_candle():\n    source = FakeSource()\n    service = FakeService()\n    closed_m5, first = run_once(\n        source=source,\n        service=service,\n        profile=build_profile(RuntimeConfig()),\n        symbol="XAUUSD",\n        candle_count=50,\n        now=NOW,\n    )\n    closed_again, second = run_once(\n        source=source,\n        service=service,\n        profile=build_profile(RuntimeConfig()),\n        symbol="XAUUSD",\n        candle_count=50,\n        now=NOW,\n        last_closed_m5=closed_m5,\n    )\n    assert first is not None\n    assert closed_again == closed_m5\n    assert second is None\n    assert len(service.calls) == 1\n