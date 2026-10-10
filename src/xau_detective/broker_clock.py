"""Broker-clock utilities inferred from MT5 candle boundaries.

MT5 candle timestamps are normalized to UTC by the adapter. A broker's D1
candle opens at broker midnight, so the latest D1 open provides the current
broker UTC offset without hardcoding GMT+2/GMT+3 or a user's local timezone.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Iterable


def infer_broker_offset(daily_open_times: Iterable[datetime]) -> timedelta:
    timestamps = tuple(daily_open_times)
    if not timestamps:
        raise ValueError("BROKER_TIME_D1_DATA_REQUIRED")

    utc_timestamps: list[datetime] = []
    for timestamp in timestamps:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("BROKER_TIME_UTC_TIMESTAMP_REQUIRED")
        normalized_timestamp = timestamp.astimezone(UTC)
        if normalized_timestamp.second or normalized_timestamp.microsecond:
            raise ValueError("BROKER_TIME_D1_OPEN_NOT_MINUTE_ALIGNED")
        utc_timestamps.append(normalized_timestamp)

    offsets = {
        timedelta(
            seconds=(
                -(
                    timestamp.hour * 3600
                    + timestamp.minute * 60
                )
            )
            % 86400
        )
        for timestamp in utc_timestamps
    }
    if len(offsets) != 1:
        raise ValueError("BROKER_TIME_OFFSET_INCONSISTENT")

    seconds = next(iter(offsets))
    if seconds >= timedelta(hours=12):
        seconds -= timedelta(days=1)
    if seconds < timedelta(hours=-12) or seconds > timedelta(hours=14):
        raise ValueError("BROKER_TIME_OFFSET_OUT_OF_RANGE")
    return seconds


def broker_timezone(offset: timedelta) -> timezone:
    if offset < timedelta(hours=-12) or offset > timedelta(hours=14):
        raise ValueError("BROKER_TIME_OFFSET_OUT_OF_RANGE")
    return timezone(offset, name=f"Broker UTC{offset.total_seconds() / 3600:+g}")


def to_broker_time(timestamp_utc: datetime, offset: timedelta) -> datetime:
    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    return timestamp_utc.astimezone(broker_timezone(offset))
