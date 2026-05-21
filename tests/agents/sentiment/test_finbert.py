import pytest
from unittest.mock import patch, MagicMock
from agents.sentiment.finbert import FinBertSentiment, SentimentResult


def test_sentiment_result_fields():
    r = SentimentResult(label="positive", score=0.92, compound=0.92)
    assert r.label == "positive"
    assert r.score == 0.92
    assert r.compound == 0.92


def test_finbert_analyze_returns_result():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"label": "positive", "score": 0.91}]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        result = fb.analyze("Apple beats earnings estimates by 15%")

    assert isinstance(result, SentimentResult)
    assert result.label == "positive"
    assert result.compound > 0


def test_finbert_negative_returns_negative_compound():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"label": "negative", "score": 0.88}]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        result = fb.analyze("Company misses revenue targets, outlook slashed")

    assert result.compound < 0


def test_finbert_neutral_returns_zero_compound():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"label": "neutral", "score": 0.78}]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        result = fb.analyze("Company reports quarterly results")

    assert result.compound == 0.0


def test_finbert_batch_analyze_returns_list():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [
        {"label": "positive", "score": 0.91},
        {"label": "negative", "score": 0.85},
    ]
    texts = ["Good earnings", "Bad outlook"]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        results = fb.batch_analyze(texts)

    assert len(results) == 2
    assert results[0].compound > 0
    assert results[1].compound < 0
