"""Pepperstone Spot Gold session-gap policy for MT5 market data."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta


_DAILY_CLOSE = time(23, 45)
_DAILY_OPEN = time(1, 15)


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
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def pepperstone_gold_gap_is_expected(previous: datetime, current: datetime) -> bool:
    """Allow documented daily rollover, weekend, and Good Friday closures."""
    if current <= previous:
        return False

    # Friday -> Monday and weekend boundaries are expected closures.
    if previous.weekday() == 4 and current.weekday() == 0:
        return True
    if previous.weekday() == 5 and current.weekday() == 0:
        return True
    if previous.weekday() == 6 and current.weekday() == 0:
        return True

    # Good Friday removes the Friday daily candle, creating a Thursday -> Monday gap.
    good_friday = _easter_sunday(previous.year) - timedelta(days=2)
    if (
        previous.date() == good_friday - timedelta(days=1)
        and current.date() == good_friday + timedelta(days=3)
        and current.weekday() == 0
    ):
        return True

    # Monday-Thursday: Gold closes near 23:59 server time and reopens near 01:01.
    next_day = previous.date() + timedelta(days=1)
    return (
        previous.weekday() in {0, 1, 2, 3}
        and current.date() == next_day
        and previous.time() >= _DAILY_CLOSE
        and current.time() <= _DAILY_OPEN
    )
