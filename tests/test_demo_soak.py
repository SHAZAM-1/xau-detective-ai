from datetime import UTC, datetime

from xau_detective.demo_soak import run_demo_soak, valid_candles


def test_soak_runs_repeated_cycles_without_orders_when_analysis_disabled():
    result = run_demo_soak(cycles=25)
    assert result.cycles == 25
    assert result.orders_sent == 0
    assert set(result.reasons) == {"AUTO_ANALYSIS_DISABLED"}


def test_soak_fails_closed_on_connection_loss():
    result = run_demo_soak(cycles=20, failure_cycle=7, failure="DISCONNECT")
    assert result.cycles == 20
    assert all(reason == "MT5_CONNECTION_UNHEALTHY" for reason in result.reasons)


def test_soak_fails_closed_on_missing_tick():
    result = run_demo_soak(cycles=10, failure_cycle=3, failure="TICK")
    assert all(reason == "MT5_TICK_UNAVAILABLE" for reason in result.reasons)


def test_soak_rejects_live_environment():
    result = run_demo_soak(cycles=5, failure="LIVE")
    assert all(reason == "LIVE_EXECUTION_LOCKED_V1" for reason in result.reasons)


def test_soak_validates_cycle_count():
    try:
        run_demo_soak(cycles=0)
    except ValueError as exc:
        assert str(exc) == "cycles must be positive"
    else:
        raise AssertionError("expected ValueError")


def test_valid_candles_are_point_in_time_safe():
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    data = valid_candles(now)
    assert all(series[-1].timestamp < now for series in data.values())
