from datetime import UTC, datetime, timedelta

from xau_detective.mt5_market_hours import pepperstone_gold_gap_is_expected


def test_good_friday_thursday_to_monday_gap_is_expected():
    previous = datetime(2026, 4, 2, tzinfo=UTC)
    current = datetime(2026, 4, 6, tzinfo=UTC)
    assert pepperstone_gold_gap_is_expected(previous, current)


def test_normal_thursday_to_monday_gap_is_not_expected():
    previous = datetime(2026, 4, 9, tzinfo=UTC)
    current = datetime(2026, 4, 13, tzinfo=UTC)
    assert not pepperstone_gold_gap_is_expected(previous, current)


def test_weekend_friday_to_monday_gap_remains_expected():
    previous = datetime(2026, 10, 2, 22, tzinfo=UTC)
    current = datetime(2026, 10, 5, 1, tzinfo=UTC)
    assert pepperstone_gold_gap_is_expected(previous, current)


def test_long_friday_to_monday_outage_is_not_expected():
    previous = datetime(2026, 10, 2, tzinfo=UTC)
    current = datetime(2026, 10, 12, tzinfo=UTC)
    assert not pepperstone_gold_gap_is_expected(previous, current)


def test_daily_rollover_uses_bounded_elapsed_time_not_fixed_utc_hour():
    previous = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)
    current = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
    assert pepperstone_gold_gap_is_expected(previous, current)


def test_long_weekday_gap_is_not_misclassified_as_rollover():
    previous = datetime(2026, 10, 5, 10, tzinfo=UTC)
    current = datetime(2026, 10, 6, 10, tzinfo=UTC)
    assert not pepperstone_gold_gap_is_expected(previous, current)


def test_naive_timestamps_fail_closed():
    previous = datetime(2026, 10, 5, 22, 30)
    current = datetime(2026, 10, 6, 0, 30)
    assert not pepperstone_gold_gap_is_expected(previous, current)


def test_good_friday_dates_do_not_whitelist_unbounded_gap():
    previous = datetime(2026, 4, 2, tzinfo=UTC)
    current = datetime(2026, 4, 6, 13, tzinfo=UTC)
    assert not pepperstone_gold_gap_is_expected(previous, current)
