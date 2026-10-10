"""Pepperstone Spot Gold session-gap policy for MT5 market data."""
from __future__ import annotations

from datetime import date, datetime, timedelta


# Candle timestamps are normalized to UTC by the MT5 adapter. Avoid checking
# fixed wall-clock hours here: the broker's UTC offset changes with DST.
_MIN_ROLLOVER_GAP = timedelta(minutes=30)
_MAX_ROLLOVER_GAP = timedelta(hours=4)
_MIN_WEEKEND_GAP = timedelta(hours=36)
_MAX_WEEKEND_GAP = timedelta(hours=80)
_MIN_HOLIDAY_GAP = timedelta(hours=72)
_MAX_HOLIDAY_GAP = timedelta(hours=108)


def _easter_sunday(year: int) -> date:
    """Return Western Easter Sunday for the Gregorian calendar."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    easter_offset = (32 + 2 * e + 2 * i - h - k) % 7
    month_offset = (a + 11 * h + 22 * easter_offset) // 451
    month = (h + easter_offset - 7 * month_offset + 114) // 31
    day = ((h + easter_offset - 7 * month_offset + 114) % 31) + 1
    return date(year, month, day)


def pepperstone_gold_gap_is_expected(previous: datetime, current: datetime) -> bool:
    """Recognize bounded rollover/weekend/Good Friday gaps; reject long outages.

    The input timestamps must be timezone-aware and are expected to be UTC
    normalized. Calendar boundaries alone are insufficient evidence that a
    data gap is expected, so each accepted closure also has an elapsed-time
    bound. Actual broker session hours should be validated against MT5 data.
    """
    if (
        previous.tzinfo is None
        or current.tzinfo is None
        or current <= previous
    ):
        return False

    elapsed = current - previous
    day_delta = (current.date() - previous.date()).days

    # Normal weekday rollover. Duration-based bounds avoid fixed UTC clock
    # assumptions and continue to work when the broker's offset changes.
    if (
        previous.weekday() in {0, 1, 2, 3}
        and day_delta == 1
        and _MIN_ROLLOVER_GAP <= elapsed <= _MAX_ROLLOVER_GAP
    ):
        return True

    # Friday -> Monday weekend closure, limited to a plausible weekend span.
    if (
        previous.weekday() == 4
        and current.weekday() == 0
        and day_delta == 3
        and _MIN_WEEKEND_GAP <= elapsed <= _MAX_WEEKEND_GAP
    ):
        return True

    # Good Friday removes the Friday daily candle, creating a Thursday -> Monday gap.
    good_friday = _easter_sunday(previous.year) - timedelta(days=2)
    return (
        previous.date() == good_friday - timedelta(days=1)
        and current.date() == good_friday + timedelta(days=3)
        and current.weekday() == 0
        and day_delta == 4
        and _MIN_HOLIDAY_GAP <= elapsed <= _MAX_HOLIDAY_GAP
    )
