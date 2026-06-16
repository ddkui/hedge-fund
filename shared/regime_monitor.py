# shared/regime_monitor.py
"""
Intraday regime switching based on volatility and macro signals.
Adjusts parameters when VIX > 30 or other hard flags triggered.
"""
from __future__ import annotations

import os
from enum import Enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class Regime(str, Enum):
    EXPANSION = "expansion"
    CRISIS = "crisis"
    PANDEMIC = "pandemic"


class RegimeMonitor:
    MODEL_PATH = "models/hmm_regime.pkl"

    def __init__(self):
        self.current_regime = Regime.EXPANSION
        self.vix_threshold_crisis = 30.0
        self.vix_threshold_panic = 50.0
        self.hard_flags = {
            "vix_above_threshold": False,
            "unemployment_spike": False,
            "fed_emergency_action": False,
        }
        self._model = None
        self._label_map: dict[int, Regime] = {}
        self._load_model()

    def _load_model(self) -> None:
        try:
            import joblib
            data = joblib.load(self.MODEL_PATH)
            self._model = data["model"]
            self._label_map = data["label_map"]
        except Exception:
            pass

    def fit(self, features: "np.ndarray") -> None:
        """Train GaussianHMM(n=3) on [vix, vix_change_1d, yield_curve_spread, credit_spread]."""
        import numpy as np
        import joblib
        from hmmlearn import hmm

        model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=100, random_state=42)
        model.fit(features)
        order = np.argsort(model.means_[:, 0])
        self._label_map = {
            int(order[0]): Regime.EXPANSION,
            int(order[1]): Regime.CRISIS,
            int(order[2]): Regime.PANDEMIC,
        }
        self._model = model
        os.makedirs(os.path.dirname(self.MODEL_PATH) or ".", exist_ok=True)
        joblib.dump({"model": model, "label_map": self._label_map}, self.MODEL_PATH)

    def predict_regime_probability(self, features: "np.ndarray") -> dict[Regime, float]:
        """Returns {Regime: probability}; falls back to rule-based certainty if no model trained."""
        if self._model is None:
            return {Regime.EXPANSION: 1.0, Regime.CRISIS: 0.0, Regime.PANDEMIC: 0.0}
        probs = self._model.predict_proba(features)
        last = probs[-1]
        result: dict[Regime, float] = {}
        for i, p in enumerate(last):
            r = self._label_map.get(i, Regime.EXPANSION)
            result[r] = result.get(r, 0.0) + float(p)
        return result

    def predict_regime(self, features: "np.ndarray") -> Regime:
        probs = self.predict_regime_probability(features)
        return max(probs, key=lambda r: probs[r])

    def update_vix(self, vix_value: float) -> Regime:
        """
        Update regime based on VIX level.

        Returns:
            New regime (may be same as current)
        """
        if vix_value > self.vix_threshold_panic:
            self.current_regime = Regime.PANDEMIC
            self.hard_flags["vix_above_threshold"] = True
        elif vix_value > self.vix_threshold_crisis:
            self.current_regime = Regime.CRISIS
            self.hard_flags["vix_above_threshold"] = True
        else:
            self.current_regime = Regime.EXPANSION
            self.hard_flags["vix_above_threshold"] = False

        return self.current_regime

    def check_hard_flags(self, flags: dict) -> Regime:
        """
        Check hard flags (unemployment spike, Fed action, etc).

        Args:
            flags: Dict of flag_name -> bool

        Returns:
            Updated regime
        """
        self.hard_flags.update(flags)

        if any([
            self.hard_flags.get("unemployment_spike", False),
            self.hard_flags.get("fed_emergency_action", False),
        ]):
            self.current_regime = Regime.CRISIS
        elif self.hard_flags.get("vix_above_threshold", False):
            self.current_regime = Regime.CRISIS

        return self.current_regime

    def get_regime(self) -> Regime:
        """Get current regime."""
        return self.current_regime

    def reset_daily(self) -> None:
        """Reset intraday flags at market open."""
        self.hard_flags = {k: False for k in self.hard_flags}


