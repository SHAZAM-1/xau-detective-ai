from datetime import UTC, datetime

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
    previous = datetime(2026, 10, 2, tzinfo=UTC)
    current = datetime(2026, 10, 5, tzinfo=UTC)
    assert pepperstone_gold_gap_is_expected(previous, current)
