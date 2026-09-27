from datetime import datetime, timedelta, timezone
from decimal import Decimal

from xau_detective.redundancy import FeatureSeries, RedundancyConfig, analyze_redundancy

def series(name: str, family: str, values: tuple[str, ...]) -> FeatureSeries:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = tuple(start + timedelta(minutes=15 * i) for i in range(len(values)))
    return FeatureSeries(name, family, "M15", timestamps, tuple(Decimal(value) for value in values))

def test_high_correlation_is_flagged_and_clustered():
    values = tuple(str(i) for i in range(40))
    report = analyze_redundancy((series("ema_fast", "trend", values), series("ema_slow", "trend", values)))
    assert len(report.pairs) == 1
    assert report.pairs[0].same_evidence_family is True
    assert report.pairs[0].correlation > Decimal("0.99")
    assert report.clusters[0].features == ("ema_fast", "ema_slow")
    assert report.clusters[0].representative == "ema_fast"

def test_negative_correlation_is_also_redundant():
    values = tuple(str(i) for i in range(40))
    inverse = tuple(str(100 - i) for i in range(40))
    report = analyze_redundancy((series("trend", "trend", values), series("inverse", "momentum", inverse)))
    assert len(report.pairs) == 1
    assert report.pairs[0].correlation < Decimal("-0.99")

def test_low_correlation_is_not_flagged():
    values_a = tuple(str(i % 2) for i in range(40))
    values_b = tuple(str((i * 7) % 13) for i in range(40))
    report = analyze_redundancy((series("a", "a", values_a), series("b", "b", values_b)))
    assert report.pairs == ()

def test_insufficient_overlap_is_neutral():
    values = tuple(str(i) for i in range(10))
    report = analyze_redundancy((series("a", "trend", values), series("b", "momentum", values)), config=RedundancyConfig(min_observations=30))
    assert report.pairs == ()
    assert report.insufficient_pairs == 1

def test_missing_values_align_point_in_time():
    values_a = tuple(str(i) if i % 3 else None for i in range(40))
    values_b = tuple(str(i) for i in range(40))
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = tuple(start + timedelta(minutes=15 * i) for i in range(40))
    left = FeatureSeries("a", "trend", "M15", timestamps, tuple(Decimal(v) if v is not None else None for v in values_a))
    right = series("b", "trend", values_b)
    report = analyze_redundancy((left, right))
    assert len(report.pairs) == 1

def test_priority_controls_representative_deterministically():
    values = tuple(str(i) for i in range(40))
    report = analyze_redundancy((series("ema_fast", "trend", values), series("ema_slow", "trend", values)), priority={"ema_slow": 1, "ema_fast": 2})
    assert report.clusters[0].representative == "ema_slow"