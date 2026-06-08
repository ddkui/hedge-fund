from pydantic import BaseModel
from datetime import date

class PaperMetadata(BaseModel):
    """Standardized paper metadata."""
    paper_id: str
    source: str
    title: str
    authors: str
    abstract: str
    url: str
    publication_date: date

class ScoredPaper(BaseModel):
    """Paper with implementation and maintainer relevance scores."""
    metadata: PaperMetadata
    implementability_score: float
    strategic_value_score: float
    maintainer_relevance_score: float
    overall_score: float
    suggested_issue_tags: str
