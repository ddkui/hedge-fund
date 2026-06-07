from datetime import date
import pytest
from agents.supervisor_researcher.models import PaperMetadata, ScoredPaper


def test_paper_metadata_creation():
    """Test creating a PaperMetadata instance with all required fields."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_001",
        source="arxiv",
        title="Advanced Momentum Strategies in Quantitative Trading",
        authors="Smith, J.; Johnson, K.",
        abstract="This paper explores momentum-based trading strategies using machine learning.",
        url="https://arxiv.org/abs/2024.00001",
        publication_date=date(2024, 3, 15)
    )

    # Assert all fields are set correctly
    assert metadata.paper_id == "arxiv_2024_001"
    assert metadata.source == "arxiv"
    assert metadata.title == "Advanced Momentum Strategies in Quantitative Trading"
    assert metadata.authors == "Smith, J.; Johnson, K."
    assert metadata.abstract == "This paper explores momentum-based trading strategies using machine learning."
    assert metadata.url == "https://arxiv.org/abs/2024.00001"
    assert metadata.publication_date == date(2024, 3, 15)


def test_scored_paper_creation():
    """Test creating a ScoredPaper instance with metadata and scores."""
    metadata = PaperMetadata(
        paper_id="ssrn_2024_002",
        source="ssrn",
        title="Mean Reversion Detection Using Deep Learning",
        authors="Doe, A.; Smith, B.",
        abstract="A comprehensive study on mean reversion patterns.",
        url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4567890",
        publication_date=date(2024, 1, 10)
    )

    scored = ScoredPaper(
        metadata=metadata,
        relevance_score=85.5,
        academic_score=78.2,
        confidence_score=92.1,
        strategy_tags="mean_reversion,deep_learning,signal_processing"
    )

    # Assert all fields are set correctly
    assert scored.metadata.paper_id == "ssrn_2024_002"
    assert scored.relevance_score == 85.5
    assert scored.academic_score == 78.2
    assert scored.confidence_score == 92.1
    assert scored.strategy_tags == "mean_reversion,deep_learning,signal_processing"


def test_paper_metadata_validation():
    """Test that PaperMetadata validates required fields."""
    # Pydantic will raise ValidationError when missing required fields
    with pytest.raises(Exception):  # Pydantic raises ValidationError
        PaperMetadata(
            paper_id="test",
            source="arxiv",
            title="Test",
            authors="Test Author",
            abstract="Test abstract",
            url="https://example.com"
            # Missing publication_date - required field
        )


def test_scored_paper_with_various_tags():
    """Test ScoredPaper with various strategy tags."""
    metadata = PaperMetadata(
        paper_id="test_001",
        source="arxiv",
        title="Multi-Strategy Framework",
        authors="Test Author",
        abstract="Testing multiple strategies",
        url="https://example.com",
        publication_date=date(2024, 6, 8)
    )

    # Test with single tag
    scored1 = ScoredPaper(
        metadata=metadata,
        relevance_score=50.0,
        academic_score=50.0,
        confidence_score=50.0,
        strategy_tags="momentum"
    )
    assert scored1.strategy_tags == "momentum"

    # Test with multiple tags
    scored2 = ScoredPaper(
        metadata=metadata,
        relevance_score=75.0,
        academic_score=75.0,
        confidence_score=75.0,
        strategy_tags="momentum,mean_reversion,ml"
    )
    assert scored2.strategy_tags == "momentum,mean_reversion,ml"
