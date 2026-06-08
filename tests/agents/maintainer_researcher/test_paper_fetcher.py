from datetime import datetime, date, timedelta
import pytest
from unittest.mock import MagicMock, patch
from agents.maintainer_researcher.paper_fetcher import (
    fetch_arxiv_papers,
    fetch_ssrn_papers,
    parse_paper_metadata
)
from agents.maintainer_researcher.models import PaperMetadata


def test_parse_paper_metadata_arxiv():
    """Test parsing arXiv paper metadata."""
    mock_paper = MagicMock()
    mock_paper.entry_id = "http://arxiv.org/abs/2024.00001v1"
    mock_paper.title = "Test Paper Title"
    mock_paper.authors = [
        MagicMock(name="John Smith"),
        MagicMock(name="Jane Doe")
    ]
    mock_paper.summary = "Test abstract content"
    mock_paper.pdf_url = "https://arxiv.org/pdf/2024.00001v1.pdf"
    mock_paper.published = datetime(2024, 6, 1)

    metadata = parse_paper_metadata(mock_paper, source="arxiv")

    assert metadata.paper_id == "2024.00001v1"
    assert metadata.source == "arxiv"
    assert metadata.title == "Test Paper Title"
    assert "John Smith" in metadata.authors
    assert "Jane Doe" in metadata.authors
    assert metadata.abstract == "Test abstract content"
    assert metadata.url == "https://arxiv.org/pdf/2024.00001v1.pdf"
    assert metadata.publication_date == date(2024, 6, 1)


def test_parse_paper_metadata_ssrn():
    """Test parsing SSRN paper metadata."""
    paper_dict = {
        "id": "ssrn_123456",
        "title": "SSRN Paper Title",
        "authors": "Author A, Author B",
        "abstract": "SSRN abstract",
        "url": "https://papers.ssrn.com/sol3/papers.cfm",
        "publication_date": date(2024, 5, 15)
    }

    metadata = parse_paper_metadata(paper_dict, source="ssrn")

    assert metadata.paper_id == "ssrn_123456"
    assert metadata.source == "ssrn"
    assert metadata.title == "SSRN Paper Title"
    assert metadata.authors == "Author A, Author B"
    assert metadata.abstract == "SSRN abstract"
    assert metadata.url == "https://papers.ssrn.com/sol3/papers.cfm"
    assert metadata.publication_date == date(2024, 5, 15)


def test_parse_paper_metadata_invalid_source():
    """Test parsing with invalid source raises ValueError."""
    paper_dict = {"id": "test"}
    with pytest.raises(ValueError):
        parse_paper_metadata(paper_dict, source="unknown_source")


@patch("agents.maintainer_researcher.paper_fetcher.arxiv.Client")
@patch("agents.maintainer_researcher.paper_fetcher.arxiv.Search")
def test_fetch_arxiv_papers_success(mock_search, mock_client):
    """Test successfully fetching arXiv papers."""
    # Mock paper results
    mock_paper1 = MagicMock()
    mock_paper1.entry_id = "http://arxiv.org/abs/2024.00001v1"
    mock_paper1.published = datetime.utcnow() - timedelta(days=2)

    mock_paper2 = MagicMock()
    mock_paper2.entry_id = "http://arxiv.org/abs/2024.00002v1"
    mock_paper2.published = datetime.utcnow() - timedelta(days=5)

    # Old paper should be filtered out
    mock_paper3 = MagicMock()
    mock_paper3.entry_id = "http://arxiv.org/abs/2024.00003v1"
    mock_paper3.published = datetime.utcnow() - timedelta(days=10)

    mock_client_instance = MagicMock()
    mock_client_instance.results.return_value = [mock_paper1, mock_paper2, mock_paper3]
    mock_client.return_value = mock_client_instance

    papers = fetch_arxiv_papers(search_query="consensus algorithm", max_results=50, days_back=7)

    # Should filter out papers older than 7 days
    assert len(papers) == 2
    assert mock_paper1 in papers
    assert mock_paper2 in papers
    assert mock_paper3 not in papers


@patch("agents.maintainer_researcher.paper_fetcher.arxiv.Client")
@patch("agents.maintainer_researcher.paper_fetcher.arxiv.Search")
def test_fetch_arxiv_papers_empty_results(mock_search, mock_client):
    """Test fetching arXiv papers with no results."""
    mock_client_instance = MagicMock()
    mock_client_instance.results.return_value = []
    mock_client.return_value = mock_client_instance

    papers = fetch_arxiv_papers(search_query="nonexistent", max_results=50)

    assert papers == []


def test_fetch_ssrn_papers_returns_empty():
    """Test that fetch_ssrn_papers returns empty list (stub implementation)."""
    papers = fetch_ssrn_papers(search_keywords=["test"], max_results=50)
    assert papers == []
    assert isinstance(papers, list)


def test_fetch_arxiv_papers_with_category_filters():
    """Test that arxiv queries include category filters."""
    with patch("agents.maintainer_researcher.paper_fetcher.arxiv.Client") as mock_client:
        with patch("agents.maintainer_researcher.paper_fetcher.arxiv.Search") as mock_search:
            mock_client_instance = MagicMock()
            mock_client_instance.results.return_value = []
            mock_client.return_value = mock_client_instance

            fetch_arxiv_papers(search_query="test", max_results=50, days_back=7)

            # Verify Search was called with proper query including category filters
            mock_search.assert_called_once()
            call_args = mock_search.call_args
            query_arg = call_args[1]["query"]
            assert "test" in query_arg
            assert "cat:cs.SE" in query_arg or "cat:cs.AI" in query_arg
