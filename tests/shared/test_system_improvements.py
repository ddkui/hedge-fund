import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from shared.system_improvements import SystemImprovement, add_improvement_record, Base

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

def test_add_system_improvement_record(test_db_engine):
    """Test adding a system improvement record to database."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)

    with SessionLocal() as session:
        record = add_improvement_record(
            session=session,
            source="arxiv",
            paper_id="2405.54321",
            title="Low-Latency Order Execution Optimization",
            authors="Narang, A.",
            abstract="We propose VWAP improvements...",
            url="https://arxiv.org/abs/2405.54321",
            publication_date=datetime(2026, 5, 15).date(),
            impact_area="execution",
            impact_score=92.0,
            feasibility_score=88.0,
            academic_score=85.0,
            combined_score=88.3,
            implementation_idea="Implement Narang's VWAP algorithm with ML prediction"
        )

        assert record.id is not None
        assert record.impact_area == "execution"
        assert record.combined_score == 88.3
        assert record.slack_alert_sent is False
