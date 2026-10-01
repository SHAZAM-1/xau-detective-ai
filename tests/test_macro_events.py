from datetime import UTC, datetime, timedelta

from xau_detective.macro_events import MacroEvent, MacroEventType, classify_macro_event


BASE = datetime(2026, 10, 1, 12, tzinfo=UTC)


def test_upcoming_event_has_no_release_surprise():
    event = MacroEvent(MacroEventType.CPI, BASE + timedelta(hours=1), consensus=3.0)
    result = classify_macro_event(event, now=BASE)
    assert result.state == "UPCOMING"
    assert result.surprise is None


def test_released_event_calculates_consensus_surprise():
    event = MacroEvent(
        MacroEventType.NFP,
        BASE,
        actual=250.0,
        consensus=180.0,
        previous=200.0,
    )
    result = classify_macro_event(event, now=BASE + timedelta(minutes=1))
    assert result.state == "RELEASED"
    assert result.surprise == 70.0
    assert "SURPRISE_ABOVE_CONSENSUS" in result.evidence
    assert "ACTUAL_ABOVE_PREVIOUS" in result.evidence


def test_released_event_without_actual_fails_closed():
    event = MacroEvent(MacroEventType.FOMC, BASE, consensus=4.5)
    result = classify_macro_event(event, now=BASE + timedelta(minutes=1))
    assert result.state == "RELEASED_DATA_UNAVAILABLE"
    assert result.surprise is None


def test_all_supported_macro_event_types_are_explicit():
    assert {item.value for item in MacroEventType} == {"FOMC", "CPI", "PCE", "NFP"}
