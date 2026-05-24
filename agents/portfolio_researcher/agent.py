# agents/portfolio_researcher/agent.py
from agents.base import AnalysisAgent


def _direction(signal_type: str) -> str:
    st = signal_type.lower()
    if "bullish" in st:
        return "bullish"
    if "bearish" in st:
        return "bearish"
    return "neutral"


class PortfolioResearcherAgent(AnalysisAgent):
    """
    Runs every 30 minutes. For each open position, pulls latest signals
    and emits Hold / Trim / Sell with full reasoning for the PM to act on.

    Logic:
    - Opposing signal with conf >= 65 → sell (thesis broken)
    - Aligned signal with conf < 45    → trim (conviction weakening)
    - Aligned signal with conf >= 45   → hold
    - No signal                        → hold
    """

    async def run_once(self):
        open_positions = await self.db.fetch(
            "SELECT id, symbol, direction, entry_thesis "
            "FROM positions WHERE status = 'open'"
        )
        if not open_positions:
            return

        sell_count = 0

        for pos in open_positions:
            symbol = pos["symbol"]
            entry_direction = pos["direction"]  # "long" or "short"

            latest_signals = await self.db.fetch(
                """
                SELECT agent, symbol, signal_type, confidence, reasoning
                FROM signals
                WHERE symbol = $1
                  AND agent IN ('aggregator', 'quant_supervisor', 'research', 'sentiment')
                  AND time > now() - INTERVAL '30 minutes'
                ORDER BY time DESC
                LIMIT 10
                """,
                symbol,
            )

            if not latest_signals:
                await self.store_signal(
                    symbol=symbol,
                    signal_type="hold",
                    confidence=50.0,
                    reasoning=f"No fresh signals for {symbol} — holding",
                )
                continue

            # Use aggregator as primary, fall back to others
            primary = next(
                (s for s in latest_signals if s["agent"] == "aggregator"),
                latest_signals[0],
            )
            sig_direction = _direction(primary["signal_type"])
            conf = float(primary["confidence"])

            # Determine position direction
            pos_direction = "bullish" if entry_direction == "long" else "bearish"
            opposing = sig_direction != pos_direction and sig_direction != "neutral"

            if opposing and conf >= 65.0:
                action = "sell"
                reasoning = (
                    f"Thesis contradicted: entered {pos_direction}, "
                    f"now seeing {sig_direction} ({conf:.0f}% conf). "
                    f"Original thesis: {pos['entry_thesis'] or 'unknown'}"
                )
                sell_count += 1
            elif not opposing and conf < 45.0:
                action = "trim"
                reasoning = f"Conviction weakening: {sig_direction} at {conf:.0f}% — trim position"
            else:
                action = "hold"
                reasoning = f"Thesis intact: {sig_direction} at {conf:.0f}%"

            await self.store_signal(
                symbol=symbol,
                signal_type=action,
                confidence=conf,
                reasoning=reasoning,
            )

        # Alert CIO if multiple simultaneous sells
        if sell_count >= 3:
            await self.bus.publish("cio.alert", {
                "level": "urgent",
                "message": f"Portfolio Researcher flagged {sell_count} simultaneous sell signals",
            })
