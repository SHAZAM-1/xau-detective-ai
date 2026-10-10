"""Conservative Pepperstone Spot Gold session-gap policy.

Timestamps are UTC-normalized MT5 candle opens. Calendar-only guesses cannot
prove a closure is expected; bounds are intentionally timeframe-specific.
Broker-session validation against captured MT5 candles remains necessary.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .timeframes import Timeframe

_MIN_ROLLOVER_GAP = timedelta(minutes=30)
_MIN_WEEKEND_GAP = timedelta(hours=36)
_MIN_HOLIDAY_GAP = timedelta(hours=72)

# Upper bounds constrain false positives. They are safety limits, not claims
# about exact Pepperstone trading hours; those must be checked against MT5.
_MAX_ROLLOVER_BY_TIMEFRAME = {
    Timeframe.M5: timedelta(hours=2),
    Timeframe.M15: timedelta(hours=2),
    Timeframe.H1: timedelta(hours=3),
    Timeframe.H4: timedelta(hours=8),
    Timeframe.D1: timedelta(hours=4),
}
_MAX_WEEKEND_BY_TIMEFRAME = {
    Timeframe.M5: timedelta(hours=60),
    Timeframe.M15: timedelta(hours=60),
    Timeframe.H1: timedelta(hours=60),
    Timeframe.H4: timedelta(hours=64),
    Timeframe.D1: timedelta(hours=80),
}
_MAX_HOLIDAY_BY_TIMEFRAME = {
    Timeframe.M5: timedelta(hours=84),
    Timeframe.M15: timedelta(hours=84),
    Timeframe.H1: timedelta(hours=84),
    Timeframe.H4: timedelta(hours=96),
    Timeframe.D1: timedelta(hours=108),
}


def _easter_sunday(year: int) -> date:
    """Return Western Easter Sunday for the Gregorian calendar."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - 15) % 30
    i = c // 4
    k = c % 4
    easter_offset = (32 + 2 * e + 2 * i - h - k) % 7
    month_offset = (a + 11 * h + 22 * easter_offset) // 451
    month = (h + easter_offset - 7 * month_offset + 114) // 31
    day = ((h + easter_offset - 7 * month_offset + 114) % 31) + 1
    return date(year, month, day)


def _timeframe(value: Timeframe | str | None) -> Timeframe | None:
    if value is None:
        return None
    if isinstance(value, Timeframe):
        return value
    try:
        return Timeframe(str(value).upper())
    except ValueError:
        return None


def pepperstone_gold_gap_is_expected(
    previous: datetime,
    current: datetime,
    timeframe: Timeframe | str | None = None,
) -> bool:
    """Classify a bounded known-closure-shaped gap for a specific timeframe.

    If timeframe is omitted, preserve the legacy broad bounds for compatibility.
    Production paths should always supply it. Naive timestamps, reversed ranges,
    unknown timeframes, and overlong gaps fail closed.
    """
    if (
        previous.tzinfo is None
        or current.tzinfo is None
        or current <= previous
    ):
        return False

    tf = _timeframe(timeframe)
    if timeframe is not None and tf is None:
        return False

    elapsed = current - previous
    day_delta = (current.date() - previous.date()).days
    max_rollover = (
        _MAX_ROLLOVER_BY_TIMEFRAME[tf]
        if tf is not None
        else timedelta(hours=4)
    )
    max_weekend = (
        _MAX_WEEKEND_BY_TIMEFRAME[tf]
        if tf is not None
        else timedelta(hours=80)
    )
    max_holiday = (
        _MAX_HOLIDAY_BY_TIMEFRAME[tf]
        if tf is not None
        else timedelta(hours=108)
    )

    if (
        previous.weekday() in {0, 1, 2, 3}
        and day_delta == 1
        and _MIN_ROLLOVER_GAP <= elapsed <= max_rollover
    ):
        return True

    if (
        previous.weekday() == 4
        and current.weekday() == 0
        and day_delta == 3
        and _MIN_WEEKEND_GAP <= elapsed <= max_weekend
    ):
        return True

    good_friday = _easter_sunday(previous.year) - timedelta(days=2)
    return (
        previous.date() == good_friday - timedelta(days=1)
        and current.date() == good_friday + timedelta(days=3)
        and current.weekday() == 0
        and day_delta == 4
        and _MIN_HOLIDAY_GAP <= elapsed <= max_holiday
    )
