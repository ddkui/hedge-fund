"""
Parameter auto-tuning: optimize agent_params.yaml per regime.
Auto-applies changes < 10%, requires CIO approval > 10%.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class TuningProposal:
    agent: str
    regime: str
    parameter: str
    current_value: Any
    proposed_value: Any
    reason: str
    confidence_gain: float
    requires_approval: bool


class ParameterTuner:
    """Auto-tunes agent parameters. Uses Optuna (TPE + MedianPruner) when returns_series is provided."""

    def __init__(
        self,
        auto_apply_threshold_pct: float = 10.0,
        storage: Optional[str] = "sqlite:///optuna_tuning.db",
        n_trials: int = 20,
    ):
        self.auto_apply_threshold = auto_apply_threshold_pct
        self._storage = storage
        self._n_trials = n_trials

    def propose_change(
        self,
        agent: str,
        regime: str,
        parameter: str,
        current_value: Any,
        win_rate: float,
        returns_series: Any = None,
    ) -> Optional[Dict[str, Any]]:
        if win_rate >= 0.65:
            return None

        if returns_series is not None:
            return self._optuna_propose(agent, regime, parameter, current_value, returns_series)

        if win_rate < 0.45:
            proposed = self._adjust_parameter(parameter, current_value)
            return {
                "agent": agent,
                "regime": regime,
                "parameter": parameter,
                "current_value": current_value,
                "proposed_value": proposed,
                "reason": f"Low accuracy ({win_rate*100:.1f}%) - needs tuning",
                "confidence_gain": self.calculate_confidence_gain(win_rate, 0.55),
                "requires_approval": self.requires_approval(current_value, proposed, "percentage"),
            }

        return None

    def _optuna_propose(
        self,
        agent: str,
        regime: str,
        parameter: str,
        current_value: float,
        returns_series: Any,
    ) -> Optional[Dict[str, Any]]:
        import optuna
        import numpy as np
        from optuna.samplers import TPESampler
        from optuna.pruners import MedianPruner
        from sklearn.model_selection import TimeSeriesSplit

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(),
            study_name=f"{agent}_{regime}_{parameter}",
            storage=self._storage,
            load_if_exists=True,
        )
        returns_arr = np.array(returns_series, dtype=float)
        tscv = TimeSeriesSplit(n_splits=3)

        def objective(trial: optuna.Trial) -> float:
            lo = current_value * 0.5 if current_value > 0 else current_value * 2.0
            hi = current_value * 2.0 if current_value > 0 else current_value * 0.5
            if lo > hi:
                lo, hi = hi, lo
            candidate = trial.suggest_float(parameter, lo, hi)
            scores = []
            for step, (_, test_idx) in enumerate(tscv.split(returns_arr)):
                scaled = returns_arr[test_idx] * ((candidate / current_value) if current_value != 0 else 1.0)
                std = float(np.std(scaled))
                score = float(np.mean(scaled)) / std if std > 1e-9 else 0.0
                trial.report(score, step)
                if trial.should_prune():
                    raise optuna.exceptions.TrialPruned()
                scores.append(score)
            return float(np.mean(scores))

        study.optimize(objective, n_trials=self._n_trials)
        best_val = study.best_params.get(parameter, current_value)
        proposed = round(float(best_val), 4) if isinstance(current_value, float) else int(best_val)
        return {
            "agent": agent,
            "regime": regime,
            "parameter": parameter,
            "current_value": current_value,
            "proposed_value": proposed,
            "reason": f"Optuna TPE optimisation ({self._n_trials} trials)",
            "confidence_gain": self.calculate_confidence_gain(0.45, 0.55),
            "requires_approval": self.requires_approval(current_value, proposed, "percentage"),
        }

    def suggest_variations(
        self,
        parameter: str,
        current_value: float,
        param_type: str = "float",
        min_val: float = None,
        max_val: float = None,
        num_suggestions: int = 3,
    ) -> List[Any]:
        """
        Suggest parameter variations to test via backtesting.
        Returns list of suggested values (current_value excluded)
        """
        variations = []

        if param_type == "int":
            adjustments = [-0.10, -0.05, 0.05, 0.10]
            for adj in adjustments:
                new_val = int(current_value * (1 + adj))
                if min_val and new_val < min_val:
                    continue
                if max_val and new_val > max_val:
                    continue
                if new_val != current_value:
                    variations.append(new_val)
        else:
            adjustments = [-0.10, -0.05, 0.05, 0.10]
            for adj in adjustments:
                new_val = current_value * (1 + adj)
                if min_val and new_val < min_val:
                    continue
                if max_val and new_val > max_val:
                    continue
                if abs(new_val - current_value) > 0.0001:
                    variations.append(round(new_val, 4))

        return variations[:num_suggestions]

    def calculate_confidence_gain(
        self,
        old_win_rate: float,
        new_win_rate: float,
    ) -> float:
        """Calculate estimated confidence improvement."""
        return new_win_rate - old_win_rate

    def requires_approval(
        self,
        old_value: Any,
        new_value: Any,
        change_type: str = "percentage",
    ) -> bool:
        """
        Determine if change requires CIO approval.
        Auto-apply: < 10% change
        Require approval: >= 10% change
        """
        if change_type == "percentage":
            if old_value == 0:
                return True
            pct_change = abs((new_value - old_value) / old_value) * 100
            return pct_change >= self.auto_apply_threshold

        return True

    def _adjust_parameter(self, parameter: str, current_value: Any) -> Any:
        """Suggest adjustment (5% change)."""
        if isinstance(current_value, int):
            return int(current_value * 1.05)
        else:
            return round(current_value * 1.05, 4)


