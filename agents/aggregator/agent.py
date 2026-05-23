from collections import defaultdict
from agents.base import AnalysisAgent
from agents.macro.regime import MacroRegime

AGENT_CATEGORY = {
    "technical": "technical",
    "sentiment": "sentiment",
    "macro": "macro",
    "research": "fundamental",
}

REGIME_WEIGHTS = {
    MacroRegime.EXPANSION:   {"technical": 0.30, "fundamental": 0.30, "sentiment": 0.25, "macro": 0.15},
    MacroRegime.CONTRACTION: {"technical": 0.20, "fundamental": 0.30, "sentiment": 0.10, "macro": 0.40},
    MacroRegime.STAGFLATION: {"technical": 0.25, "fundamental": 0.25, "sentiment": 0.10, "macro": 0.40},
    MacroRegime.RECOVERY:    {"technical": 0.35, "fundamental": 0.25, "sentiment": 0.15, "macro": 0.25},
}

DEFAULT_WEIGHTS = {"technical": 0.30, "fundamental": 0.30, "sentiment": 0.20, "macro": 0.20}

BULLISH_KEYWORDS = {"bullish", "overbought", "macd_bullish", "expansion", "recovery", "bb_lower_touch"}
BEARISH_KEYWORDS = {"bearish", "oversold_risk", "macd_bearish", "contraction", "stagflation", "bb_upper_touch"}


def _signal_direction(signal_type: str) -> float:
    st = signal_type.lower()
    if any(k in st for k in BULLISH_KEYWORDS):
        return 1.0
    if any(k in st for k in BEARISH_KEYWORDS):
        return -1.0
    return 0.0


class SignalAggregatorAgent(AnalysisAgent):
    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, time
            FROM signals
            WHERE time > now_or_backtest() - INTERVAL '6 hours'
              AND agent != 'aggregator'
            ORDER BY time DESC
            """
        )
        if not rows:
            return

        # Detect current macro regime from recent macro signals
        current_regime = MacroRegime.EXPANSION
        for row in rows:
            if row["agent"] == "macro":
                for regime in MacroRegime:
                    if regime.value in row["signal_type"]:
                        current_regime = regime
                        break
                break

        weights = REGIME_WEIGHTS.get(current_regime, DEFAULT_WEIGHTS)

        # Group signals by symbol
        by_symbol: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            sym = row["symbol"] or "__market__"
            by_symbol[sym].append(row)

        for symbol, signals in by_symbol.items():
            if symbol == "__market__":
                continue

            weighted_score = 0.0
            total_weight = 0.0

            for sig in signals:
                cat = AGENT_CATEGORY.get(sig["agent"], "technical")
                w = weights.get(cat, 0.25)
                direction = _signal_direction(sig["signal_type"])
                confidence = float(sig["confidence"]) / 100.0
                weighted_score += direction * confidence * w
                total_weight += w

            if total_weight == 0:
                continue

            normalized = weighted_score / total_weight
            consensus_confidence = min(100.0, abs(normalized) * 100 * (1 + len(signals) / 10))

            if normalized > 0.1:
                consensus = "consensus_bullish"
            elif normalized < -0.1:
                consensus = "consensus_bearish"
            else:
                consensus = "consensus_neutral"

            agent_breakdown = [
                {"agent": sig["agent"], "signal": sig["signal_type"], "confidence": sig["confidence"]}
                for sig in signals[:5]
            ]

            await self.store_signal(
                symbol=symbol,
                signal_type=consensus,
                confidence=consensus_confidence,
                reasoning=(
                    f"Regime={current_regime.value}, weighted_score={normalized:.3f}, "
                    f"signals_used={len(signals)}, weights={weights}"
                ),
                metadata={
                    "regime": current_regime.value,
                    "weighted_score": round(normalized, 4),
                    "signal_count": len(signals),
                    "agent_breakdown": agent_breakdown,
                },
            )
            self.logger.info("consensus_signal", symbol=symbol, consensus=consensus, score=normalized)
