from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from xau_detective.audit_log import JsonlAuditLog
from xau_detective.market import Candle
from xau_detective.mt5_demo_runtime import (
    RuntimeConfig,
    build_profile,
    fetch_closed_snapshot,
    run_demo_runtime,
    run_once,
)
from xau_detective.timeframes import Timeframe
from xau_detective.trade_journal import JsonlTradeJournal


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
        RuntimeConfig(
            execution_enabled=True,
            auto_execution_enabled=False,
        ).validate()


def test_build_profile_keeps_execution_disabled_by_default():
    profile = build_profile(RuntimeConfig())
    assert profile.auto_execution_enabled is False
    assert profile.auto_analysis_enabled is True


def test_fetch_closed_snapshot_excludes_forming_candle():
    source = FakeSource()
    data = fetch_closed_snapshot(
        source,
        symbol="XAUUSD",
        count=50,
        now=NOW,
    )

    intervals = {
        Timeframe.D1: timedelta(days=1),
        Timeframe.H4: timedelta(hours=4),
        Timeframe.H1: timedelta(hours=1),
        Timeframe.M15: timedelta(minutes=15),
        Timeframe.M5: timedelta(minutes=5),
    }

    for timeframe, candles in data.items():
        assert candles
        assert candles[-1].timestamp + intervals[timeframe] <= NOW


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
    assert service.calls[0]["idempotency_key"] == (
        f"XAUUSD:M5:{closed_m5.isoformat()}"
    )
    assert service.calls[0]["m5"][-1].timestamp + timedelta(minutes=5) <= NOW


def test_run_once_skips_same_closed_m5_candle():
    source = FakeSource()
    service = FakeService()
    profile = build_profile(RuntimeConfig())

    closed_m5, first = run_once(
        source=source,
        service=service,
        profile=profile,
        symbol="XAUUSD",
        candle_count=50,
        now=NOW,
    )

    closed_again, second = run_once(
        source=source,
        service=service,
        profile=profile,
        symbol="XAUUSD",
        candle_count=50,
        now=NOW,
        last_closed_m5=closed_m5,
    )

    assert first is not None
    assert closed_again == closed_m5
    assert second is None
    assert len(service.calls) == 1



def test_runtime_shuts_down_if_symbol_resolution_fails(monkeypatch):
    shutdown_calls = []

    class FakeMT5:
        def initialize(self):
            return True

        def shutdown(self):
            shutdown_calls.append(True)

    class BrokenSource:
        def __init__(self, mt5_module):
            pass

        def resolve_symbol(self, symbol):
            raise RuntimeError("SYMBOL_RESOLUTION_FAILED")

    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5CandleSource",
        BrokenSource,
    )

    with pytest.raises(RuntimeError, match="SYMBOL_RESOLUTION_FAILED"):
        run_demo_runtime(
            mt5_module=FakeMT5(),
            config=RuntimeConfig(),
            once=True,
        )

    assert shutdown_calls == [True]



def test_fetch_closed_snapshot_rejects_stale_m5_data():
    class StaleM5Source(FakeSource):
        def fetch(self, symbol, timeframe, count):
            candles = super().fetch(symbol, timeframe, count)
            if timeframe is not Timeframe.M5:
                return candles
            return tuple(
                Candle(
                    timestamp=candle.timestamp - timedelta(hours=1),
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
                for candle in candles
            )

    with pytest.raises(RuntimeError, match="M5:STALE_DATA"):
        fetch_closed_snapshot(
            StaleM5Source(),
            symbol="XAUUSD",
            count=50,
            now=NOW,
        )



def test_runtime_uses_durable_journal_and_audit_log(monkeypatch, tmp_path):
    captured = {}
    shutdown_calls = []

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
            return NOW

    def fake_service(mt5_module, **kwargs):
        captured.update(kwargs)
        return object()

    def fake_run_once(**kwargs):
        return NOW, type("Result", (), {"reason": "NO_TRADE"})()

    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5CandleSource",
        FakeSource,
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5DemoTradingService",
        fake_service,
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.run_once",
        fake_run_once,
    )

    run_demo_runtime(
        mt5_module=FakeMT5(),
        config=RuntimeConfig(log_dir=tmp_path),
        once=True,
        now_fn=lambda: NOW,
    )

    assert isinstance(captured["journal"], JsonlTradeJournal)
    assert captured["journal"].path == tmp_path / "trades.jsonl"
    assert isinstance(captured["audit_log"], JsonlAuditLog)
    assert captured["audit_log"].path == tmp_path / "audit.jsonl"
    assert shutdown_calls == [True]



def test_runtime_rejects_stale_market_tick_before_cycle(monkeypatch, tmp_path):
    shutdown_calls = []
    cycle_calls = []

    class FakeMT5:
        def initialize(self):
            return True

        def shutdown(self):
            shutdown_calls.append(True)

    class StaleTickSource:
        def __init__(self, mt5_module):
            pass

        def resolve_symbol(self, symbol):
            return symbol

        def market_time(self, symbol):
            return NOW - timedelta(minutes=5)

    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5CandleSource",
        StaleTickSource,
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.MT5DemoTradingService",
        lambda mt5_module, **kwargs: object(),
    )
    monkeypatch.setattr(
        "xau_detective.mt5_demo_runtime.run_once",
        lambda **kwargs: cycle_calls.append(True),
    )

    with pytest.raises(RuntimeError, match="MT5_MARKET_TIME_STALE"):
        run_demo_runtime(
            mt5_module=FakeMT5(),
            config=RuntimeConfig(log_dir=tmp_path),
            once=True,
            now_fn=lambda: NOW,
        )

    assert cycle_calls == []
    assert shutdown_calls == [True]
    events = JsonlAuditLog(tmp_path / "audit.jsonl").events()
    assert events[-1].event == "runtime_rejection"
    assert events[-1].reason == "MT5_MARKET_TIME_STALE"
    assert events[-1].status == "BLOCKED"



@pytest.mark.parametrize("risk_fraction", [float("nan"), float("inf"), "not-a-number"])
def test_runtime_config_rejects_malformed_or_non_finite_risk_fraction(risk_fraction):
    with pytest.raises(ValueError, match="RISK_FRACTION_OUT_OF_RANGE"):
        RuntimeConfig(risk_fraction=risk_fraction).validate()


@pytest.mark.parametrize("poll_seconds", ["invalid", "5", True, float("nan"), float("inf"), 0, -1])
def test_runtime_config_rejects_malformed_or_non_positive_poll_interval(poll_seconds):
    with pytest.raises(ValueError, match="POLL_SECONDS_MUST_BE_POSITIVE"):
        RuntimeConfig(poll_seconds=poll_seconds).validate()


def test_build_profile_normalizes_valid_numeric_risk_fraction():
    profile = build_profile(RuntimeConfig(risk_fraction="0.02"))
    assert profile.risk_fraction == Decimal("0.02")


@pytest.mark.parametrize("flag", ["execution_enabled", "auto_execution_enabled"])
def test_runtime_config_rejects_non_boolean_execution_gates(flag):
    with pytest.raises(ValueError, match="EXECUTION_GATES_MUST_MATCH"):
        RuntimeConfig(**{flag: "false", **({"auto_execution_enabled": "false"} if flag == "execution_enabled" else {})}).validate()
