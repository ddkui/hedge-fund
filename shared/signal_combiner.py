"""Multi-timeframe signal combining: merge 5m/15m/1h signals."""
from typing import Dict, Optional, Any
from enum import Enum


class SignalType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalCombiner:
    """Combines signals from multiple timeframes with weighted voting."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        consensus_threshold: float = 0.60,
    ):
        self.weights = weights or {"5m": 0.20, "15m": 0.30, "1h": 0.50}
        self.consensus_threshold = consensus_threshold

    def combine(
        self,
        signals: Dict[str, Dict[str, float]],
    ) -> Optional[Dict[str, Any]]:
        """Combine signals from multiple timeframes."""
        required = set(self.weights.keys())
        provided = set(signals.keys())
        if provided != required:
            return None

        bullish_score = 0.0
        bearish_score = 0.0

        for timeframe, weight in self.weights.items():
            tf_signals = signals[timeframe]
            bullish_score += tf_signals.get("bullish", 0) * weight
            bearish_score += tf_signals.get("bearish", 0) * weight

        net_score = bullish_score - bearish_score
        confidence = abs(net_score) / 2 + 0.5

        signal_type = (
            SignalType.BULLISH if net_score > 0.1
            else SignalType.BEARISH if net_score < -0.1
            else SignalType.NEUTRAL
        )

        warning = None
        if bullish_score > 0.4 and bearish_score > 0.4:
            warning = "Conflicting signals between timeframes"
            confidence *= 0.7

        result = {
            "signal": signal_type.value,
            "confidence": min(confidence, 1.0),
        }

        if warning:
            result["warning"] = warning

        return result

    def get_timeframe_agreement(
        self,
        signals: Dict[str, Dict[str, float]],
    ) -> float:
        """Calculate agreement score between timeframes."""
        if not signals or len(signals) < 2:
            return 1.0

        scores = [s.get("bullish", 0) for s in signals.values()]
        max_score = max(scores)
        min_score = min(scores)

        agreement = 1.0 - ((max_score - min_score) / 1.0)
        return agreement
