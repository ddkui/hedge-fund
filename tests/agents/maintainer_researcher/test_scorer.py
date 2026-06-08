import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from agents.maintainer_researcher.scorer import (
    calculate_implementability_score,
    calculate_strategic_value_score,
    calculate_maintainer_relevance_score,
    calculate_overall_score,
    tag_issue_types
)


def test_calculate_implementability_score():
    """Test implementability score calculation."""
    title = "Efficient Algorithm Implementation"
    abstract = "This paper describes an efficient algorithm with code examples and pseudocode."

    score = calculate_implementability_score(title, abstract)

    assert 0 <= score <= 100
    assert isinstance(score, float)
    # Score should be reasonably high due to keywords
    assert score > 20


def test_calculate_strategic_value_score():
    """Test strategic value score calculation for hedge fund operations."""
    title = "Automated Trading Execution System"
    abstract = "An advanced system for automated order routing and risk management in trading."

    score = calculate_strategic_value_score(title, abstract)

    assert 0 <= score <= 100
    assert isinstance(score, float)
    # Should score higher due to trading-relevant keywords
    assert score > 20


def test_calculate_maintainer_relevance_score_recent_paper():
    """Test maintainer relevance score for recent papers."""
    title = "Recent Implementation Advances"
    abstract = "Implementation details and architectural patterns."

    # Paper published 2 days ago
    score = calculate_maintainer_relevance_score(title, abstract, days_old=2)

    assert 0 <= score <= 100
    assert isinstance(score, float)
    # Should be weighted towards recency (60%) + implementability (40%)
    # Recency: (7-2)/7 * 100 = 71.4
    assert score > 40


def test_calculate_maintainer_relevance_score_old_paper():
    """Test maintainer relevance score for old papers."""
    title = "Old Implementation Details"
    abstract = "Implementation details from years ago."

    # Paper published 15 days ago (beyond threshold)
    score = calculate_maintainer_relevance_score(title, abstract, days_old=15)

    assert 0 <= score <= 100
    assert isinstance(score, float)
    # Recency score would be 0 since 15 > 7
    assert score >= 0


def test_calculate_maintainer_relevance_score_boundary():
    """Test maintainer relevance at 7-day boundary."""
    title = "Boundary Test Paper"
    abstract = "Testing boundary conditions for relevance scoring."

    # Paper published exactly 7 days ago
    score = calculate_maintainer_relevance_score(title, abstract, days_old=7)

    assert 0 <= score <= 100
    assert isinstance(score, float)
    # Recency: (7-7)/7 * 100 = 0


def test_calculate_overall_score():
    """Test overall score calculation as weighted average."""
    implementability = 80.0
    strategic_value = 75.0
    maintainer_relevance = 85.0

    overall = calculate_overall_score(implementability, strategic_value, maintainer_relevance)

    # Expected: 0.35*80 + 0.35*75 + 0.30*85 = 28 + 26.25 + 25.5 = 79.75
    expected = 0.35 * 80 + 0.35 * 75 + 0.30 * 85
    assert abs(overall - expected) < 0.1
    assert 0 <= overall <= 100


def test_calculate_overall_score_zero_scores():
    """Test overall score with zero component scores."""
    overall = calculate_overall_score(0.0, 0.0, 0.0)

    assert overall == 0.0


def test_calculate_overall_score_max_scores():
    """Test overall score with maximum component scores."""
    overall = calculate_overall_score(100.0, 100.0, 100.0)

    assert overall == 100.0


def test_tag_issue_types_with_algorithm():
    """Test issue type tagging detects algorithm keywords."""
    abstract = "Efficient algorithm implementation with optimized code structure"

    tags = tag_issue_types(abstract)

    assert isinstance(tags, list)
    assert "algorithm" in tags


def test_tag_issue_types_with_architecture():
    """Test issue type tagging detects architecture keywords."""
    abstract = "Novel system architecture and design patterns for distributed systems"

    tags = tag_issue_types(abstract)

    assert isinstance(tags, list)
    assert "architecture" in tags


def test_tag_issue_types_with_performance():
    """Test issue type tagging detects performance keywords."""
    abstract = "Performance optimization and scalability improvements through parallelization"

    tags = tag_issue_types(abstract)

    assert isinstance(tags, list)
    assert "performance" in tags


def test_tag_issue_types_with_reliability():
    """Test issue type tagging detects reliability keywords."""
    abstract = "Fault tolerance and resilience mechanisms for distributed systems"

    tags = tag_issue_types(abstract)

    assert isinstance(tags, list)
    assert "reliability" in tags


def test_tag_issue_types_multiple_matches():
    """Test issue type tagging with multiple matching keywords."""
    abstract = "Algorithm with optimized architecture for reliable performance and scalability"

    tags = tag_issue_types(abstract)

    assert isinstance(tags, list)
    assert len(tags) > 0
    # Should detect multiple issue types
    assert len(set(tags)) >= 1


def test_tag_issue_types_no_matches():
    """Test issue type tagging returns investigation when no keywords match."""
    abstract = "Random unrelated text about birds and weather patterns and cooking"

    tags = tag_issue_types(abstract)

    assert isinstance(tags, list)
    assert "investigation" in tags


def test_tag_issue_types_case_insensitive():
    """Test that tagging is case insensitive."""
    abstract_lower = "algorithm implementation details"
    abstract_upper = "ALGORITHM IMPLEMENTATION DETAILS"

    tags_lower = tag_issue_types(abstract_lower)
    tags_upper = tag_issue_types(abstract_upper)

    assert "algorithm" in tags_lower
    assert "algorithm" in tags_upper


def test_score_calculations_preserve_bounds():
    """Test that all score calculations respect 0-100 bounds."""
    # Test with extreme sentiment inputs
    extreme_title = "Unbelievably revolutionary world-changing breakthrough algorithm ever"
    extreme_abstract = "This is the most important work ever done with incredible optimization"

    impl_score = calculate_implementability_score(extreme_title, extreme_abstract)
    strat_score = calculate_strategic_value_score(extreme_title, extreme_abstract)
    maint_score = calculate_maintainer_relevance_score(extreme_title, extreme_abstract, days_old=1)

    assert 0 <= impl_score <= 100
    assert 0 <= strat_score <= 100
    assert 0 <= maint_score <= 100

    overall = calculate_overall_score(impl_score, strat_score, maint_score)
    assert 0 <= overall <= 100
