import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from shared.academic_research import AcademicResearch, add_research_record
from gateway.database import Base, engine

def test_add_academic_research_record():
    """Test adding an academic research record to database."""
    Base.metadata.create_all(engine)

    with Session(engine) as session:
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
