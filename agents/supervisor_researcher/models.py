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
    """Paper with relevance and academic scores."""
    metadata: PaperMetadata
    relevance_score: float
    academic_score: float
    confidence_score: float
    strategy_tags: str
