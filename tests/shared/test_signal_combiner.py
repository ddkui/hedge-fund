import pytest
from shared.signal_combiner import SignalCombiner

def test_combiner_weights_timeframes():
    """Test that combiner applies correct timeframe weights."""
    combiner = SignalCombiner(weights={"5m": 0.2, "15m": 0.3, "1h": 0.5})

    signals = {
        "5m": {"bullish": 0.8},
        "15m": {"bullish": 0.7},
        "1h": {"bullish": 0.9},
    }

    combined = combiner.combine(signals)

    assert combined["confidence"] == pytest.approx(0.82, abs=0.01)

def test_combiner_requires_all_timeframes():
    """Test that combiner requires signals from all timeframes."""
    combiner = SignalCombiner(weights={"5m": 0.2, "15m": 0.3, "1h": 0.5})

    signals = {"5m": {"bullish": 0.8}}

    result = combiner.combine(signals)

    assert result is None

def test_combiner_detects_conflicting_signals():
    """Test that combiner flags conflicting signals."""
    combiner = SignalCombiner()

    signals = {
        "5m": {"bullish": 0.9},
        "15m": {"bearish": 0.8},
        "1h": {"bullish": 0.7},
    }

    result = combiner.combine(signals)

    assert result["confidence"] < 0.5
    assert "conflicting" in result.get("warning", "").lower()

def test_combiner_consensus_threshold():
    """Test that strong consensus produces high confidence."""
    combiner = SignalCombiner()

    signals = {
        "5m": {"bullish": 0.9},
        "15m": {"bullish": 0.85},
        "1h": {"bullish": 0.88},
    }

    result = combiner.combine(signals)

    assert result["confidence"] > 0.8
    assert result["signal"] == "bullish"

def test_combiner_reduces_false_signals():
    """Test that combining reduces false signals."""
    combiner = SignalCombiner()

    signals = {
        "5m": {"bullish": 0.52},
        "15m": {"bullish": 0.48},
        "1h": {"bullish": 0.50},
    }

    result = combiner.combine(signals)

    assert 0.45 <= result["confidence"] <= 0.55
