import pytest
from datetime import date
from agents.supervisor_researcher.signal_generator import create_draft_signal
from agents.supervisor_researcher.models import PaperMetadata


def test_create_draft_signal_momentum():
    """Test creating momentum paper signal, asserts direction BUY."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_001",
        source="arxiv",
        title="Advanced Momentum Strategies in Quantitative Trading",
        authors="Smith, J.; Johnson, K.",
        abstract="This paper explores momentum-based trading strategies using machine learning.",
        url="https://arxiv.org/abs/2024.00001",
        publication_date=date(2024, 3, 15)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=85.5,
        strategy_tags="momentum"
    )

    assert signal["paper_id"] == "arxiv_2024_001"
    assert signal["paper_title"] == "Advanced Momentum Strategies in Quantitative Trading"
    assert signal["paper_url"] == "https://arxiv.org/abs/2024.00001"
    assert signal["source"] == "arxiv"
    assert signal["strategy_type"] == "momentum"
    assert signal["direction"] == "BUY"
    assert signal["confidence"] == 85.5
    assert signal["tags"] == "momentum"
    assert signal["requires_review"] is False
    assert "momentum stocks" in signal["reasoning"]
    assert "Smith, J.; Johnson, K." in signal["reasoning"]


def test_create_draft_signal_pairs():
    """Test creating pairs paper signal, asserts direction NEUTRAL."""
    metadata = PaperMetadata(
        paper_id="ssrn_2024_002",
        source="ssrn",
        title="Statistical Arbitrage Using Pairs Trading",
        authors="Doe, A.; Smith, B.",
        abstract="A study on pairs trading methodologies.",
        url="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4567890",
        publication_date=date(2024, 1, 10)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=72.0,
        strategy_tags="pairs_trading"
    )

    assert signal["paper_id"] == "ssrn_2024_002"
    assert signal["strategy_type"] == "pairs_trading"
    assert signal["direction"] == "NEUTRAL"
    assert signal["confidence"] == 72.0
    assert "pairs positions" in signal["reasoning"]
    assert signal["requires_review"] is True  # 72 < 75


def test_signal_requires_review_when_low_confidence():
    """Test that signal requires_review is true when confidence < 75."""
    metadata = PaperMetadata(
        paper_id="test_2024_001",
        source="arxiv",
        title="Test Paper",
        authors="Test Author",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 1, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=74.9,
        strategy_tags="momentum"
    )

    assert signal["requires_review"] is True
    assert signal["confidence"] == 74.9


def test_signal_no_review_when_high_confidence():
    """Test that signal requires_review is false when confidence >= 75."""
    metadata = PaperMetadata(
        paper_id="test_2024_002",
        source="arxiv",
        title="Test Paper",
        authors="Test Author",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 1, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=75.0,
        strategy_tags="momentum"
    )

    assert signal["requires_review"] is False
    assert signal["confidence"] == 75.0


def test_create_draft_signal_mean_reversion():
    """Test creating mean reversion paper signal, asserts direction SELL."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_003",
        source="arxiv",
        title="Mean Reversion Detection Using Deep Learning",
        authors="Chen, X.; Lee, Y.",
        abstract="A study on mean reversion patterns.",
        url="https://arxiv.org/abs/2024.00003",
        publication_date=date(2024, 2, 20)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=88.0,
        strategy_tags="mean_reversion"
    )

    assert signal["strategy_type"] == "mean_reversion"
    assert signal["direction"] == "SELL"
    assert signal["confidence"] == 88.0
    assert signal["requires_review"] is False
    assert "overvalued positions" in signal["reasoning"]


def test_create_draft_signal_ml():
    """Test creating ML trading paper signal, asserts direction BUY."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_004",
        source="arxiv",
        title="Machine Learning for Trading Signal Generation",
        authors="Park, S.; Kim, J.",
        abstract="Using ML models for trading signals.",
        url="https://arxiv.org/abs/2024.00004",
        publication_date=date(2024, 4, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=81.5,
        strategy_tags="ml"
    )

    assert signal["strategy_type"] == "ml"
    assert signal["direction"] == "BUY"
    assert signal["confidence"] == 81.5
    assert signal["requires_review"] is False
    assert "algorithmic buy signals" in signal["reasoning"]


def test_create_draft_signal_multiple_tags():
    """Test creating signal with multiple strategy tags uses first tag."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_005",
        source="arxiv",
        title="Combined Strategies",
        authors="Author, A.",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 1, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=80.0,
        strategy_tags="momentum,ml,mean_reversion"
    )

    # Should use first tag (momentum)
    assert signal["strategy_type"] == "momentum"
    assert signal["direction"] == "BUY"
    assert signal["tags"] == "momentum,ml,mean_reversion"


def test_create_draft_signal_empty_tags_defaults_to_momentum():
    """Test that empty strategy_tags defaults to momentum."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_006",
        source="arxiv",
        title="Unknown Strategy Paper",
        authors="Author, B.",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 1, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=70.0,
        strategy_tags=""
    )

    # Should default to momentum
    assert signal["strategy_type"] == "momentum"
    assert signal["direction"] == "BUY"
    assert signal["requires_review"] is True  # 70 < 75


def test_create_draft_signal_unknown_strategy():
    """Test that unknown strategy defaults to momentum."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_007",
        source="arxiv",
        title="Unknown Strategy Paper",
        authors="Author, C.",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 1, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=80.0,
        strategy_tags="unknown_strategy"
    )

    # Should default to momentum for unknown strategy
    assert signal["strategy_type"] == "unknown_strategy"
    # But STRATEGY_SIGNAL_MAPPING returns default (momentum) config
    assert signal["direction"] == "BUY"


def test_create_draft_signal_contains_all_required_fields():
    """Test that signal contains all required fields."""
    metadata = PaperMetadata(
        paper_id="arxiv_2024_008",
        source="arxiv",
        title="Test Paper",
        authors="Test Author",
        abstract="Test abstract",
        url="https://arxiv.org/abs/test",
        publication_date=date(2024, 1, 1)
    )

    signal = create_draft_signal(
        paper=metadata,
        confidence_score=80.0,
        strategy_tags="momentum"
    )

    required_fields = [
        "paper_id", "paper_title", "paper_url", "source",
        "strategy_type", "direction", "reasoning", "confidence",
        "tags", "requires_review"
    ]

    for field in required_fields:
        assert field in signal, f"Missing required field: {field}"
        assert signal[field] is not None, f"Field {field} is None"
