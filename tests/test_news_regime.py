from datetime import UTC, datetime

from xau_detective.news_regime import (
    NewsCategory,
    NewsObservation,
    NewsRegime,
    classify_news_regime,
)


def test_missing_news_data_is_unknown():
    result = classify_news_regime(())
    assert result.regime is NewsRegime.UNKNOWN
    assert result.evidence == ("NEWS_DATA_UNAVAILABLE",)


def test_high_impact_geopolitical_context_is_preserved():
    result = classify_news_regime(
        (
            NewsObservation(
                datetime(2026, 10, 1, 12, tzinfo=UTC),
                NewsCategory.GEOPOLITICAL,
                NewsRegime.HIGH_IMPACT,
                high_impact_count=1,
                source_count=2,
            ),
        )
    )
    assert result.regime is NewsRegime.HIGH_IMPACT
    assert NewsCategory.GEOPOLITICAL in result.categories
    assert "HIGH_IMPACT_NEWS_PRESENT" in result.evidence


def test_multiple_categories_are_deduplicated():
    result = classify_news_regime(
        (
            NewsObservation(
                datetime(2026, 10, 1, 12, tzinfo=UTC),
                NewsCategory.MACRO,
                NewsRegime.ELEVATED,
            ),
            NewsObservation(
                datetime(2026, 10, 1, 12, 1, tzinfo=UTC),
                NewsCategory.MACRO,
                NewsRegime.CALM,
            ),
            NewsObservation(
                datetime(2026, 10, 1, 12, 2, tzinfo=UTC),
                NewsCategory.CENTRAL_BANK,
                NewsRegime.ELEVATED,
            ),
        )
    )
    assert result.regime is NewsRegime.ELEVATED
    assert result.categories == (NewsCategory.MACRO, NewsCategory.CENTRAL_BANK)
