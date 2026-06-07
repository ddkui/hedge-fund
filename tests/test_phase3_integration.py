"""Phase 3 Integration tests: parameter tuner → regime predictor → signal combiner → order clusterer."""
import pytest
from shared.parameter_tuner import ParameterTuner
from shared.regime_predictor import RegimePredictor
from shared.signal_combiner import SignalCombiner
from shared.order_clusterer import OrderClusterer

def test_full_optimization_flow():
    """Test: poor signal → tune parameters → predict regime → combine signals → batch orders."""

    # 1. Detect poor agent performance
    tuner = ParameterTuner()
    proposal = tuner.propose_change(
        agent="technical",
        regime="expansion",
        parameter="rsi_threshold",
        current_value=30,
        win_rate=0.40
    )
    assert proposal is not None

    # 2. Predict regime changes
    predictor = RegimePredictor()
    vix_spike = [15.0, 18.0, 25.0, 35.0]
    regime_pred = predictor.predict_next_regime(vix_spike)
    assert regime_pred["predicted_regime"] == "crisis"

    # 3. Combine signals from multiple timeframes
    combiner = SignalCombiner()
    signals = {
        "5m": {"bullish": 0.7},
        "15m": {"bullish": 0.8},
        "1h": {"bullish": 0.85},
    }
    combined = combiner.combine(signals)
    assert combined["confidence"] > 0.75

    # 4. Batch orders for execution
    clusterer = OrderClusterer(min_batch_value=10000)
    clusterer.add_order({"symbol": "AAPL", "qty": 50, "price": 150})
    clusterer.add_order({"symbol": "MSFT", "qty": 20, "price": 300})
    batch = clusterer.get_batch()
    assert batch is not None
    assert batch.total_value > 10000
