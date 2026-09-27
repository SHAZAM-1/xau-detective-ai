from datetime import datetime, timedelta, timezone
from decimal import Decimal

from xau_detective.pattern_study import PatternDatasetRow
from xau_detective.scoring import fit_baseline, score_row, score_rows_oos

def row(i: int, *, pattern: str = "Hammer", direction: str = "BULLISH", ret: str = "0.01") -> PatternDatasetRow:
    return PatternDatasetRow(
        timeframe="M15", pattern=pattern,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * i),
        index=i, direction=direction, confidence=Decimal("0.9"), horizon=1,
        forward_return=Decimal(ret), mfe=Decimal("0.01"), mae=Decimal("0.005"),
    )

def test_baseline_uses_training_statistics_only():
    train = tuple(row(i, ret="0.01") for i in range(30))
    result = score_row(row(100, ret="-0.50"), fit_baseline(train))
    assert result.score > 50
    assert result.reason == "CALIBRATED_BASELINE"

def test_small_samples_are_not_promoted():
    train = tuple(row(i) for i in range(10))
    result = score_row(row(100), fit_baseline(train))
    assert result.score == 50
    assert result.reason == "INSUFFICIENT_SAMPLE"

def test_unseen_context_is_neutral():
    train = tuple(row(i) for i in range(30))
    result = score_row(row(100, pattern="Evening Star", direction="BEARISH", ret="-0.01"), fit_baseline(train))
    assert result.score == 50
    assert result.reason == "UNSEEN_CONTEXT"

def test_oos_scoring_does_not_fit_on_test_rows():
    train = tuple(row(i, ret="0.01") for i in range(30))
    test = tuple(row(100 + i, ret="-0.01") for i in range(30))
    scores = score_rows_oos(train, test)
    assert all(item.score > 50 for item in scores)
