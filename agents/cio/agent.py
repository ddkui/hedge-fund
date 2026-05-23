import json
import re
from agents.base import AnalysisAgent
from shared.config import settings

DIRECTIVE_TTL_SECONDS = 25 * 3600  # 25 hours


class CIOAgent(AnalysisAgent):
    async def run_once(self):
        all_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, reasoning, time
            FROM signals
            WHERE time > NOW() - INTERVAL '24 hours'
            ORDER BY time DESC
            LIMIT 200
            """
        )
        open_positions = await self.db.fetch(
            "SELECT symbol, direction, quantity, entry_price FROM positions WHERE status = 'open'"
        )
        price_rows = await self.db.fetch(
            "SELECT DISTINCT ON (symbol) symbol, close FROM prices WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
            [p["symbol"] for p in open_positions] or ["__none__"],
        )
        prices = {r["symbol"]: float(r["close"]) for r in price_rows}

        positions_with_pnl = []
        for pos in open_positions:
            price = prices.get(pos["symbol"], float(pos["entry_price"]))
            direction_multiplier = -1.0 if pos["direction"] == "short" else 1.0
            pnl = (price - float(pos["entry_price"])) * float(pos["quantity"]) * direction_multiplier
            positions_with_pnl.append({
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "quantity": float(pos["quantity"]),
                "entry_price": float(pos["entry_price"]),
                "current_price": price,
                "unrealized_pnl": round(pnl, 2),
            })

        closed_trades = await self.db.fetch(
            """
            SELECT symbol, action, quantity, price, pm_reasoning, time
            FROM trades
            WHERE status = 'executed' AND time > NOW() - INTERVAL '7 days'
            ORDER BY time DESC
            LIMIT 50
            """
        )
        macro_signal = await self.db.fetch(
            "SELECT signal_type, confidence, time FROM signals WHERE agent = 'macro' ORDER BY time DESC LIMIT 1"
        )
        risk_events = await self.db.fetch(
            "SELECT limit_type, details, action_taken, time FROM risk_events WHERE time > NOW() - INTERVAL '24 hours'"
        )
        cio_overrides = await self.db.fetch(
            "SELECT symbol, reasoning, time FROM signals WHERE signal_type = 'cio_override' AND time > NOW() - INTERVAL '24 hours'"
        )

        macro_regime = macro_signal[0]["signal_type"] if macro_signal else "unknown"

        prompt = self._build_prompt(
            positions=positions_with_pnl,
            closed_trades=[dict(r) for r in closed_trades],
            macro_regime=macro_regime,
            risk_events=[dict(r) for r in risk_events],
            cio_overrides=[dict(r) for r in cio_overrides],
            recent_signals=[dict(r) for r in all_signals[:30]],
        )

        raw_response = await self.router.complete(
            prompt=prompt,
            model=settings.ollama_research_model,
            system="You are a Chief Investment Officer. Respond only with a valid JSON array of directives.",
        )

        directives = self._parse_directives(raw_response)

        for directive in directives:
            if directive.get("action", "none") == "none":
                continue
            symbol = directive.get("symbol")
            if not symbol:
                continue
            await self.bus.set(
                f"cio:directive:{symbol}",
                {
                    "action": directive["action"],
                    "reason": directive.get("reason", ""),
                    "confidence_multiplier": float(directive.get("confidence_multiplier", 1.0)),
                },
                ex=DIRECTIVE_TTL_SECONDS,
            )
            self.logger.info("cio_directive_set", symbol=symbol, action=directive["action"])

        pm_pushback_note = ""
        if cio_overrides:
            pm_pushback_note = f" PM overrode {len(cio_overrides)} CIO directive(s)."

        await self.store_signal(
            signal_type="daily_brief",
            confidence=100.0,
            reasoning=f"Regime={macro_regime}. {len(directives)} directives issued.{pm_pushback_note} Raw: {raw_response[:500]}",
            metadata={
                "positions": positions_with_pnl,
                "directives": directives,
                "regime": macro_regime,
                "risk_events_count": len(risk_events),
                "cio_overrides_count": len(cio_overrides),
            },
        )

    def _build_prompt(self, positions, closed_trades, macro_regime, risk_events, cio_overrides, recent_signals) -> str:
        return f"""You are reviewing the hedge fund portfolio. Current macro regime: {macro_regime}.

Open positions with unrealized P&L:
{json.dumps(positions, indent=2)}

Recent closed trades (last 7 days):
{json.dumps(closed_trades[:10], indent=2, default=str)}

Recent risk events (last 24h):
{json.dumps(risk_events, indent=2, default=str)}

PM pushbacks on prior CIO directives:
{json.dumps(cio_overrides, indent=2, default=str)}

Based on this, provide a JSON array of per-symbol directives. Each item:
{{
  "symbol": "TICKER",
  "action": "low_conviction" | "avoid_open" | "request_close" | "none",
  "confidence_multiplier": 0.0-1.0,
  "reason": "one sentence"
}}

Return ONLY the JSON array, nothing else."""

    def _parse_directives(self, raw: str) -> list[dict]:
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
            result = json.loads(cleaned)
            if not isinstance(result, list):
                raise ValueError("Expected JSON array")
            return result
        except (json.JSONDecodeError, ValueError):
            self.logger.warning("cio_parse_failed", raw=raw[:200])
            return []
