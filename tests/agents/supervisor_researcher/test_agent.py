"""
Test suite for SupervisorResearcherAgent with orchestration and scheduling.
Tests follow TDD: test first, implement after.
"""
import pytest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch
from agents.supervisor_researcher.agent import SupervisorResearcherAgent
from agents.supervisor_researcher.models import PaperMetadata
import arxiv


class MockArxivResult:
    """Mock arxiv.Result object for testing."""
    def __init__(self, title="Test Paper", summary="Test summary",
                 paper_id="2024.00001", published=None):
        self.title = title
        self.summary = summary
        self.entry_id = f"http://arxiv.org/abs/{paper_id}v1"
        self.published = published or datetime(2024, 3, 15)
        self.pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        self.authors = [Mock(name="Test Author")]


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def supervisor_agent(mock_session):
    """Create SupervisorResearcherAgent with mock session."""
    return SupervisorResearcherAgent(session=mock_session)


# =============================================================================
# TEST: Agent runs with search queries
# =============================================================================

def test_supervisor_researcher_agent_runs():
    """Test that agent.run() executes with 2 queries and returns results dict."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    # Mock fetch_arxiv_papers to return empty list
    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.return_value = []

        results = agent.run(
            search_queries=["quant momentum trading", "mean reversion"],
            max_papers=50,
            min_confidence=60.0
        )

    # Assert results dict structure
    assert isinstance(results, dict)
    assert 'papers_fetched' in results
    assert 'papers_scored' in results
    assert 'draft_signals_created' in results
    assert 'research_records_saved' in results
    assert 'errors' in results
    assert results['papers_fetched'] == 0


def test_supervisor_researcher_agent_fetches_papers():
    """Test that agent fetches papers from arxiv for each query."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    # Create mock papers
    mock_paper_1 = MockArxivResult(
        title="Momentum Trading with ML",
        summary="Machine learning for momentum trading",
        paper_id="2024.00001",
        published=datetime(2024, 3, 15)
    )
    mock_paper_2 = MockArxivResult(
        title="Mean Reversion Detection",
        summary="Using statistical methods for mean reversion",
        paper_id="2024.00002",
        published=datetime(2024, 3, 14)
    )

    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.side_effect = [[mock_paper_1], [mock_paper_2]]

        with patch('agents.supervisor_researcher.agent.parse_paper_metadata') as mock_parse:
            mock_parse.side_effect = [
                PaperMetadata(
                    paper_id="2024.00001",
                    source="arxiv",
                    title="Momentum Trading with ML",
                    authors="Author A",
                    abstract="ML momentum",
                    url="http://arxiv.org/abs/2024.00001",
                    publication_date=date(2024, 3, 15)
                ),
                PaperMetadata(
                    paper_id="2024.00002",
                    source="arxiv",
                    title="Mean Reversion Detection",
                    authors="Author B",
                    abstract="Mean reversion",
                    url="http://arxiv.org/abs/2024.00002",
                    publication_date=date(2024, 3, 14)
                )
            ]

            with patch('agents.supervisor_researcher.agent.calculate_relevance_score') as mock_rel:
                mock_rel.return_value = 75.0

                with patch('agents.supervisor_researcher.agent.calculate_academic_score') as mock_acad:
                    mock_acad.return_value = 70.0

                    with patch('agents.supervisor_researcher.agent.calculate_confidence_score') as mock_conf:
                        mock_conf.return_value = 72.5

                        with patch('agents.supervisor_researcher.agent.tag_strategies') as mock_tags:
                            mock_tags.return_value = ["momentum"]

                            with patch('agents.supervisor_researcher.agent.add_research_record') as mock_add_record:
                                mock_add_record.return_value = MagicMock(id=1)

                                results = agent.run(
                                    search_queries=["quant momentum", "mean reversion"],
                                    max_papers=50,
                                    min_confidence=60.0
                                )

    assert results['papers_fetched'] == 2
    assert mock_fetch.call_count == 2


