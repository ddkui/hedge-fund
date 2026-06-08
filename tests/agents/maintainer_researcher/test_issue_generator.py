from datetime import date
import pytest
from agents.maintainer_researcher.models import PaperMetadata
from agents.maintainer_researcher.issue_generator import (
    generate_issue_title,
    generate_issue_body,
    create_draft_github_issue
)


def test_generate_issue_title_basic():
    """Test generating GitHub issue title from paper metadata."""
    title = generate_issue_title(
        paper_title="Efficient Algorithm for Distributed Systems",
        paper_authors="Smith, J.; Doe, A.",
        issue_type="feature"
    )

    assert "[FEATURE]" in title
    assert "Efficient Algorithm for Distributed Systems" in title


def test_generate_issue_title_with_colon():
    """Test that colons in paper titles are handled correctly."""
    title = generate_issue_title(
        paper_title="Advanced Techniques: A Comprehensive Guide",
        paper_authors="Author, A.",
        issue_type="enhancement"
    )

    assert "[ENHANCEMENT]" in title
    assert "Advanced Techniques - A Comprehensive Guide" in title
    assert ":" not in title


def test_generate_issue_title_truncation():
    """Test that long titles are truncated to 80 characters."""
    long_title = "A" * 100  # 100 character title
    title = generate_issue_title(
        paper_title=long_title,
        paper_authors="Author",
        issue_type="feature"
    )

    # Should be truncated
    assert len(title) <= 90  # [FEATURE] + 80 chars + ellipsis
    assert title.endswith("...")


def test_generate_issue_title_case_sensitivity():
    """Test that issue type is uppercased in title."""
    title_lowercase = generate_issue_title(
        paper_title="Test Paper",
        paper_authors="Author",
        issue_type="bug"
    )

    assert "[BUG]" in title_lowercase
    assert "[bug]" not in title_lowercase


def test_generate_issue_body_structure():
    """Test that generated issue body contains all required sections."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_001",
        source="arxiv",
        title="Test Paper Title",
        authors="Smith, J.; Doe, A.",
        abstract="This is a test abstract about algorithms and systems.",
        url="https://arxiv.org/abs/2024.00001",
        publication_date=date(2024, 6, 1)
    )

    body = generate_issue_body(
        metadata=metadata,
        implementability_score=85.0,
        strategic_value_score=78.0,
        maintainer_relevance_score=90.0,
        overall_score=84.3,
        suggested_tags="algorithm,architecture"
    )

    # Check for required sections
    assert "## Paper Summary" in body
    assert "## Relevance Assessment" in body
    assert "## Suggested Issue Tags" in body
    assert "## Next Steps" in body
    assert metadata.title in body
    assert metadata.authors in body
    assert metadata.url in body


def test_generate_issue_body_scores_displayed():
    """Test that scores are displayed correctly in issue body."""
    metadata = PaperMetadata(
        paper_id="test_001",
        source="arxiv",
        title="Score Test Paper",
        authors="Test Author",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 6, 1)
    )

    body = generate_issue_body(
        metadata=metadata,
        implementability_score=75.5,
        strategic_value_score=82.3,
        maintainer_relevance_score=88.7,
        overall_score=82.2,
        suggested_tags="test"
    )

    assert "75.5" in body
    assert "82.3" in body
    assert "88.7" in body
    assert "82.2" in body


def test_generate_issue_body_abstract_included():
    """Test that paper abstract is included in issue body."""
    abstract_text = "This paper proposes a novel approach to distributed consensus using advanced algorithms."
    metadata = PaperMetadata(
        paper_id="abstract_test",
        source="arxiv",
        title="Abstract Test",
        authors="Author",
        abstract=abstract_text,
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )

    body = generate_issue_body(
        metadata=metadata,
        implementability_score=50.0,
        strategic_value_score=50.0,
        maintainer_relevance_score=50.0,
        overall_score=50.0,
        suggested_tags="test"
    )

    assert abstract_text in body


def test_create_draft_github_issue_complete():
    """Test creating a complete draft GitHub issue."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_draft",
        source="arxiv",
        title="Complete Draft Issue Test",
        authors="Test Author, Another Author",
        abstract="Testing the complete issue creation workflow.",
        url="https://arxiv.org/abs/2024.draft",
        publication_date=date(2024, 6, 1)
    )

    issue = create_draft_github_issue(
        metadata=metadata,
        implementability_score=80.0,
        strategic_value_score=75.0,
        maintainer_relevance_score=85.0,
        overall_score=80.0,
        suggested_tags="algorithm,performance",
        issue_type="feature"
    )

    # Verify structure
    assert isinstance(issue, dict)
    assert "title" in issue
    assert "body" in issue
    assert "labels" in issue
    assert "paper_id" in issue
    assert "paper_url" in issue

    # Verify content
    assert "[FEATURE]" in issue["title"]
    assert "Complete Draft Issue Test" in issue["title"]
    assert "## Paper Summary" in issue["body"]
    assert "## Relevance Assessment" in issue["body"]
    assert "feature" in issue["labels"]
    assert "research-based" in issue["labels"]
    assert "automated" in issue["labels"]
    assert issue["paper_id"] == "arxiv_2024_draft"
    assert issue["paper_url"] == "https://arxiv.org/abs/2024.draft"


def test_create_draft_github_issue_labels():
    """Test that draft issue includes correct labels."""
    metadata = PaperMetadata(
        paper_id="label_test",
        source="arxiv",
        title="Label Test",
        authors="Author",
        abstract="Testing labels",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )

    # Test with feature issue type
    feature_issue = create_draft_github_issue(
        metadata=metadata,
        implementability_score=70.0,
        strategic_value_score=70.0,
        maintainer_relevance_score=70.0,
        overall_score=70.0,
        suggested_tags="test",
        issue_type="feature"
    )

    assert "feature" in feature_issue["labels"]
    assert "research-based" in feature_issue["labels"]
    assert "automated" in feature_issue["labels"]

    # Test with bug issue type
    bug_issue = create_draft_github_issue(
        metadata=metadata,
        implementability_score=70.0,
        strategic_value_score=70.0,
        maintainer_relevance_score=70.0,
        overall_score=70.0,
        suggested_tags="test",
        issue_type="bug"
    )

    assert "bug" in bug_issue["labels"]
    assert "research-based" in bug_issue["labels"]
    assert "automated" in bug_issue["labels"]


def test_create_draft_github_issue_default_type():
    """Test that create_draft_github_issue defaults to 'feature' type."""
    metadata = PaperMetadata(
        paper_id="default_test",
        source="arxiv",
        title="Default Type Test",
        authors="Author",
        abstract="Testing default issue type",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )

    # Call without specifying issue_type
    issue = create_draft_github_issue(
        metadata=metadata,
        implementability_score=60.0,
        strategic_value_score=60.0,
        maintainer_relevance_score=60.0,
        overall_score=60.0,
        suggested_tags="test"
    )

    # Should default to feature
    assert "feature" in issue["labels"]
    assert "[FEATURE]" in issue["title"]


def test_generate_issue_body_paper_id_reference():
    """Test that generated issue body includes paper ID reference."""
    paper_id = "arxiv_2024_reference"
    metadata = PaperMetadata(
        paper_id=paper_id,
        source="arxiv",
        title="Reference Test",
        authors="Author",
        abstract="Testing paper ID reference",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )

    body = generate_issue_body(
        metadata=metadata,
        implementability_score=50.0,
        strategic_value_score=50.0,
        maintainer_relevance_score=50.0,
        overall_score=50.0,
        suggested_tags="test"
    )

    assert paper_id in body
    assert "MaintainerResearcherAgent" in body
