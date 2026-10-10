from datetime import UTC, datetime, timedelta, timezone

import pytest

from xau_detective.broker_clock import infer_broker_offset, to_broker_time


def test_infer_pepperstone_summer_server_offset():
    daily = (
        datetime(2026, 10, 5, 21, tzinfo=UTC),
        datetime(2026, 10, 6, 21, tzinfo=UTC),
    )
    assert infer_broker_offset(daily) == timedelta(hours=3)


def test_infer_pepperstone_winter_server_offset():
    daily = (
        datetime(2026, 11, 2, 22, tzinfo=UTC),
        datetime(2026, 11, 3, 22, tzinfo=UTC),
    )
    assert infer_broker_offset(daily) == timedelta(hours=2)


def test_broker_time_conversion():
    timestamp = datetime(2026, 10, 6, 20, 15, tzinfo=UTC)
    assert to_broker_time(timestamp, timedelta(hours=3)).hour == 23


def test_inconsistent_broker_offsets_fail_closed():
    daily = (
        datetime(2026, 10, 5, 21, tzinfo=UTC),
        datetime(2026, 10, 6, 22, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="BROKER_TIME_OFFSET_INCONSISTENT"):
        infer_broker_offset(daily)


def test_infer_offset_normalizes_aware_non_utc_datetime():
    # Midnight at UTC+3 is 21:00 UTC on the previous date.
    daily = (datetime(2026, 10, 6, 0, tzinfo=timezone(timedelta(hours=3))),)
    assert infer_broker_offset(daily) == timedelta(hours=3)


def test_naive_daily_open_timestamp_fails_closed():
    with pytest.raises(ValueError, match="BROKER_TIME_UTC_TIMESTAMP_REQUIRED"):
        infer_broker_offset((datetime(2026, 10, 5, 21),))


def test_daily_open_with_seconds_fails_closed():
    with pytest.raises(ValueError, match="BROKER_TIME_D1_OPEN_NOT_MINUTE_ALIGNED"):
        infer_broker_offset((datetime(2026, 10, 5, 21, 0, 1, tzinfo=UTC),))


def test_broker_time_conversion_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="UTC_TIMESTAMP_REQUIRED"):
        to_broker_time(datetime(2026, 10, 6, 20, 15), timedelta(hours=3))
