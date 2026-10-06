"""Pepperstone Spot Gold session-gap policy for MT5 market data."""
from __future__ import annotations

from datetime import datetime, time, timedelta


_DAILY_CLOSE = time(23, 45)
_DAILY_OPEN = time(1, 15)


def pepperstone_gold_gap_is_expected(previous: datetime, current: datetime) -> bool:
    """Allow only documented daily rollover and weekend closures."""
    if current <= previous:
        return False

    # Friday -> Monday and weekend boundaries are expected closures.
    if previous.weekday() == 4 and current.weekday() == 0:
        return True
    if previous.weekday() == 5 and current.weekday() == 0:
        return True
    if previous.weekday() == 6 and current.weekday() == 0:
        return True

    # Monday-Thursday: Gold closes near 23:59 server time and reopens near 01:01.
    next_day = previous.date() + timedelta(days=1)
    return (
        previous.weekday() in {0, 1, 2, 3}
        and current.date() == next_day
        and previous.time() >= _DAILY_CLOSE
        and current.time() <= _DAILY_OPEN
    )
