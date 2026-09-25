from datetime import UTC, datetime


from xau_detective.session import classify_session


def test_session_windows_and_overlap():
    assert classify_session(datetime(2026, 1, 1, 5, tzinfo=UTC)).label == "ASIA"
    assert classify_session(datetime(2026, 1, 1, 10, tzinfo=UTC)).label == "LONDON"
    assert classify_session(datetime(2026, 1, 1, 14, tzinfo=UTC)).overlap == "LONDON+NEW_YORK"


def test_off_session():
    assert classify_session(datetime(2026, 1, 1, 23, tzinfo=UTC)).label == "OFF_SESSION"
