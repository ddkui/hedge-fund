from typing import Dict, Any
from agents.supervisor_researcher.models import PaperMetadata

STRATEGY_SIGNAL_MAPPING = {
    "momentum": {"direction": "BUY", "template": "Momentum strategy paper '{title}' suggests buying momentum stocks"},
    "mean_reversion": {"direction": "SELL", "template": "Mean reversion paper '{title}' suggests selling overvalued positions"},
    "pairs_trading": {"direction": "NEUTRAL", "template": "Pairs trading research '{title}' suggests establishing pairs positions"},
    "ml": {"direction": "BUY", "template": "ML trading paper '{title}' suggests algorithmic buy signals"},
}


def create_draft_signal(paper: PaperMetadata, confidence_score: float, strategy_tags: str) -> Dict[str, Any]:
    """Create draft trading signal from paper."""
    primary_strategy = strategy_tags.split(',')[0] if strategy_tags else "momentum"
    signal_config = STRATEGY_SIGNAL_MAPPING.get(primary_strategy, STRATEGY_SIGNAL_MAPPING["momentum"])
    reasoning = signal_config["template"].format(title=paper.title) + f" Paper by {paper.authors}"
    return {
        "paper_id": paper.paper_id,
        "paper_title": paper.title,
        "paper_url": paper.url,
        "source": paper.source,
        "strategy_type": primary_strategy,
        "direction": signal_config["direction"],
        "reasoning": reasoning,
        "confidence": confidence_score,
        "tags": strategy_tags,
        "requires_review": confidence_score < 75
    }
