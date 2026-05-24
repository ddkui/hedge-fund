from collections import defaultdict
from datetime import datetime, timezone
from agents.base import AnalysisAgent
from shared.memory import MemoryMixin

QUANT_AGENTS = ["momentum", "mean_reversion", "ml_quant"]
BULLISH_KEYWORDS = {"bullish"}
BEARISH_KEYWORDS = {"bearish"}


def _direction(signal_type: str) -> float:
    st = signal_type.lower()
    if any(k in st for k in BULLISH_KEYWORDS):
        return 1.0
    if any(k in st for k in BEARISH_KEYWORDS):
        return -1.0
    return 0.0


class QuantSupervisorAgent(MemoryMixin, AnalysisAgent):
    async def run_once(self):
        signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, time
            FROM signals
            WHERE agent = ANY($1) AND time > now_or_backtest() - INTERVAL '10 minutes'
            ORDER BY time DESC
            """,
            QUANT_AGENTS,
        )

        algo_rows = await self.db.fetch(
            """
            SELECT quant_agent, sharpe_ratio
            FROM quant_algos
            WHERE status != 'retired'
            """
        )
        sharpe_weights = {
            r["quant_agent"]: max(0.1, float(r["sharpe_ratio"] or 1.0))
            for r in algo_rows
        }

        if not signals:
            return

        by_symbol: dict[str, list] = defaultdict(list)
        for sig in signals:
            by_symbol[sig["symbol"]].append(sig)

        for symbol, sigs in by_symbol.items():
            weighted_score = 0.0
            total_weight = 0.0

            for sig in sigs:
                w = sharpe_weights.get(sig["agent"], 1.0)
                direction = _direction(sig["signal_type"])
                confidence = float(sig["confidence"]) / 100.0
                weighted_score += direction * confidence * w
                total_weight += w

            if total_weight == 0:
                continue

            normalized = weighted_score / total_weight

            if normalized > 0.1:
                signal_type = "quant_bullish"
            elif normalized < -0.1:
                signal_type = "quant_bearish"
            else:
                continue

            confidence = min(100.0, abs(normalized) * 100 * (1 + len(sigs) / 5))

            quant_reasoning = f"quant_weighted_score={normalized:.3f}, signals_used={len(sigs)}"
            await self.store_signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                reasoning=quant_reasoning,
                metadata={
                    "weighted_score": round(normalized, 4),
                    "signal_count": len(sigs),
                    "agents": [s["agent"] for s in sigs],
                },
            )
            now = datetime.now(timezone.utc)
            await self.write_to_obsidian(
                title=f"Quant Decision: {symbol} {signal_type}",
                body=f"**Decision:** {signal_type}\n**Reason:** {quant_reasoning}\n**Confidence:** {confidence:.2f}",
                tags=["quant", "supervisor", signal_type],
            )
            await self.write_to_chroma(
                doc_id=f"quant-supervisor-{symbol}-{now.isoformat()}",
                text=quant_reasoning,
                metadata={"symbol": symbol, "agent": "quant_supervisor", "signal_type": signal_type},
            )
            self.logger.info("quant_consensus", symbol=symbol, signal=signal_type, score=normalized)
