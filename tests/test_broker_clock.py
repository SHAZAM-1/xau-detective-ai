from datetime import UTC, datetime, timedelta

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
