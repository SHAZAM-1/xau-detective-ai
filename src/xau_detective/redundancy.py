"""Training-only feature redundancy analysis for XAUUSD research.

The analyzer identifies highly correlated feature series so the scoring layer
does not accidentally count the same market information more than once.
It never deletes features or makes trade decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt


@dataclass(frozen=True)
class FeatureSeries:
    """A point-in-time feature series aligned by timestamp."""
    name: str
    evidence_family: str
    timeframe: str
    timestamps: tuple[object, ...]
    values: tuple[Decimal | None, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("feature name must not be empty")
        if not self.evidence_family.strip():
            raise ValueError("evidence family must not be empty")
        if not self.timeframe.strip():
            raise ValueError("timeframe must not be empty")
        if len(self.timestamps) != len(self.values):
            raise ValueError("timestamps and values must have equal length")


@dataclass(frozen=True)
class RedundancyConfig:
    correlation_threshold: Decimal = Decimal("0.85")
    min_observations: int = 30

    def __post_init__(self) -> None:
        if self.correlation_threshold <= 0 or self.correlation_threshold > 1:
            raise ValueError("correlation_threshold must be in (0, 1]")
        if self.min_observations < 2:
            raise ValueError("min_observations must be at least 2")


@dataclass(frozen=True)
class RedundantFeaturePair:
    left: str
    right: str
    correlation: Decimal
    observations: int
    same_evidence_family: bool
    reason: str


@dataclass(frozen=True)
class RedundancyCluster:
    cluster_id: int
    features: tuple[str, ...]
    representative: str


@dataclass(frozen=True)
class RedundancyReport:
    pairs: tuple[RedundantFeaturePair, ...]
    clusters: tuple[RedundancyCluster, ...]
    insufficient_pairs: int


def _pearson(values_a: tuple[Decimal, ...], values_b: tuple[Decimal, ...]) -> Decimal | None:
    if len(values_a) != len(values_b) or len(values_a) < 2:
        return None
    mean_a = sum(values_a, Decimal(0)) / Decimal(len(values_a))
    mean_b = sum(values_b, Decimal(0)) / Decimal(len(values_b))
    centered_a = tuple(value - mean_a for value in values_a)
    centered_b = tuple(value - mean_b for value in values_b)
    numerator = sum((a * b for a, b in zip(centered_a, centered_b)), Decimal(0))
    denom_a = sum((a * a for a in centered_a), Decimal(0))
    denom_b = sum((b * b for b in centered_b), Decimal(0))
    if denom_a == 0 or denom_b == 0:
        return None
    denominator = Decimal(str(sqrt(float(denom_a * denom_b))))
    if denominator == 0:
        return None
    return numerator / denominator


def _aligned(left: FeatureSeries, right: FeatureSeries) -> tuple[tuple[Decimal, ...], tuple[Decimal, ...]]:
    right_by_timestamp = {timestamp: value for timestamp, value in zip(right.timestamps, right.values) if value is not None}
    left_values: list[Decimal] = []
    right_values: list[Decimal] = []
    for timestamp, value in zip(left.timestamps, left.values):
        if value is None:
            continue
        counterpart = right_by_timestamp.get(timestamp)
        if counterpart is None:
            continue
        left_values.append(value)
        right_values.append(counterpart)
    return tuple(left_values), tuple(right_values)


def analyze_redundancy(series: tuple[FeatureSeries, ...], *, config: RedundancyConfig = RedundancyConfig(), priority: dict[str, int] | None = None) -> RedundancyReport:
    """Analyze pairwise redundancy using only the supplied training series.

    Call this with training-window observations only. No future/test values are
    consumed or inferred by this function.
    """
    ordered = tuple(sorted(series, key=lambda item: (item.timeframe, item.name)))
    pairs: list[RedundantFeaturePair] = []
    insufficient_pairs = 0

    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            if left.timeframe != right.timeframe:
                continue
            left_values, right_values = _aligned(left, right)
            observations = len(left_values)
            if observations < config.min_observations:
                insufficient_pairs += 1
                continue
            correlation = _pearson(left_values, right_values)
            if correlation is None:
                insufficient_pairs += 1
                continue
            if abs(correlation) < config.correlation_threshold:
                continue
            reason = ("SAME_EVIDENCE_FAMILY_AND_HIGH_CORRELATION" if left.evidence_family == right.evidence_family else "HIGH_CORRELATION_ACROSS_EVIDENCE_FAMILIES")
            pairs.append(RedundantFeaturePair(left.name, right.name, correlation, observations, left.evidence_family == right.evidence_family, reason))

    parent = {item.name: item.name for item in ordered}
    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name
    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left
    for pair in pairs:
        union(pair.left, pair.right)
    groups: dict[str, list[str]] = {}
    for name in sorted(parent):
        groups.setdefault(find(name), []).append(name)
    def rank(name: str) -> tuple[int, str]:
        return ((priority or {}).get(name, 10**9), name)
    clusters: list[RedundancyCluster] = []
    for cluster_id, names in enumerate(sorted((tuple(sorted(names)) for names in groups.values() if len(names) > 1)), start=1):
        representative = min(names, key=rank)
        clusters.append(RedundancyCluster(cluster_id, names, representative))
    return RedundancyReport(tuple(pairs), tuple(clusters), insufficient_pairs)