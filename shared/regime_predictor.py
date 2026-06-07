"""
ML regime prediction: predict regime changes before they occur.
Uses VIX patterns, unemployment, Fed data to forecast regimes.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
import numpy as np


class Regime(str, Enum):
    EXPANSION = "expansion"
    CRISIS = "crisis"
    PANDEMIC = "pandemic"


class RegimePredictor:
    """Predicts market regime changes using historical patterns."""

    def __init__(
        self,
        min_history_points: int = 5,
        vix_crisis_threshold: float = 30.0,
        vix_panic_threshold: float = 50.0,
        unemployment_spike_threshold: float = 1.5,
    ):
        self.min_history = min_history_points
        self.vix_crisis = vix_crisis_threshold
        self.vix_panic = vix_panic_threshold
        self.unemployment_spike = unemployment_spike_threshold

    def predict_next_regime(
        self,
        vix_history: List[float],
        economic_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Predict next regime from VIX and economic data."""
        if len(vix_history) < self.min_history:
            return None

        vix_array = np.array(vix_history)

        recent_vix = vix_array[-1]
        vix_volatility = np.std(vix_array[-5:]) if len(vix_array) >= 5 else np.std(vix_array)

        # Check for VIX spike pattern
        if self._detect_vix_spike(vix_array):
            if recent_vix > self.vix_panic:
                return {
                    "predicted_regime": Regime.PANDEMIC,
                    "confidence": 0.9,
                    "reason": "VIX panic spike detected (> 50)"
                }
            elif recent_vix > self.vix_crisis:
                return {
                    "predicted_regime": Regime.CRISIS,
                    "confidence": 0.85,
                    "reason": "VIX spike detected (> 30)"
                }

        # Check economic data if provided
        if economic_data:
            econ_prediction = self._predict_from_economic(economic_data)
            if econ_prediction:
                return econ_prediction

        # Default to expansion if stable
        if vix_volatility < 5 and recent_vix < self.vix_crisis:
            return {
                "predicted_regime": Regime.EXPANSION,
                "confidence": 0.65,
                "reason": "Stable conditions - expansion likely"
            }

        return None

    def predict_from_economic_data(
        self,
        economic_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Predict regime from unemployment, Fed data."""
        return self._predict_from_economic(economic_data)

    def _detect_vix_spike(self, vix_array: np.ndarray) -> bool:
        """Detect if VIX has spiked recently."""
        recent = vix_array[-3:] if len(vix_array) >= 3 else vix_array
        return recent[-1] > recent[0] and recent[-1] - recent[0] > 5

    def _predict_from_economic(
        self,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Predict from unemployment rate, Fed actions."""
        unemployment = data.get("unemployment_rate", 0)
        prev_unemployment = data.get("previous_unemployment", 0)
        fed_action = data.get("fed_emergency_action", False)

        # Unemployment spike
        if unemployment - prev_unemployment > self.unemployment_spike:
            return {
                "predicted_regime": Regime.CRISIS,
                "confidence": 0.8,
                "reason": f"Unemployment spike detected ({prev_unemployment:.1f}% → {unemployment:.1f}%)"
            }

        # Fed emergency action
        if fed_action:
            return {
                "predicted_regime": Regime.CRISIS,
                "confidence": 0.85,
                "reason": "Fed emergency action detected"
            }

        return None
