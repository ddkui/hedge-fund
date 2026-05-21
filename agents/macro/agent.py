from agents.base import AnalysisAgent
from agents.macro.regime import classify_regime


class MacroResearchAgent(AnalysisAgent):
    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT DISTINCT ON (series_id) series_id, value, time
            FROM macro_data
            ORDER BY series_id, time DESC
            """
        )
        if not rows:
            return

        latest = {r["series_id"]: float(r["value"]) for r in rows}

        # Get previous FEDFUNDS reading for cycle detection
        prev_rows = await self.db.fetch(
            """
            SELECT value FROM macro_data
            WHERE series_id = 'FEDFUNDS'
            ORDER BY time DESC LIMIT 2
            """
        )
        if len(prev_rows) >= 2:
            latest["FEDFUNDS_PREV"] = float(prev_rows[1]["value"])

        result = classify_regime(latest)

        prompt = (
            f"Current macroeconomic regime: {result.summary}\n\n"
            f"Raw indicators: {latest}\n\n"
            "As a senior macroeconomic strategist, provide a 2-paragraph outlook: "
            "(1) what this regime means for equities, bonds, and crypto, "
            "(2) what to watch for a regime change. Be concise and specific."
        )
        narrative = await self.router.chat("macro", [{"role": "user", "content": prompt}])

        await self.store_signal(
            symbol=None,
            signal_type=f"macro_regime_{result.regime.value}",
            confidence=result.confidence,
            reasoning=f"{result.summary}\n\n{narrative}",
            metadata={
                "regime": result.regime.value,
                "fed_cycle": result.fed_cycle.value,
                "yield_curve_inverted": result.yield_curve_inverted,
                "risk_on": result.risk_on,
                "indicators": {k: round(v, 2) for k, v in latest.items()},
            },
        )
        self.logger.info("macro_regime", regime=result.regime.value, fed_cycle=result.fed_cycle.value)
