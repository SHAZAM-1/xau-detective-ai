from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xau_detective.data_quality import validate_candles
from xau_detective.market import Candle


def c(t):
    return Candle(t, Decimal(1), Decimal(2), Decimal("0.5"), Decimal("1.5"))


def test_data_gap_is_rejected():
    t = datetime.now(UTC)
    result = validate_candles((c(t), c(t + timedelta(hours=3))), timedelta(hours=1))
    assert not result.usable
    assert "DATA_GAP" in result.reasons


def test_non_monotonic_timestamps_are_rejected():
    t = datetime.now(UTC)
    result = validate_candles((c(t), c(t - timedelta(minutes=5))), timedelta(minutes=5))
    assert not result.usable
    assert "NON_MONOTONIC_TIMESTAMPS" in result.reasons


def test_duplicate_timestamps_are_rejected():
    t = datetime.now(UTC)
    result = validate_candles((c(t), c(t)), timedelta(minutes=5))
    assert not result.usable
    assert "NON_MONOTONIC_TIMESTAMPS" in result.reasons


def test_zero_range_candle_is_rejected():
    t = datetime.now(UTC)
    candle = Candle(t, Decimal(1), Decimal(1), Decimal(1), Decimal(1))
    result = validate_candles((candle,))
    assert not result.usable
    assert "ZERO_RANGE_CANDLE" in result.reasons


def test_non_positive_price_is_rejected():
    t = datetime.now(UTC)
    candle = Candle(t, Decimal(0), Decimal(1), Decimal("0.5"), Decimal("0.8"))
    result = validate_candles((candle,))
    assert not result.usable
    assert "NON_POSITIVE_PRICE" in result.reasons



def test_expected_gap_policy_can_allow_a_known_session_closure():
    t = datetime(2026, 10, 5, 23, 55, tzinfo=UTC)
    result = validate_candles(
        (c(t), c(t + timedelta(hours=1, minutes=5))),
        timedelta(minutes=5),
        gap_is_expected=lambda previous, current: True,
    )
    assert result.usable


def test_gap_policy_does_not_hide_unexpected_gaps():
    t = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    result = validate_candles(
        (c(t), c(t + timedelta(hours=1))),
        timedelta(minutes=5),
        gap_is_expected=lambda previous, current: False,
    )
    assert not result.usable
    assert "DATA_GAP" in result.reasons


def test_timeframe_specific_gap_policy_receives_timeframe():
    from xau_detective.timeframes import Timeframe

    t = datetime(2026, 10, 5, 21, tzinfo=UTC)
    seen = []

    def policy(previous, current, timeframe):
        seen.append(timeframe)
        return timeframe is Timeframe.H4

    result = validate_candles(
        (c(t), c(t + timedelta(hours=3))),
        timedelta(hours=1),
        timeframe=Timeframe.H4,
        gap_is_expected_for_timeframe=policy,
    )

    assert result.usable
    assert seen == [Timeframe.H4]


def test_timeframe_specific_gap_policy_fails_closed_without_timeframe():
    t = datetime(2026, 10, 5, 21, tzinfo=UTC)
    result = validate_candles(
        (c(t), c(t + timedelta(hours=3))),
        timedelta(hours=1),
        gap_is_expected_for_timeframe=lambda previous, current, timeframe: True,
    )

    assert not result.usable
    assert "DATA_GAP" in result.reasons



def test_naive_candle_timestamp_is_rejected():
    result = validate_candles(
        (c(datetime(2026, 10, 6, 10, 0)),),
    )
    assert not result.usable
    assert "NAIVE_TIMESTAMP" in result.reasons


def test_invalid_candle_timestamp_type_is_rejected():
    candle = Candle(None, Decimal(1), Decimal(2), Decimal("0.5"), Decimal("1.5"))
    result = validate_candles((candle,))
    assert not result.usable
    assert "INVALID_TIMESTAMP" in result.reasons
