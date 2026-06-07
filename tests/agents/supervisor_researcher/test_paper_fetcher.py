import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date
from agents.supervisor_researcher.paper_fetcher import (
    fetch_arxiv_papers,
    fetch_ssrn_papers,
    parse_paper_metadata,
)
from agents.supervisor_researcher.models import PaperMetadata


class TestFetchArxivPapers:
    """Test suite for arXiv paper fetching."""

    def test_fetch_arxiv_papers_returns_list(self):
        """Test that fetch_arxiv_papers returns a list."""
        with patch("agents.supervisor_researcher.paper_fetcher.arxiv.Client") as mock_client_class:
            # Mock the client and its search results
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create a mock result
            mock_result = MagicMock()
            mock_result.entry_id = "http://arxiv.org/abs/2024.00001v1"
            mock_result.title = "Test Paper"
            author1 = MagicMock()
            author1.name = "Author One"
            author2 = MagicMock()
            author2.name = "Author Two"
            mock_result.authors = [author1, author2]
            mock_result.summary = "Test abstract"
            mock_result.pdf_url = "https://arxiv.org/pdf/2024.00001v1.pdf"
            mock_result.published = datetime.utcnow()

            mock_client.results = MagicMock(return_value=[mock_result])

            # Call the function
            result = fetch_arxiv_papers("momentum strategies", max_results=10, days_back=30)

            # Assert result is a list
            assert isinstance(result, list)

    def test_fetch_arxiv_papers_filters_by_days(self):
        """Test that fetch_arxiv_papers filters papers by age."""
        with patch("agents.supervisor_researcher.paper_fetcher.arxiv.Client") as mock_client_class:
            with patch("agents.supervisor_researcher.paper_fetcher.datetime") as mock_datetime:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                # Set a fixed "current" time for testing
                current_time = datetime(2024, 6, 8, 12, 0, 0)
                mock_datetime.utcnow.return_value = current_time

                # Create old and new mock results
                old_result = MagicMock()
                old_result.entry_id = "http://arxiv.org/abs/2020.00001v1"
                old_result.published = datetime(2020, 1, 1)  # Very old

                new_result = MagicMock()
                new_result.entry_id = "http://arxiv.org/abs/2024.06.01v1"
                new_result.published = datetime(2024, 6, 1)  # 7 days old

                mock_client.results = MagicMock(return_value=[old_result, new_result])

                # Call with 7 days_back
                result = fetch_arxiv_papers("test", max_results=50, days_back=7)

                # Only the new result should be returned
                assert len(result) == 1
                assert result[0].entry_id == "http://arxiv.org/abs/2024.06.01v1"


class TestFetchSSRNPapers:
    """Test suite for SSRN paper fetching."""

    def test_fetch_ssrn_papers_returns_empty_list(self):
        """Test that fetch_ssrn_papers returns an empty list (API requires scraping)."""
        result = fetch_ssrn_papers(["momentum", "trading"], max_results=50)
        assert isinstance(result, list)
        assert len(result) == 0


class TestParsePaperMetadata:
    """Test suite for paper metadata parsing."""

    def test_parse_paper_metadata_arxiv(self):
        """Test parsing arXiv paper metadata."""
        # Create a mock arXiv paper
        mock_paper = MagicMock()
        mock_paper.entry_id = "http://arxiv.org/abs/2024.00001v1"
        mock_paper.title = "Advanced Momentum Strategies"

        # Create author objects with name attribute
        author1 = MagicMock()
        author1.name = "Smith, J."
        author2 = MagicMock()
        author2.name = "Doe, A."
        mock_paper.authors = [author1, author2]

        mock_paper.summary = "This paper explores momentum trading strategies."
        mock_paper.pdf_url = "https://arxiv.org/pdf/2024.00001v1.pdf"
        mock_paper.published = datetime(2024, 3, 15)

        # Parse the metadata
        result = parse_paper_metadata(mock_paper, source="arxiv")

        # Assert it's a PaperMetadata instance
        assert isinstance(result, PaperMetadata)

        # Assert the fields are correct
        assert result.paper_id == "2024.00001v1"
        assert result.source == "arxiv"
        assert result.title == "Advanced Momentum Strategies"
        assert "Smith, J." in result.authors
        assert "Doe, A." in result.authors
        assert result.abstract == "This paper explores momentum trading strategies."
        assert result.url == "https://arxiv.org/pdf/2024.00001v1.pdf"
        assert result.publication_date == date(2024, 3, 15)

    def test_parse_paper_metadata_ssrn(self):
        """Test parsing SSRN paper metadata."""
        # Create a mock SSRN paper (as a dict)
        mock_paper = {
            "id": "ssrn_4567890",
            "title": "Mean Reversion Detection Using Deep Learning",
            "authors": "Doe, A.; Smith, B.",
            "abstract": "A comprehensive study on mean reversion patterns.",
            "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4567890",
            "publication_date": date(2024, 1, 10),
        }

        # Parse the metadata
        result = parse_paper_metadata(mock_paper, source="ssrn")

        # Assert it's a PaperMetadata instance
        assert isinstance(result, PaperMetadata)

        # Assert the fields are correct
        assert result.paper_id == "ssrn_4567890"
        assert result.source == "ssrn"
        assert result.title == "Mean Reversion Detection Using Deep Learning"
        assert result.authors == "Doe, A.; Smith, B."
        assert result.abstract == "A comprehensive study on mean reversion patterns."
        assert result.url == "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4567890"
        assert result.publication_date == date(2024, 1, 10)

    def test_parse_paper_metadata_invalid_source(self):
        """Test that parsing with invalid source raises ValueError."""
        mock_paper = {}

        with pytest.raises(ValueError, match="Unknown source"):
            parse_paper_metadata(mock_paper, source="invalid_source")

    def test_parse_paper_metadata_arxiv_with_multiple_authors(self):
        """Test parsing arXiv paper with multiple authors."""
        mock_paper = MagicMock()
        mock_paper.entry_id = "http://arxiv.org/abs/2023.50000v1"
        mock_paper.title = "Machine Learning in Finance"
        # Create multiple author mocks
        author1 = MagicMock()
        author1.name = "Alice Smith"
        author2 = MagicMock()
        author2.name = "Bob Johnson"
        author3 = MagicMock()
        author3.name = "Charlie Brown"
        mock_paper.authors = [author1, author2, author3]
        mock_paper.summary = "A study on ML applications in finance."
        mock_paper.pdf_url = "https://arxiv.org/pdf/2023.50000v1.pdf"
        mock_paper.published = datetime(2023, 12, 1)

        result = parse_paper_metadata(mock_paper, source="arxiv")

        assert result.paper_id == "2023.50000v1"
        assert "Alice Smith" in result.authors
        assert "Bob Johnson" in result.authors
        assert "Charlie Brown" in result.authors
        assert result.publication_date == date(2023, 12, 1)
