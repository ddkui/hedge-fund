import json
from datetime import datetime, timezone
from shared.agent_base import BaseAgent


class AnalysisAgent(BaseAgent):
    async def store_signal(
        self,
        signal_type: str,
        confidence: float,
        reasoning: str,
        symbol: str | None = None,
        metadata: dict | None = None,
    ):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO signals (time, agent, symbol, signal_type, confidence, reasoning, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            now, self.name, symbol, signal_type, confidence, reasoning,
            json.dumps(metadata or {}),
        )
        safe_metadata = json.loads(json.dumps(metadata or {}))
        try:
            await self.bus.publish(f"signals.{self.name}", {
                "agent": self.name,
                "symbol": symbol,
                "signal_type": signal_type,
                "confidence": confidence,
                "reasoning": reasoning,
                "metadata": safe_metadata,
                "time": now.isoformat(),
            })
        except Exception as exc:
            self.logger.error("signal_publish_failed", signal_type=signal_type, symbol=symbol, error=str(exc))
