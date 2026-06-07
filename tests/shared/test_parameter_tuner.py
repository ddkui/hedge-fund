import pytest
from datetime import datetime, timedelta
from shared.parameter_tuner import ParameterTuner

def test_tuner_generates_proposal_for_low_accuracy():
    """Test that tuner proposes parameter change when accuracy < 45%."""
    tuner = ParameterTuner()

    agent = "technical"
    regime = "expansion"
    current_win_rate = 0.35
    parameter = "rsi_threshold"
    current_value = 30

    proposal = tuner.propose_change(
        agent=agent,
        regime=regime,
        parameter=parameter,
        current_value=current_value,
        win_rate=current_win_rate
    )

    assert proposal is not None
    assert proposal["parameter"] == "rsi_threshold"
    assert proposal["current_value"] == 30
    assert proposal["proposed_value"] != 30
    assert proposal["reason"] == "Low accuracy (35.0%) - needs tuning"

def test_tuner_no_proposal_for_high_accuracy():
    """Test that tuner skips tuning when win_rate >= 65%."""
    tuner = ParameterTuner()

    proposal = tuner.propose_change(
        agent="sentiment",
        regime="crisis",
        parameter="confidence_threshold",
        current_value=0.5,
        win_rate=0.75
    )

    assert proposal is None

def test_tuner_suggests_parameter_variations():
    """Test that tuner suggests reasonable parameter variations."""
    tuner = ParameterTuner()

    suggestions = tuner.suggest_variations(
        parameter="rsi_threshold",
        current_value=30,
        param_type="int",
        min_val=10,
        max_val=90
    )

    assert len(suggestions) > 0
    assert 10 <= suggestions[0] <= 90
    assert suggestions[0] != 30
    for val in suggestions:
        assert isinstance(val, int)

def test_tuner_calculates_confidence_gain():
    """Test that tuner estimates confidence gain from parameter change."""
    tuner = ParameterTuner()

    gain = tuner.calculate_confidence_gain(
        old_win_rate=0.40,
        new_win_rate=0.50
    )

    assert gain > 0
    assert gain == pytest.approx(0.10)

def test_tuner_respects_change_threshold():
    """Test that small changes auto-apply, large changes need approval."""
    tuner = ParameterTuner()

    small_change = tuner.requires_approval(
        old_value=100,
        new_value=105,
        change_type="percentage"
    )
    assert not small_change

    large_change = tuner.requires_approval(
        old_value=100,
        new_value=125,
        change_type="percentage"
    )
    assert large_change
