from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()

class AcademicResearch(Base):
    """Academic research paper record with scoring and signal generation."""
    __tablename__ = "academic_research"

    id = Column(Integer, primary_key=True)
    date_discovered = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), nullable=False)
    paper_id = Column(String(100), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=False)
    abstract = Column(Text, nullable=False)
    url = Column(String(500), nullable=False)
    publication_date = Column(Date, nullable=False)
    relevance_score = Column(Float, nullable=False)
    academic_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    strategy_tags = Column(String(200))
    generated_signal_id = Column(Integer)
    slack_alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def add_research_record(
    session: Session,
    source: str,
    paper_id: str,
    title: str,
    authors: str,
    abstract: str,
    url: str,
    publication_date: date,
    relevance_score: float,
    academic_score: float,
    confidence_score: float,
    strategy_tags: str = None,
    generated_signal_id: int = None
) -> AcademicResearch:
    """Add a research record to the database."""
    record = AcademicResearch(
        source=source,
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        publication_date=publication_date,
        relevance_score=relevance_score,
        academic_score=academic_score,
        confidence_score=confidence_score,
        strategy_tags=strategy_tags,
        generated_signal_id=generated_signal_id
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record

def mark_slack_alert_sent(session: Session, record_id: int) -> AcademicResearch:
    """Mark that Slack alert was sent for this record."""
    record = session.query(AcademicResearch).filter_by(id=record_id).first()
    if record:
        record.slack_alert_sent = True
        session.commit()
        session.refresh(record)
    return record
