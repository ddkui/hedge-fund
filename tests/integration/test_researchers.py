"""
Integration tests for researcher endpoints and jobs.
Tests the complete research workflow from API to database.
"""
import pytest
from datetime import datetime, date
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from shared.academic_research import Base as AcademicBase, AcademicResearch, add_research_record
from shared.system_improvements import Base as ImprovementsBase, SystemImprovement, add_improvement_record


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create tables
    AcademicBase.metadata.create_all(engine)
    ImprovementsBase.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield SessionLocal()


def test_get_research_papers_empty(test_db):
    """Test GET /api/research/papers returns empty list when no papers exist."""
    from gateway.routers.research import get_research_papers

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_research_papers(skip=0, limit=10)

        assert result["count"] == 0
        assert result["papers"] == []
        assert result["skip"] == 0
        assert result["limit"] == 10


def test_get_research_papers_with_data(test_db):
    """Test GET /api/research/papers returns papers from database."""
    from gateway.routers.research import get_research_papers

    # Add test paper
    add_research_record(
        session=test_db,
        source="arxiv",
        paper_id="test_001",
        title="Test Paper Title",
        authors="Test Author",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 6, 1),
        relevance_score=80.0,
        academic_score=75.0,
        confidence_score=77.5
    )

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_research_papers(skip=0, limit=10)

        assert result["count"] == 1
        assert len(result["papers"]) == 1
        assert result["papers"][0]["title"] == "Test Paper Title"
        assert result["papers"][0]["confidence_score"] == 77.5


def test_get_research_papers_pagination(test_db):
    """Test pagination of research papers."""
    from gateway.routers.research import get_research_papers

    # Add multiple papers
    for i in range(15):
        add_research_record(
            session=test_db,
            source="arxiv",
            paper_id=f"test_{i:03d}",
            title=f"Paper {i}",
            authors="Author",
            abstract="Abstract",
            url="https://example.com",
            publication_date=date(2024, 6, 1),
            relevance_score=50.0,
            academic_score=50.0,
            confidence_score=50.0
        )

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        # First page
        result1 = get_research_papers(skip=0, limit=10)
        assert result1["count"] == 10
        assert len(result1["papers"]) == 10

        # Second page
        result2 = get_research_papers(skip=10, limit=10)
        assert result2["count"] == 5
        assert len(result2["papers"]) == 5


def test_get_research_papers_limit_validation(test_db):
    """Test that limit is capped at 100."""
    from gateway.routers.research import get_research_papers

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        # Request with limit > 100
        result = get_research_papers(skip=0, limit=500)

        assert result["limit"] == 100


def test_get_system_improvements_empty(test_db):
    """Test GET /api/research/improvements returns empty list when none exist."""
    from gateway.routers.research import get_system_improvements

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_system_improvements(skip=0, limit=10)

        assert result["count"] == 0
        assert result["improvements"] == []


def test_get_system_improvements_with_data(test_db):
    """Test GET /api/research/improvements returns improvements from database."""
    from gateway.routers.research import get_system_improvements

    # Add test improvement
    add_improvement_record(
        session=test_db,
        source="arxiv",
        paper_id="imp_001",
        title="System Improvement Idea",
        authors="Researcher",
        abstract="Improvement abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1),
        impact_area="performance",
        impact_score=85.0,
        feasibility_score=75.0,
        academic_score=80.0,
        combined_score=80.0,
        implementation_idea="Implementation plan"
    )

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_system_improvements(skip=0, limit=10)

        assert result["count"] == 1
        assert len(result["improvements"]) == 1
        assert result["improvements"][0]["title"] == "System Improvement Idea"
        assert result["improvements"][0]["combined_score"] == 80.0


def test_get_system_improvements_sorted_by_score(test_db):
    """Test that improvements are sorted by combined score descending."""
    from gateway.routers.research import get_system_improvements

    # Add improvements with different scores
    for i, score in enumerate([50.0, 90.0, 70.0]):
        add_improvement_record(
            session=test_db,
            source="arxiv",
            paper_id=f"imp_{i:03d}",
            title=f"Improvement {i}",
            authors="Author",
            abstract="Abstract",
            url="https://example.com",
            publication_date=date(2024, 6, 1),
            impact_area="performance",
            impact_score=score,
            feasibility_score=score,
            academic_score=score,
            combined_score=score,
            implementation_idea="Idea"
        )

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_system_improvements(skip=0, limit=10)

        # Should be sorted highest first
        assert result["improvements"][0]["combined_score"] == 90.0
        assert result["improvements"][1]["combined_score"] == 70.0
        assert result["improvements"][2]["combined_score"] == 50.0


