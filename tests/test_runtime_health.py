from datetime import UTC, datetime

from xau_detective.runtime_health import RuntimeHealthTracker


def test_runtime_health_tracks_operational_events():
    tracker = RuntimeHealthTracker()
    now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

    tracker.cycle_started(now)
    tracker.preflight_passed()
    tracker.analysis_attempted(now)
    tracker.reconciliation_checked(now, active_exposure=True)
    tracker.execution_attempted(now)
    tracker.execution_succeeded()

    snapshot = tracker.snapshot()
    assert snapshot.cycles == 1
    assert snapshot.successful_preflights == 1
    assert snapshot.analysis_attempts == 1
    assert snapshot.execution_attempts == 1
    assert snapshot.execution_successes == 1
    assert snapshot.reconciliation_checks == 1
    assert snapshot.active_exposure
    assert snapshot.last_cycle_at == now


def test_runtime_health_normalizes_naive_timestamps():
    tracker = RuntimeHealthTracker()
    naive = datetime(2026, 9, 27, 12, 0)
    tracker.cycle_started(naive)
    tracker.rejected("TEST_REJECTION")
    tracker.errored("TEST_ERROR")

    snapshot = tracker.snapshot()
    assert snapshot.last_cycle_at is not None
    assert snapshot.last_cycle_at.tzinfo is UTC
    assert snapshot.rejected_cycles == 1
    assert snapshot.error_cycles == 1
    assert snapshot.last_reason == "TEST_ERROR"
