import pytest
from shared.regime_predictor import RegimePredictor, Regime

def test_predictor_identifies_crisis_from_vix_pattern():
    """Test that predictor detects crisis regime from VIX spike pattern."""
    predictor = RegimePredictor()

    vix_history = [15.0, 16.0, 18.0, 22.0, 25.0, 30.0, 35.0]

    prediction = predictor.predict_next_regime(vix_history)

    assert prediction["predicted_regime"] == Regime.CRISIS
    assert prediction["confidence"] > 0.7
    assert "VIX spike detected" in prediction["reason"]

def test_predictor_returns_confidence_score():
    """Test that predictor returns confidence between 0-1."""
    predictor = RegimePredictor()

    vix = [20.0, 21.0, 22.0, 25.0, 30.0]

    result = predictor.predict_next_regime(vix)

    assert 0 <= result["confidence"] <= 1

def test_predictor_detects_unemployment_spike():
    """Test that predictor detects unemployment spike as crisis signal."""
    predictor = RegimePredictor()

    economic_data = {
        "unemployment_rate": 5.2,
        "previous_unemployment": 3.5,
        "fed_emergency_action": False
    }

    prediction = predictor.predict_from_economic_data(economic_data)

    assert prediction["predicted_regime"] == Regime.CRISIS
    assert "Unemployment spike" in prediction["reason"]

def test_predictor_identifies_expansion_stability():
    """Test that stable conditions predict expansion."""
    predictor = RegimePredictor()

    vix = [15.0, 15.2, 14.8, 15.1, 15.3]
    economic = {
        "unemployment_rate": 3.8,
        "previous_unemployment": 3.7,
        "fed_emergency_action": False
    }

    result = predictor.predict_next_regime(vix, economic)

    assert result["predicted_regime"] == Regime.EXPANSION
    assert result["confidence"] > 0.6

def test_predictor_requires_minimum_history():
    """Test that predictor requires sufficient historical data."""
    predictor = RegimePredictor(min_history_points=5)

    short_history = [20.0, 21.0]

    result = predictor.predict_next_regime(short_history)

    assert result is None
