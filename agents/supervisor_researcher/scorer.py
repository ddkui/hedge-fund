# agents/supervisor_researcher/scorer.py
import numpy as np
from typing import Dict, List
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer('all-MiniLM-L6-v2')

STRATEGY_KEYWORDS = {
    "momentum": ["momentum", "trend following"],
    "mean_reversion": ["mean reversion", "reverting"],
    "pairs_trading": ["pairs trading", "statistical arbitrage"],
    "ml": ["machine learning", "deep learning", "neural network", "lstm"],
    "alternative_data": ["alternative data", "satellite", "sentiment"]
}

def calculate_relevance_score(
    paper_title: str,
    paper_abstract: str,
    strategy_descriptions: Dict[str, str]
) -> float:
    """Calculate relevance score using semantic similarity (0-100)."""
    paper_text = f"{paper_title}. {paper_abstract}"
    paper_embedding = model.encode(paper_text)
    strategy_embeddings = {
        name: model.encode(desc)
        for name, desc in strategy_descriptions.items()
    }
    similarities = [
        cosine_similarity([paper_embedding], [strategy_embeddings[name]])[0][0]
        for name in strategy_embeddings
    ]
    max_similarity = max(similarities) if similarities else 0.0
    return float(min(100, max_similarity * 100))

def calculate_academic_score(
    citations: int,
    max_citations_in_dataset: int,
    venue_rank: float = 0.5
) -> float:
    """Calculate academic quality score (0-100)."""
    citation_score = min(100, (citations / max_citations_in_dataset) * 100) if max_citations_in_dataset > 0 else 0
    academic_score = (citation_score * 0.7) + (venue_rank * 100 * 0.3)
    return float(min(100, academic_score))

def calculate_confidence_score(
    relevance_score: float,
    academic_score: float,
    days_old: int
) -> float:
    """Calculate combined confidence: 0.5*relevance + 0.3*recency + 0.2*academic."""
    recency_score = max(0, (7 - days_old) / 7 * 100)
    confidence = (
        0.5 * relevance_score +
        0.3 * recency_score +
        0.2 * academic_score
    )
    return float(min(100, max(0, confidence)))

def tag_strategies(paper_abstract: str) -> List[str]:
    """Auto-tag paper with relevant strategies based on keywords."""
    abstract_lower = paper_abstract.lower()
    tags = []
    for strategy, keywords in STRATEGY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in abstract_lower:
                tags.append(strategy)
                break
    return tags if tags else ["other"]
