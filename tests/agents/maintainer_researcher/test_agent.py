from datetime import datetime, date, timedelta
import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session
from agents.maintainer_researcher.agent import MaintainerResearcherAgent
from agents.maintainer_researcher.models import PaperMetadata


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    return MagicMock(spec=Session)


@pytest.fixture
def agent(mock_session):
    """Create a MaintainerResearcherAgent instance with mocked session."""
    return MaintainerResearcherAgent(session=mock_session)


def test_agent_initialization(mock_session):
    """Test that agent initializes with session."""
    agent = MaintainerResearcherAgent(session=mock_session)

    assert agent.session is mock_session


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
@patch("agents.maintainer_researcher.agent.parse_paper_metadata")
@patch("agents.maintainer_researcher.agent.calculate_implementability_score")
@patch("agents.maintainer_researcher.agent.calculate_strategic_value_score")
@patch("agents.maintainer_researcher.agent.calculate_maintainer_relevance_score")
@patch("agents.maintainer_researcher.agent.calculate_overall_score")
@patch("agents.maintainer_researcher.agent.tag_issue_types")
@patch("agents.maintainer_researcher.agent.create_draft_github_issue")
@patch("agents.maintainer_researcher.agent.add_research_record")
def test_agent_run_success(
    mock_add_record,
    mock_create_issue,
    mock_tag_types,
    mock_overall_score,
    mock_maint_relevance,
    mock_strat_value,
    mock_impl_score,
    mock_parse_metadata,
    mock_fetch_papers,
    agent,
    mock_session
):
    """Test successful agent run with papers above score threshold."""
    # Setup mocks
    mock_paper = MagicMock()
    mock_paper.published = datetime.utcnow() - timedelta(days=2)
    mock_fetch_papers.return_value = [mock_paper]

    metadata = PaperMetadata(
        paper_id="test_001",
        source="arxiv",
        title="Test Paper",
        authors="Test Author",
        abstract="Test abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )
    mock_parse_metadata.return_value = metadata

    mock_impl_score.return_value = 80.0
    mock_strat_value.return_value = 75.0
    mock_maint_relevance.return_value = 85.0
    mock_overall_score.return_value = 80.0
    mock_tag_types.return_value = ["algorithm", "performance"]
    mock_create_issue.return_value = {"title": "Test Issue"}
    mock_add_record.return_value = MagicMock()

    # Run agent
    results = agent.run(
        search_queries=["test query"],
        max_papers=50,
        min_overall_score=65.0
    )

    # Assertions
    assert results["papers_fetched"] == 1
    assert results["papers_scored"] == 1
    assert results["draft_issues_created"] == 1
    assert results["research_records_saved"] == 1
    assert results["errors"] == []
    assert len(results) == 5


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
@patch("agents.maintainer_researcher.agent.parse_paper_metadata")
@patch("agents.maintainer_researcher.agent.calculate_implementability_score")
@patch("agents.maintainer_researcher.agent.calculate_strategic_value_score")
@patch("agents.maintainer_researcher.agent.calculate_maintainer_relevance_score")
@patch("agents.maintainer_researcher.agent.calculate_overall_score")
@patch("agents.maintainer_researcher.agent.tag_issue_types")
def test_agent_run_filters_low_scores(
    mock_tag_types,
    mock_overall_score,
    mock_maint_relevance,
    mock_strat_value,
    mock_impl_score,
    mock_parse_metadata,
    mock_fetch_papers,
    agent,
    mock_session
):
    """Test that agent filters papers below score threshold."""
    mock_paper = MagicMock()
    mock_paper.published = datetime.utcnow() - timedelta(days=2)
    mock_fetch_papers.return_value = [mock_paper]

    metadata = PaperMetadata(
        paper_id="low_score",
        source="arxiv",
        title="Low Score Paper",
        authors="Author",
        abstract="Abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )
    mock_parse_metadata.return_value = metadata

    mock_impl_score.return_value = 40.0
    mock_strat_value.return_value = 35.0
    mock_maint_relevance.return_value = 30.0
    mock_overall_score.return_value = 35.0  # Below 65.0 threshold
    mock_tag_types.return_value = ["investigation"]

    results = agent.run(
        search_queries=["test query"],
        max_papers=50,
        min_overall_score=65.0
    )

    # Paper should be scored but not saved
    assert results["papers_fetched"] == 1
    assert results["papers_scored"] == 1
    assert results["draft_issues_created"] == 0
    assert results["research_records_saved"] == 0


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
def test_agent_run_multiple_queries(mock_fetch_papers, agent, mock_session):
    """Test agent processes multiple search queries."""
    mock_fetch_papers.return_value = []

    agent.run(
        search_queries=["query1", "query2", "query3"],
        max_papers=50
    )

    # Verify fetch was called for each query
    assert mock_fetch_papers.call_count == 3
    call_args_list = [call[1]["search_query"] for call in mock_fetch_papers.call_args_list]
    assert "query1" in call_args_list
    assert "query2" in call_args_list
    assert "query3" in call_args_list


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
def test_agent_run_fetch_error_handling(mock_fetch_papers, agent, mock_session):
    """Test agent handles errors during paper fetching."""
    mock_fetch_papers.side_effect = Exception("Network error")

    results = agent.run(
        search_queries=["test query"],
        max_papers=50
    )

    assert results["papers_fetched"] == 0
    assert len(results["errors"]) == 1
    assert "Network error" in results["errors"][0]


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
@patch("agents.maintainer_researcher.agent.parse_paper_metadata")
def test_agent_run_parse_error_handling(mock_parse_metadata, mock_fetch_papers, agent, mock_session):
    """Test agent handles errors during metadata parsing."""
    mock_paper = MagicMock()
    mock_paper.published = datetime.utcnow() - timedelta(days=2)
    mock_fetch_papers.return_value = [mock_paper]

    mock_parse_metadata.side_effect = Exception("Parse error")

    results = agent.run(
        search_queries=["test query"],
        max_papers=50
    )

    assert results["papers_fetched"] == 1
    assert results["papers_scored"] == 0
    assert len(results["errors"]) == 1
    assert "Parse error" in results["errors"][0]


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
@patch("agents.maintainer_researcher.agent.parse_paper_metadata")
@patch("agents.maintainer_researcher.agent.calculate_implementability_score")
@patch("agents.maintainer_researcher.agent.calculate_strategic_value_score")
@patch("agents.maintainer_researcher.agent.calculate_maintainer_relevance_score")
@patch("agents.maintainer_researcher.agent.calculate_overall_score")
@patch("agents.maintainer_researcher.agent.tag_issue_types")
@patch("agents.maintainer_researcher.agent.create_draft_github_issue")
@patch("agents.maintainer_researcher.agent.add_research_record")
def test_agent_run_multiple_papers(
    mock_add_record,
    mock_create_issue,
    mock_tag_types,
    mock_overall_score,
    mock_maint_relevance,
    mock_strat_value,
    mock_impl_score,
    mock_parse_metadata,
    mock_fetch_papers,
    agent,
    mock_session
):
    """Test agent processes multiple papers in single run."""
    # Setup multiple papers
    mock_papers = [
        MagicMock(published=datetime.utcnow() - timedelta(days=1)),
        MagicMock(published=datetime.utcnow() - timedelta(days=2)),
        MagicMock(published=datetime.utcnow() - timedelta(days=3))
    ]
    mock_fetch_papers.return_value = mock_papers

    metadata_list = [
        PaperMetadata(
            paper_id=f"paper_{i}",
            source="arxiv",
            title=f"Paper {i}",
            authors="Author",
            abstract="Abstract",
            url="https://example.com",
            publication_date=date(2024, 6, 1)
        ) for i in range(3)
    ]
    mock_parse_metadata.side_effect = metadata_list

    mock_impl_score.return_value = 85.0
    mock_strat_value.return_value = 80.0
    mock_maint_relevance.return_value = 88.0
    mock_overall_score.return_value = 84.3
    mock_tag_types.return_value = ["algorithm"]
    mock_create_issue.return_value = {"title": "Issue"}
    mock_add_record.return_value = MagicMock()

    results = agent.run(
        search_queries=["test"],
        max_papers=50
    )

    assert results["papers_fetched"] == 3
    assert results["papers_scored"] == 3
    assert results["draft_issues_created"] == 3
    assert results["research_records_saved"] == 3


def test_agent_run_default_parameters(agent, mock_session):
    """Test agent run with default parameters."""
    with patch("agents.maintainer_researcher.agent.fetch_arxiv_papers") as mock_fetch:
        mock_fetch.return_value = []

        agent.run(search_queries=["test"])

        # Verify default parameters
        call_args = mock_fetch.call_args_list[0]
        assert call_args[1]["max_results"] == 50
        assert call_args[1]["days_back"] == 7


def test_agent_run_custom_parameters(agent, mock_session):
    """Test agent run with custom parameters."""
    with patch("agents.maintainer_researcher.agent.fetch_arxiv_papers") as mock_fetch:
        mock_fetch.return_value = []

        agent.run(
            search_queries=["test"],
            max_papers=100,
            min_overall_score=75.0
        )

        # Verify custom parameters
        call_args = mock_fetch.call_args_list[0]
        assert call_args[1]["max_results"] == 100


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
@patch("agents.maintainer_researcher.agent.parse_paper_metadata")
@patch("agents.maintainer_researcher.agent.calculate_implementability_score")
@patch("agents.maintainer_researcher.agent.calculate_strategic_value_score")
@patch("agents.maintainer_researcher.agent.calculate_maintainer_relevance_score")
@patch("agents.maintainer_researcher.agent.calculate_overall_score")
@patch("agents.maintainer_researcher.agent.tag_issue_types")
@patch("agents.maintainer_researcher.agent.add_research_record")
def test_agent_calculates_days_old_correctly(
    mock_add_record,
    mock_tag_types,
    mock_overall_score,
    mock_maint_relevance,
    mock_strat_value,
    mock_impl_score,
    mock_parse_metadata,
    mock_fetch_papers,
    agent,
    mock_session
):
    """Test that agent correctly calculates days_old for scoring."""
    published_time = datetime.utcnow() - timedelta(days=3)
    mock_paper = MagicMock()
    mock_paper.published = published_time
    mock_fetch_papers.return_value = [mock_paper]

    metadata = PaperMetadata(
        paper_id="days_test",
        source="arxiv",
        title="Days Test",
        authors="Author",
        abstract="Abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )
    mock_parse_metadata.return_value = metadata

    mock_impl_score.return_value = 80.0
    mock_strat_value.return_value = 80.0
    mock_overall_score.return_value = 80.0
    mock_maint_relevance.return_value = 80.0
    mock_tag_types.return_value = ["test"]
    mock_add_record.return_value = MagicMock()

    agent.run(search_queries=["test"])

    # Verify maintainer_relevance_score was called with correct days_old
    mock_maint_relevance.assert_called_once()
    call_args = mock_maint_relevance.call_args
    # Should be 3 days old (approximately)
    assert 2 <= call_args[0][2] <= 4  # days_old parameter


@patch("agents.maintainer_researcher.agent.fetch_arxiv_papers")
@patch("agents.maintainer_researcher.agent.parse_paper_metadata")
@patch("agents.maintainer_researcher.agent.calculate_implementability_score")
@patch("agents.maintainer_researcher.agent.calculate_strategic_value_score")
@patch("agents.maintainer_researcher.agent.calculate_maintainer_relevance_score")
@patch("agents.maintainer_researcher.agent.calculate_overall_score")
@patch("agents.maintainer_researcher.agent.tag_issue_types")
@patch("agents.maintainer_researcher.agent.create_draft_github_issue")
@patch("agents.maintainer_researcher.agent.add_research_record")
def test_agent_returns_structured_results(
    mock_add_record,
    mock_create_issue,
    mock_tag_types,
    mock_overall_score,
    mock_maint_relevance,
    mock_strat_value,
    mock_impl_score,
    mock_parse_metadata,
    mock_fetch_papers,
    agent,
    mock_session
):
    """Test that agent returns properly structured results dictionary."""
    mock_paper = MagicMock()
    mock_paper.published = datetime.utcnow() - timedelta(days=1)
    mock_fetch_papers.return_value = [mock_paper]

    metadata = PaperMetadata(
        paper_id="results_test",
        source="arxiv",
        title="Results Test",
        authors="Author",
        abstract="Abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1)
    )
    mock_parse_metadata.return_value = metadata

    mock_impl_score.return_value = 80.0
    mock_strat_value.return_value = 80.0
    mock_maint_relevance.return_value = 80.0
    mock_overall_score.return_value = 80.0
    mock_tag_types.return_value = ["test"]
    mock_create_issue.return_value = {"title": "Test"}
    mock_add_record.return_value = MagicMock()

    results = agent.run(search_queries=["test"])

    # Verify structure
    assert isinstance(results, dict)
    assert "papers_fetched" in results
    assert "papers_scored" in results
    assert "draft_issues_created" in results
    assert "research_records_saved" in results
    assert "errors" in results

    # Verify types
    assert isinstance(results["papers_fetched"], int)
    assert isinstance(results["papers_scored"], int)
    assert isinstance(results["draft_issues_created"], int)
    assert isinstance(results["research_records_saved"], int)
    assert isinstance(results["errors"], list)
