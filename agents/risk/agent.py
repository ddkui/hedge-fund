from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.config import settings
from agents.risk.checker import RiskChecker


class RiskAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._checker = RiskChecker(settings=settings)

    async def run_once(self):
        state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        if not state:
            return

        portfolio_value = float(state["total_value"])
        peak_value = float(state["peak_value"])

        positions = await self.db.fetch(
            "SELECT symbol, quantity, direction, entry_price FROM positions WHERE status = 'open'"
        )
        if not positions:
            return

        open_symbols = [p["symbol"] for p in positions]
        price_rows = await self.db.fetch(
            "SELECT DISTINCT ON (symbol) symbol, close FROM prices WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
            open_symbols,
        )
        prices = {r["symbol"]: float(r["close"]) for r in price_rows}

        # Drawdown check
        if peak_value > 0:
            drawdown = (peak_value - portfolio_value) / peak_value
            if drawdown >= settings.risk_max_drawdown_pct:
                await self._log_event(None, "drawdown", f"{drawdown*100:.1f}% exceeds {settings.risk_max_drawdown_pct*100:.0f}%", "position_force_closed")
                await self._force_close_largest_loser(positions, prices)

    async def _force_close_largest_loser(self, positions: list, prices: dict):
        worst = None
        worst_pnl = float("inf")
        for pos in positions:
            sym = pos["symbol"]
            price = prices.get(sym)
            if price is None:
                continue
            pnl = (price - float(pos["entry_price"])) * float(pos["quantity"])
            if pos["direction"] == "short":
                pnl = -pnl
            if worst is None or pnl < worst_pnl:
                worst = pos
                worst_pnl = pnl

        if worst is None:
            return

        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO trades (time, symbol, action, quantity, price, paper, pm_reasoning, confidence)
            VALUES ($1, $2, 'close', $3, $4, $5, $6, $7)
            """,
            now,
            worst["symbol"],
            float(worst["quantity"]),
            0.0,
            True,
            "RiskAgent force-close: drawdown limit breached",
            0.0,
        )
        self.logger.warning("force_close_issued", symbol=worst["symbol"], pnl=worst_pnl)

    async def _log_event(self, symbol, limit_type: str, details: str, action_taken: str):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) VALUES ($1,$2,$3,$4,$5,$6)",
            now, self.name, symbol, limit_type, details, action_taken,
        )
