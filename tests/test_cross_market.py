from datetime import UTC, datetime
from decimal import Decimal

from xau_detective.cross_market import (
    CrossMarketObservation,
    classify_cross_market_context,
)


def observation(dxy: Decimal | None, real_yield: Decimal | None) -> CrossMarketObservation:
    return CrossMarketObservation(
        timestamp=datetime(2026, 10, 1, tzinfo=UTC),
        dxy_return=dxy,
        real_yield_change=real_yield,
    )


def test_cross_market_context_is_supportive_when_both_inputs_fall():
    result = classify_cross_market_context(observation(Decimal("-0.2"), Decimal("-0.05")))
    assert result.dxy_state == "DOWN"
    assert result.real_yield_state == "DOWN"
    assert result.gold_context == "GOLD_SUPPORTIVE_CONTEXT"


def test_cross_market_context_is_headwind_when_both_inputs_rise():
    result = classify_cross_market_context(observation(Decimal("0.2"), Decimal("0.05")))
    assert result.dxy_state == "UP"
    assert result.real_yield_state == "UP"
    assert result.gold_context == "GOLD_HEADWIND_CONTEXT"


def test_cross_market_context_fails_closed_when_data_is_missing():
    result = classify_cross_market_context(observation(None, Decimal("-0.05")))
    assert result.dxy_state == "UNKNOWN"
    assert result.gold_context == "INSUFFICIENT_CROSS_MARKET_DATA"


def test_cross_market_context_marks_mixed_inputs():
    result = classify_cross_market_context(observation(Decimal("-0.2"), Decimal("0.05")))
    assert result.gold_context == "MIXED_CROSS_MARKET_CONTEXT"
    assert "DXY_STATE=DOWN" in result.evidence
    assert "REAL_YIELD_STATE=UP" in result.evidence