@patch("gateway.routers.research.run_researcher_job")
def test_run_supervisor_researcher_success(mock_run_job):
    """Test POST /api/research/run-supervisor triggers job successfully."""
    from gateway.routers.research import run_supervisor_researcher

    mock_run_job.return_value = {
        "papers_fetched": 10,
        "signals_generated": 5,
        "errors": []
    }

    with patch("gateway.routers.research.run_researcher_job", mock_run_job):
        result = run_supervisor_researcher()

        assert result["status"] == "success"
        assert result["job"] == "supervisor_researcher"
        assert result["results"]["papers_fetched"] == 10
        assert result["results"]["signals_generated"] == 5


@patch("gateway.routers.research.run_researcher_job")
def test_run_supervisor_researcher_error(mock_run_job):
    """Test POST /api/research/run-supervisor handles errors gracefully."""
    from gateway.routers.research import run_supervisor_researcher

    mock_run_job.side_effect = Exception("Database connection failed")

    with patch("gateway.routers.research.run_researcher_job", mock_run_job):
        result = run_supervisor_researcher()

        assert result["status"] == "error"
        assert result["job"] == "supervisor_researcher"
        assert "Database connection failed" in result["error"]


@patch("gateway.routers.research.run_researcher_job")
def test_run_maintainer_researcher_success(mock_run_job):
    """Test POST /api/research/run-maintainer triggers job successfully."""
    from gateway.routers.research import run_maintainer_researcher

    mock_run_job.return_value = {
        "papers_fetched": 50,
        "draft_issues_created": 8,
        "errors": []
    }

    with patch("gateway.routers.research.run_researcher_job", mock_run_job):
        result = run_maintainer_researcher()

        assert result["status"] == "success"
        assert result["job"] == "maintainer_researcher"
        assert result["results"]["papers_fetched"] == 50
        assert result["results"]["draft_issues_created"] == 8


def test_run_maintainer_researcher_module_import():
    """Test that maintainer researcher can be imported from main."""
    try:
        from agents.maintainer_researcher.main import run_researcher_job
        assert callable(run_researcher_job)
    except ImportError as e:
        pytest.fail(f"Failed to import run_researcher_job: {e}")


def test_get_research_stats_empty(test_db):
    """Test GET /api/research/stats with empty database."""
    from gateway.routers.research import get_research_stats

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_research_stats()

        assert result["papers_count"] == 0
        assert result["improvements_count"] == 0
        assert result["top_paper"] is None
        assert result["top_improvement"] is None


def test_get_research_stats_with_data(test_db):
    """Test GET /api/research/stats returns correct counts and top items."""
    from gateway.routers.research import get_research_stats

    # Add papers
    add_research_record(
        session=test_db,
        source="arxiv",
        paper_id="p1",
        title="High Score Paper",
        authors="Author",
        abstract="Abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1),
        relevance_score=95.0,
        academic_score=90.0,
        confidence_score=95.0
    )

    # Add improvement
    add_improvement_record(
        session=test_db,
        source="arxiv",
        paper_id="i1",
        title="High Score Improvement",
        authors="Author",
        abstract="Abstract",
        url="https://example.com",
        publication_date=date(2024, 6, 1),
        impact_area="performance",
        impact_score=90.0,
        feasibility_score=85.0,
        academic_score=88.0,
        combined_score=88.0,
        implementation_idea="Idea"
    )

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        result = get_research_stats()

        assert result["papers_count"] == 1
        assert result["improvements_count"] == 1
        assert result["top_paper"]["title"] == "High Score Paper"
        assert result["top_paper"]["score"] == 95.0
        assert result["top_improvement"]["title"] == "High Score Improvement"
        assert result["top_improvement"]["score"] == 88.0


def test_api_endpoint_response_structure(test_db):
    """Test that API responses follow consistent structure."""
    from gateway.routers.research import get_research_papers, get_system_improvements

    with patch("gateway.routers.research.SessionLocal") as mock_session_local:
        mock_session_local.return_value = test_db

        papers_result = get_research_papers(skip=0, limit=10)
        improvements_result = get_system_improvements(skip=0, limit=10)

        # Validate papers response structure
        assert "count" in papers_result
        assert "skip" in papers_result
        assert "limit" in papers_result
        assert "papers" in papers_result
        assert isinstance(papers_result["papers"], list)

        # Validate improvements response structure
        assert "count" in improvements_result
        assert "skip" in improvements_result
        assert "limit" in improvements_result
        assert "improvements" in improvements_result
        assert isinstance(improvements_result["improvements"], list)
