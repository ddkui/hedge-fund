from datetime import date
import pytest
from agents.maintainer_researcher.models import PaperMetadata, ScoredPaper


def test_paper_metadata_creation():
    """Test creating a PaperMetadata instance with all required fields."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_001",
        source="arxiv",
        title="Distributed System Consensus Algorithms",
        authors="Smith, J.; Johnson, K.",
        abstract="This paper explores consensus mechanisms in distributed systems.",
        url="https://arxiv.org/abs/2024.00001",
        publication_date=date(2024, 6, 1)
    )

    assert metadata.paper_id == "arxiv_2024_001"
    assert metadata.source == "arxiv"
    assert metadata.title == "Distributed System Consensus Algorithms"
    assert metadata.authors == "Smith, J.; Johnson, K."
    assert metadata.abstract == "This paper explores consensus mechanisms in distributed systems."
    assert metadata.url == "https://arxiv.org/abs/2024.00001"
    assert metadata.publication_date == date(2024, 6, 1)


def test_scored_paper_creation():
    """Test creating a ScoredPaper instance with metadata and scores."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_002",
        source="arxiv",
        title="Real-time Data Processing Optimization",
        authors="Doe, A.; Smith, B.",
        abstract="A comprehensive study on streaming data systems.",
        url="https://arxiv.org/abs/2024.00002",
        publication_date=date(2024, 6, 1)
    )

    scored = ScoredPaper(
        metadata=metadata,
        implementability_score=85.5,
        strategic_value_score=78.2,
        maintainer_relevance_score=92.1,
        overall_score=85.3,
        suggested_issue_tags="architecture,performance,reliability"
    )

    assert scored.metadata.paper_id == "arxiv_2024_002"
    assert scored.implementability_score == 85.5
    assert scored.strategic_value_score == 78.2
    assert scored.maintainer_relevance_score == 92.1
    assert scored.overall_score == 85.3
    assert scored.suggested_issue_tags == "architecture,performance,reliability"


def test_paper_metadata_validation():
    """Test that PaperMetadata validates required fields."""
    with pytest.raises(Exception):
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
    """Test ScoredPaper with various issue tags."""
    metadata = PaperMetadata(
        paper_id="test_001",
        source="arxiv",
        title="Multi-Component Framework",
        authors="Test Author",
        abstract="Testing multiple components",
        url="https://example.com",
        publication_date=date(2024, 6, 8)
    )

    # Test with single tag
    scored1 = ScoredPaper(
        metadata=metadata,
        implementability_score=50.0,
        strategic_value_score=50.0,
        maintainer_relevance_score=50.0,
        overall_score=50.0,
        suggested_issue_tags="algorithm"
    )
    assert scored1.suggested_issue_tags == "algorithm"

    # Test with multiple tags
    scored2 = ScoredPaper(
        metadata=metadata,
        implementability_score=75.0,
        strategic_value_score=75.0,
        maintainer_relevance_score=75.0,
        overall_score=75.0,
        suggested_issue_tags="algorithm,architecture,performance"
    )
    assert scored2.suggested_issue_tags == "algorithm,architecture,performance"


def test_paper_metadata_different_sources():
    """Test PaperMetadata handles different sources correctly."""
    arxiv_metadata = PaperMetadata(
        paper_id="arxiv_123",
        source="arxiv",
        title="ArXiv Paper",
        authors="Author A",
        abstract="Abstract",
        url="https://arxiv.org",
        publication_date=date(2024, 6, 1)
    )
    assert arxiv_metadata.source == "arxiv"

    ssrn_metadata = PaperMetadata(
        paper_id="ssrn_456",
        source="ssrn",
        title="SSRN Paper",
        authors="Author B",
        abstract="Abstract",
        url="https://ssrn.com",
        publication_date=date(2024, 6, 1)
    )
    assert ssrn_metadata.source == "ssrn"
