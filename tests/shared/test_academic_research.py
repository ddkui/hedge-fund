import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from shared.academic_research import AcademicResearch, add_research_record, Base

@pytest.fixture
def test_db_engine():
    """Create a test in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine

def test_add_academic_research_record(test_db_engine):
    """Test adding an academic research record to database."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)

    with SessionLocal() as session:
        record = add_research_record(
            session=session,
            source="arxiv",
            paper_id="2406.12345",
            title="Machine Learning for Momentum Trading",
            authors="Smith, J.; Jones, K.",
            abstract="We propose a deep learning approach...",
            url="https://arxiv.org/abs/2406.12345",
            publication_date=datetime(2026, 6, 7).date(),
            relevance_score=82.5,
            academic_score=78.0,
            confidence_score=80.3,
            strategy_tags="momentum,ml",
            generated_signal_id=None
        )

        assert record.id is not None
        assert record.source == "arxiv"
        assert record.relevance_score == 82.5
        assert record.slack_alert_sent is False
