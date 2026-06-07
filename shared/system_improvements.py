from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()

class SystemImprovement(Base):
    """System improvement idea from academic research."""
    __tablename__ = "system_improvements"

    id = Column(Integer, primary_key=True)
    date_discovered = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), nullable=False)
    paper_id = Column(String(100), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=False)
    abstract = Column(Text, nullable=False)
    url = Column(String(500), nullable=False)
    publication_date = Column(Date, nullable=False)
    impact_area = Column(String(50), nullable=False)
    impact_score = Column(Float, nullable=False)
    feasibility_score = Column(Float, nullable=False)
    academic_score = Column(Float, nullable=False)
    combined_score = Column(Float, nullable=False)
    implementation_idea = Column(Text, nullable=False)
    github_issue_created = Column(Integer)
    issue_title = Column(String(500))
    slack_alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def add_improvement_record(
    session: Session,
    source: str,
    paper_id: str,
    title: str,
    authors: str,
    abstract: str,
    url: str,
    publication_date: date,
    impact_area: str,
    impact_score: float,
    feasibility_score: float,
    academic_score: float,
    combined_score: float,
    implementation_idea: str,
    github_issue_created: int = None,
    issue_title: str = None
) -> SystemImprovement:
    """Add a system improvement record to the database."""
    record = SystemImprovement(
        source=source,
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        publication_date=publication_date,
        impact_area=impact_area,
        impact_score=impact_score,
        feasibility_score=feasibility_score,
        academic_score=academic_score,
        combined_score=combined_score,
        implementation_idea=implementation_idea,
        github_issue_created=github_issue_created,
        issue_title=issue_title
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record

def mark_slack_alert_sent(session: Session, record_id: int) -> SystemImprovement:
    """Mark that Slack alert was sent for this record."""
    record = session.query(SystemImprovement).filter_by(id=record_id).first()
    if record:
        record.slack_alert_sent = True
        session.commit()
        session.refresh(record)
    return record
