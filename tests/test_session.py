from datetime import datetime, timezone

from xau_detective.session import classify_session


def test_session_windows_and_overlap():
    assert classify_session(datetime(2026, 1, 1, 5, tzinfo=timezone.utc)).label == "ASIA"
    assert classify_session(datetime(2026, 1, 1, 10, tzinfo=timezone.utc)).label == "LONDON"
    assert classify_session(datetime(2026, 1, 1, 14, tzinfo=timezone.utc)).overlap == "LONDON+NEW_YORK"


def test_off_session():
    assert classify_session(datetime(2026, 1, 1, 23, tzinfo=timezone.utc)).label == "OFF_SESSION"