def test_supervisor_researcher_agent_scores_papers():
    """Test that agent calculates relevance, academic, and confidence scores."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    mock_paper = MockArxivResult(
        title="Advanced Momentum Strategies",
        summary="Using machine learning for momentum trading signals",
        paper_id="2024.00001",
        published=datetime(2024, 3, 15)
    )

    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.return_value = [mock_paper]

        with patch('agents.supervisor_researcher.agent.parse_paper_metadata') as mock_parse:
            mock_parse.return_value = PaperMetadata(
                paper_id="2024.00001",
                source="arxiv",
                title="Advanced Momentum Strategies",
                authors="Test Author",
                abstract="ML momentum",
                url="http://arxiv.org/abs/2024.00001",
                publication_date=date(2024, 3, 15)
            )

            with patch('agents.supervisor_researcher.agent.calculate_relevance_score') as mock_rel:
                mock_rel.return_value = 85.0

                with patch('agents.supervisor_researcher.agent.calculate_academic_score') as mock_acad:
                    mock_acad.return_value = 80.0

                    with patch('agents.supervisor_researcher.agent.calculate_confidence_score') as mock_conf:
                        mock_conf.return_value = 82.5

                        with patch('agents.supervisor_researcher.agent.tag_strategies') as mock_tags:
                            mock_tags.return_value = ["momentum", "ml"]

                            with patch('agents.supervisor_researcher.agent.add_research_record') as mock_add:
                                mock_add.return_value = MagicMock(id=1)

                                results = agent.run(
                                    search_queries=["momentum"],
                                    max_papers=50,
                                    min_confidence=60.0
                                )

    assert results['papers_scored'] == 1
    mock_rel.assert_called_once()
    mock_acad.assert_called_once()
    mock_conf.assert_called_once()


# =============================================================================
# TEST: Agent creates research records in database
# =============================================================================

def test_agent_creates_research_records():
    """Test that agent saves research records to database when confidence > threshold."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    mock_paper = MockArxivResult(
        title="High Confidence Research Paper",
        summary="This is a high quality paper",
        paper_id="2024.00001",
        published=datetime(2024, 3, 15)
    )

    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.return_value = [mock_paper]

        with patch('agents.supervisor_researcher.agent.parse_paper_metadata') as mock_parse:
            mock_parse.return_value = PaperMetadata(
                paper_id="2024.00001",
                source="arxiv",
                title="High Confidence Research Paper",
                authors="Author A",
                abstract="High quality",
                url="http://arxiv.org/abs/2024.00001",
                publication_date=date(2024, 3, 15)
            )

            with patch('agents.supervisor_researcher.agent.calculate_relevance_score') as mock_rel:
                mock_rel.return_value = 85.0

                with patch('agents.supervisor_researcher.agent.calculate_academic_score') as mock_acad:
                    mock_acad.return_value = 80.0

                    with patch('agents.supervisor_researcher.agent.calculate_confidence_score') as mock_conf:
                        mock_conf.return_value = 82.5

                        with patch('agents.supervisor_researcher.agent.tag_strategies') as mock_tags:
                            mock_tags.return_value = ["momentum"]

                            with patch('agents.supervisor_researcher.agent.add_research_record') as mock_add_record:
                                mock_record = MagicMock(id=1)
                                mock_add_record.return_value = mock_record

                                results = agent.run(
                                    search_queries=["test"],
                                    max_papers=50,
                                    min_confidence=60.0
                                )

    assert results['research_records_saved'] >= 1
    mock_add_record.assert_called()


def test_agent_respects_confidence_threshold():
    """Test that agent only saves records when confidence >= min_confidence."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    # Paper 1: High confidence (will be saved)
    paper_high = MockArxivResult(
        title="High Confidence Paper",
        summary="Test",
        paper_id="2024.00001",
        published=datetime(2024, 3, 15)
    )

    # Paper 2: Low confidence (will NOT be saved)
    paper_low = MockArxivResult(
        title="Low Confidence Paper",
        summary="Test",
        paper_id="2024.00002",
        published=datetime(2024, 3, 15)
    )

    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.return_value = [paper_high, paper_low]

        with patch('agents.supervisor_researcher.agent.parse_paper_metadata') as mock_parse:
            mock_parse.side_effect = [
                PaperMetadata(
                    paper_id="2024.00001",
                    source="arxiv",
                    title="High Confidence Paper",
                    authors="Author A",
                    abstract="High",
                    url="http://arxiv.org/abs/2024.00001",
                    publication_date=date(2024, 3, 15)
                ),
                PaperMetadata(
                    paper_id="2024.00002",
                    source="arxiv",
                    title="Low Confidence Paper",
                    authors="Author B",
                    abstract="Low",
                    url="http://arxiv.org/abs/2024.00002",
                    publication_date=date(2024, 3, 15)
                )
            ]

            with patch('agents.supervisor_researcher.agent.calculate_relevance_score') as mock_rel:
                mock_rel.side_effect = [80.0, 40.0]

                with patch('agents.supervisor_researcher.agent.calculate_academic_score') as mock_acad:
                    mock_acad.side_effect = [75.0, 50.0]

                    with patch('agents.supervisor_researcher.agent.calculate_confidence_score') as mock_conf:
                        # High confidence = 77.5, Low confidence = 45.0
                        mock_conf.side_effect = [77.5, 45.0]

                        with patch('agents.supervisor_researcher.agent.tag_strategies') as mock_tags:
                            mock_tags.return_value = ["momentum"]

                            with patch('agents.supervisor_researcher.agent.add_research_record') as mock_add:
                                mock_add.return_value = MagicMock(id=1)

                                results = agent.run(
                                    search_queries=["test"],
                                    max_papers=50,
                                    min_confidence=60.0  # Only papers >= 60 saved
                                )

    assert results['research_records_saved'] == 1  # Only high confidence paper saved
    assert results['papers_scored'] == 2  # But both were scored
    mock_add.assert_called_once()


def test_agent_creates_draft_signals_for_high_confidence():
    """Test that agent creates draft signals when confidence >= min_confidence."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    mock_paper = MockArxivResult(
        title="Momentum Trading Paper",
        summary="Machine learning momentum strategies",
        paper_id="2024.00001",
        published=datetime(2024, 3, 15)
    )

    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.return_value = [mock_paper]

        with patch('agents.supervisor_researcher.agent.parse_paper_metadata') as mock_parse:
            mock_parse.return_value = PaperMetadata(
                paper_id="2024.00001",
                source="arxiv",
                title="Momentum Trading Paper",
                authors="Author A",
                abstract="ML momentum",
                url="http://arxiv.org/abs/2024.00001",
                publication_date=date(2024, 3, 15)
            )

            with patch('agents.supervisor_researcher.agent.calculate_relevance_score') as mock_rel:
                mock_rel.return_value = 85.0

                with patch('agents.supervisor_researcher.agent.calculate_academic_score') as mock_acad:
                    mock_acad.return_value = 80.0

                    with patch('agents.supervisor_researcher.agent.calculate_confidence_score') as mock_conf:
                        mock_conf.return_value = 82.5

                        with patch('agents.supervisor_researcher.agent.tag_strategies') as mock_tags:
                            mock_tags.return_value = ["momentum"]

                            with patch('agents.supervisor_researcher.agent.create_draft_signal') as mock_signal:
                                mock_signal.return_value = {
                                    "paper_id": "2024.00001",
                                    "direction": "BUY",
                                    "confidence": 82.5
                                }

                                with patch('agents.supervisor_researcher.agent.add_research_record') as mock_add:
                                    mock_add.return_value = MagicMock(id=1)

                                    results = agent.run(
                                        search_queries=["momentum"],
                                        max_papers=50,
                                        min_confidence=60.0
                                    )

    assert results['draft_signals_created'] >= 1
    mock_signal.assert_called()


