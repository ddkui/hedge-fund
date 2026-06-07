import pytest
from datetime import date
from agents.supervisor_researcher.scorer import (
    calculate_relevance_score,
    calculate_academic_score,
    calculate_confidence_score,
    tag_strategies,
)


def test_calculate_relevance_score():
    """Test relevance score for momentum paper - should score > 50."""
    paper_title = "Advanced Momentum Strategies in Quantitative Trading"
    paper_abstract = "This paper explores momentum-based trading strategies using machine learning techniques."
    strategy_descriptions = {
        "momentum": "Trading strategies based on trend following and momentum",
        "mean_reversion": "Strategies that exploit mean reverting patterns",
        "pairs_trading": "Statistical arbitrage using pairs trading",
        "ml": "Machine learning and neural network approaches",
        "alternative_data": "Using alternative data sources like sentiment"
    }

    score = calculate_relevance_score(paper_title, paper_abstract, strategy_descriptions)
    assert isinstance(score, float)
    assert 0 <= score <= 100
    assert score > 50, f"Expected momentum paper to score > 50, got {score}"


def test_calculate_academic_score():
    """Test academic score calculation - should return 0-100."""
    citations = 150
    max_citations = 1000
    venue_rank = 0.8  # 80% of max

    score = calculate_academic_score(citations, max_citations, venue_rank)
    assert isinstance(score, float)
    assert 0 <= score <= 100

    # Verify calculation: (150/1000)*100*0.7 + 0.8*100*0.3 = 10.5 + 24 = 34.5
    expected = (citations / max_citations) * 100 * 0.7 + venue_rank * 100 * 0.3
    assert abs(score - expected) < 0.01


def test_calculate_academic_score_zero_max():
    """Test academic score when max_citations_in_dataset is 0."""
    score = calculate_academic_score(0, 0, 0.5)
    assert isinstance(score, float)
    assert 0 <= score <= 100


def test_calculate_confidence_score():
    """Test confidence score formula: 0.5*relevance + 0.3*recency + 0.2*academic."""
    relevance_score = 80.0
    academic_score = 70.0
    days_old = 3

    score = calculate_confidence_score(relevance_score, academic_score, days_old)
    assert isinstance(score, float)
    assert 0 <= score <= 100

    # Verify formula: 0.5*80 + 0.3*((7-3)/7*100) + 0.2*70
    # = 40 + 0.3*57.14 + 14 = 40 + 17.14 + 14 = 71.14
    recency_score = max(0, (7 - days_old) / 7 * 100)
    expected = (
        0.5 * relevance_score +
        0.3 * recency_score +
        0.2 * academic_score
    )
    assert abs(score - expected) < 0.1


def test_calculate_confidence_score_old_paper():
    """Test confidence score for paper older than 7 days (recency = 0)."""
    relevance_score = 80.0
    academic_score = 70.0
    days_old = 10  # More than 7 days old

    score = calculate_confidence_score(relevance_score, academic_score, days_old)
    assert isinstance(score, float)
    assert 0 <= score <= 100

    # Recency should be 0 since days_old > 7
    # Expected: 0.5*80 + 0.3*0 + 0.2*70 = 40 + 0 + 14 = 54
    expected = 0.5 * relevance_score + 0.2 * academic_score
    assert abs(score - expected) < 0.1


def test_tag_strategies_momentum():
    """Test strategy tagging for momentum paper - should include 'momentum'."""
    abstract = "This paper explores momentum-based trading strategies using trend following approaches."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert len(tags) > 0
    assert "momentum" in tags


def test_tag_strategies_mean_reversion():
    """Test strategy tagging for mean reversion paper."""
    abstract = "A study on mean reversion patterns in financial markets, focusing on reverting trends."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert "mean_reversion" in tags


def test_tag_strategies_ml():
    """Test strategy tagging for machine learning paper."""
    abstract = "Deep learning neural networks for trading signal generation and LSTM models."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert "ml" in tags


def test_tag_strategies_pairs_trading():
    """Test strategy tagging for pairs trading paper."""
    abstract = "Statistical arbitrage using pairs trading methodology."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert "pairs_trading" in tags


def test_tag_strategies_alternative_data():
    """Test strategy tagging for alternative data paper."""
    abstract = "Sentiment analysis and satellite imagery data for market prediction."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert "alternative_data" in tags


def test_tag_strategies_no_match():
    """Test strategy tagging when no keywords match - should return 'other'."""
    abstract = "A study on general economic policy and government regulations."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert "other" in tags


def test_tag_strategies_multiple_matches():
    """Test strategy tagging for paper matching multiple strategies."""
    abstract = "Machine learning approaches to momentum and mean reversion detection using neural networks."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert len(tags) >= 2  # Should match at least momentum, mean_reversion, ml
    assert "momentum" in tags or "mean_reversion" in tags or "ml" in tags


def test_tag_strategies_case_insensitive():
    """Test that strategy tagging is case-insensitive."""
    abstract = "MOMENTUM strategies and DEEP LEARNING techniques for trading."
    tags = tag_strategies(abstract)

    assert isinstance(tags, list)
    assert "momentum" in tags
    assert "ml" in tags  # Should match "deep learning"


def test_calculate_relevance_score_low_relevance():
    """Test relevance score for completely unrelated paper."""
    paper_title = "Agricultural Practices in Ancient Rome"
    paper_abstract = "A historical study of farming methods in ancient Rome."
    strategy_descriptions = {
        "momentum": "Trading strategies based on trend following",
        "mean_reversion": "Strategies that exploit mean reverting patterns",
    }

    score = calculate_relevance_score(paper_title, paper_abstract, strategy_descriptions)
    assert isinstance(score, float)
    assert 0 <= score <= 100
    # This should have very low relevance to trading strategies


def test_calculate_academic_score_high_citations():
    """Test academic score with high citations."""
    citations = 500
    max_citations = 500
    venue_rank = 1.0  # Perfect venue

    score = calculate_academic_score(citations, max_citations, venue_rank)
    # Expected: (500/500)*100*0.7 + 1.0*100*0.3 = 70 + 30 = 100
    assert score == 100.0


def test_calculate_confidence_score_new_paper():
    """Test confidence score for very recent paper (1 day old)."""
    relevance_score = 90.0
    academic_score = 85.0
    days_old = 1

    score = calculate_confidence_score(relevance_score, academic_score, days_old)
    # Recency: (7-1)/7*100 = 85.7
    # Expected: 0.5*90 + 0.3*85.7 + 0.2*85 = 45 + 25.71 + 17 = 87.71
    recency_score = (7 - days_old) / 7 * 100
    expected = (
        0.5 * relevance_score +
        0.3 * recency_score +
        0.2 * academic_score
    )
    assert abs(score - expected) < 0.1
