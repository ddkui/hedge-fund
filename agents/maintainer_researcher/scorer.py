import numpy as np
from typing import Dict, List
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer('all-MiniLM-L6-v2')

IMPLEMENTABILITY_KEYWORDS = {
    "algorithm": ["algorithm", "implementation", "efficient", "code", "pseudocode"],
    "architecture": ["architecture", "design", "pattern", "framework"],
    "performance": ["performance", "optimization", "scalability", "throughput"],
    "reliability": ["reliability", "fault tolerance", "resilience", "distributed"],
}

STRATEGIC_KEYWORDS = {
    "hedge_operations": ["automated trading", "execution", "order routing"],
    "risk_management": ["risk management", "portfolio optimization", "hedging"],
    "data_processing": ["data pipeline", "processing", "streaming", "latency"],
    "machine_learning": ["machine learning", "prediction", "forecasting"],
}


def calculate_implementability_score(
    paper_title: str,
    paper_abstract: str
) -> float:
    """Calculate implementability score (0-100) based on practical content."""
    paper_text = f"{paper_title}. {paper_abstract}"
    paper_embedding = model.encode(paper_text)

    max_similarity = 0.0
    for keywords in IMPLEMENTABILITY_KEYWORDS.values():
        for keyword in keywords:
            keyword_embedding = model.encode(keyword)
            similarity = cosine_similarity([paper_embedding], [keyword_embedding])[0][0]
            max_similarity = max(max_similarity, similarity)

    return float(min(100, max_similarity * 100))


def calculate_strategic_value_score(
    paper_title: str,
    paper_abstract: str
) -> float:
    """Calculate strategic value score (0-100) for hedge fund operations."""
    paper_text = f"{paper_title}. {paper_abstract}"
    paper_embedding = model.encode(paper_text)

    max_similarity = 0.0
    for keywords in STRATEGIC_KEYWORDS.values():
        for keyword in keywords:
            keyword_embedding = model.encode(keyword)
            similarity = cosine_similarity([paper_embedding], [keyword_embedding])[0][0]
            max_similarity = max(max_similarity, similarity)

    return float(min(100, max_similarity * 100))


def calculate_maintainer_relevance_score(
    paper_title: str,
    paper_abstract: str,
    days_old: int
) -> float:
    """Calculate maintainer relevance score: 0.6*recency + 0.4*implementability."""
    recency_score = max(0, (7 - days_old) / 7 * 100)

    paper_text = f"{paper_title}. {paper_abstract}"
    paper_embedding = model.encode(paper_text)
    impl_keywords = [kw for keywords in IMPLEMENTABILITY_KEYWORDS.values() for kw in keywords]

    impl_similarities = []
    for keyword in impl_keywords[:5]:
        keyword_embedding = model.encode(keyword)
        similarity = cosine_similarity([paper_embedding], [keyword_embedding])[0][0]
        impl_similarities.append(similarity)

    impl_score = max(impl_similarities) * 100 if impl_similarities else 0

    relevance = (0.6 * recency_score) + (0.4 * impl_score)
    return float(min(100, max(0, relevance)))


def tag_issue_types(paper_abstract: str) -> List[str]:
    """Auto-tag paper with suggested GitHub issue types."""
    abstract_lower = paper_abstract.lower()
    tags = []

    for issue_type, keywords in IMPLEMENTABILITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in abstract_lower:
                tags.append(issue_type)
                break

    return tags if tags else ["investigation"]


def calculate_overall_score(
    implementability: float,
    strategic_value: float,
    maintainer_relevance: float
) -> float:
    """Calculate overall score: weighted average of three components."""
    overall = (
        0.35 * implementability +
        0.35 * strategic_value +
        0.30 * maintainer_relevance
    )
    return float(min(100, max(0, overall)))