def test_agent_handles_errors_gracefully():
    """Test that agent continues processing on errors and logs them."""
    mock_session = MagicMock()
    agent = SupervisorResearcherAgent(session=mock_session)

    with patch('agents.supervisor_researcher.agent.fetch_arxiv_papers') as mock_fetch:
        mock_fetch.side_effect = Exception("API Error")

        results = agent.run(
            search_queries=["test"],
            max_papers=50,
            min_confidence=60.0
        )

    assert 'errors' in results
    assert len(results['errors']) >= 1


# =============================================================================
# TEST: APScheduler integration
# =============================================================================

def test_scheduler_starts():
    """Test that APScheduler starts and job is scheduled."""
    from agents.supervisor_researcher.main import start_scheduler, stop_scheduler, scheduler

    # Clear any existing jobs
    for job in scheduler.get_jobs():
        job.remove()

    # Start scheduler
    start_scheduler()

    # Assert scheduler is running
    assert scheduler.running is True

    # Assert job exists
    jobs = scheduler.get_jobs()
    assert len(jobs) >= 1

    # Find our job
    researcher_job = None
    for job in jobs:
        if job.id == 'supervisor_researcher_daily':
            researcher_job = job
            break

    assert researcher_job is not None
    assert researcher_job.trigger is not None

    # Stop scheduler
    stop_scheduler()
    assert scheduler.running is False


def test_scheduler_runs_daily_at_6am():
    """Test that scheduler job is set to run daily at 6 AM UTC."""
    from agents.supervisor_researcher.main import start_scheduler, stop_scheduler, scheduler

    # Clear existing jobs
    for job in scheduler.get_jobs():
        job.remove()

    start_scheduler()

    # Find researcher job
    researcher_job = None
    for job in scheduler.get_jobs():
        if job.id == 'supervisor_researcher_daily':
            researcher_job = job
            break

    assert researcher_job is not None

    # Check trigger is cron
    from apscheduler.triggers.cron import CronTrigger
    assert isinstance(researcher_job.trigger, CronTrigger)

    stop_scheduler()


def test_run_researcher_job_executes_agent():
    """Test that run_researcher_job executes the supervisor researcher agent."""
    from agents.supervisor_researcher.main import run_researcher_job
    from unittest.mock import patch, MagicMock

    with patch('agents.supervisor_researcher.main.SessionLocal') as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with patch('agents.supervisor_researcher.main.SupervisorResearcherAgent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.run.return_value = {
                'papers_fetched': 10,
                'papers_scored': 10,
                'draft_signals_created': 3,
                'research_records_saved': 3,
                'errors': []
            }
            mock_agent_class.return_value = mock_agent

            result = run_researcher_job()

    assert isinstance(result, dict)
    assert 'papers_fetched' in result
    mock_session.close.assert_called_once()


def test_scheduler_stops():
    """Test that scheduler can be stopped."""
    from agents.supervisor_researcher.main import start_scheduler, stop_scheduler, scheduler

    # Clear existing jobs
    for job in scheduler.get_jobs():
        job.remove()

    start_scheduler()
    assert scheduler.running is True

    stop_scheduler()
    assert scheduler.running is False
