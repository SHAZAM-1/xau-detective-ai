"""Research-only news and geopolitical regime classification.

The classifier records the state of supplied, timestamped information. It does
not fetch news, infer sentiment from absent data, or convert headlines into
trade directions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NewsRegime(str, Enum):
    CALM = "CALM"
    ELEVATED = "ELEVATED"
    HIGH_IMPACT = "HIGH_IMPACT"
    UNKNOWN = "UNKNOWN"


class NewsCategory(str, Enum):
    MACRO = "MACRO"
    GEOPOLITICAL = "GEOPOLITICAL"
    CENTRAL_BANK = "CENTRAL_BANK"
    MARKET = "MARKET"


@dataclass(frozen=True)
class NewsObservation:
    timestamp: datetime
    category: NewsCategory
    regime: NewsRegime
    headline_count: int = 0
    high_impact_count: int = 0
    source_count: int = 0


@dataclass(frozen=True)
class NewsContext:
    regime: NewsRegime
    categories: tuple[NewsCategory, ...]
    evidence: tuple[str, ...]


def classify_news_regime(
    observations: tuple[NewsObservation, ...],
) -> NewsContext:
    """Aggregate supplied observations without inventing missing information."""
    if not observations:
        return NewsContext(NewsRegime.UNKNOWN, (), ("NEWS_DATA_UNAVAILABLE",))

    evidence: list[str] = []
    categories = tuple(dict.fromkeys(item.category for item in observations))
    highest = max(
        observations,
        key=lambda item: (
            item.regime is NewsRegime.HIGH_IMPACT,
            item.regime is NewsRegime.ELEVATED,
            item.regime is NewsRegime.CALM,
        ),
    ).regime

    if highest is NewsRegime.HIGH_IMPACT:
        evidence.append("HIGH_IMPACT_NEWS_PRESENT")
    elif highest is NewsRegime.ELEVATED:
        evidence.append("ELEVATED_NEWS_PRESENT")
    elif highest is NewsRegime.CALM:
        evidence.append("NEWS_REGIME_CALM")
    else:
        evidence.append("NEWS_REGIME_UNKNOWN")

    for category in categories:
        evidence.append(f"CATEGORY={category.value}")

    return NewsContext(highest, categories, tuple(evidence))
