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
    """Auto-tunes agent parameters based on backtesting results."""

    def __init__(self, auto_apply_threshold_pct: float = 10.0):
        """
        Args:
            auto_apply_threshold_pct: Changes <= this % auto-apply
        """
        self.auto_apply_threshold = auto_apply_threshold_pct

    def propose_change(
        self,
        agent: str,
        regime: str,
        parameter: str,
        current_value: Any,
        win_rate: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Propose parameter change if accuracy is low.
        Returns None if agent is performing well (win_rate >= 65%)
        """
        if win_rate >= 0.65:
            return None

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
                "requires_approval": self.requires_approval(
                    current_value, proposed, "percentage"
                )
            }

        return None

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
