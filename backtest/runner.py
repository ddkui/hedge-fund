import asyncio
import logging
from datetime import datetime, timezone

from backtest.clock import BacktestClock
from backtest.bus import InMemoryBus
from backtest.db import BacktestDB
from shared.config import settings

logger = logging.getLogger("backtest.runner")


class NullRouter:
    """Satisfies agents that call self.router — returns empty string."""
    async def complete(self, *args, **kwargs) -> str:
        return ""

    async def chat(self, *args, **kwargs) -> str:
        return ""


AGENT_TIERS: list[list[str]] = [
    ["technical", "sentiment", "macro", "research"],
    ["aggregator"],
    ["momentum", "mean_reversion", "ml_quant"],
    ["quant_supervisor"],
    ["portfolio_mgr"],
    ["risk"],
    ["execution"],
]

_WATCHLIST = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")


def _build_agent(name: str, db: BacktestDB, bus: InMemoryBus):
    router = NullRouter()
    if name == "technical":
        from agents.technical.agent import TechnicalAnalysisAgent
        return TechnicalAnalysisAgent("technical", bus, db, router, watchlist=_WATCHLIST)
    if name == "sentiment":
        from agents.sentiment.agent import SentimentAgent
        return SentimentAgent("sentiment", bus, db, router)
    if name == "macro":
        from agents.macro.agent import MacroResearchAgent
        return MacroResearchAgent("macro", bus, db, router)
    if name == "research":
        from agents.research.agent import FundamentalResearchAgent
        return FundamentalResearchAgent("research", bus, db, router)
    if name == "aggregator":
        from agents.aggregator.agent import SignalAggregatorAgent
        return SignalAggregatorAgent("aggregator", bus, db, router)
    if name == "momentum":
        from agents.quant.momentum.agent import MomentumQuantAgent
        return MomentumQuantAgent("momentum", bus, db, router, watchlist=_WATCHLIST)
    if name == "mean_reversion":
        from agents.quant.mean_reversion.agent import MeanReversionQuantAgent
        return MeanReversionQuantAgent("mean_reversion", bus, db, router, watchlist=_WATCHLIST)
    if name == "ml_quant":
        from agents.quant.ml_quant.agent import MLQuantAgent
        return MLQuantAgent("ml_quant", bus, db, router, watchlist=_WATCHLIST)
    if name == "quant_supervisor":
        from agents.quant.supervisor.agent import QuantSupervisorAgent
        return QuantSupervisorAgent("quant_supervisor", bus, db, router)
    if name == "portfolio_mgr":
        from agents.portfolio_mgr.agent import PortfolioManagerAgent
        return PortfolioManagerAgent("portfolio_mgr", bus, db, router)
    if name == "risk":
        from agents.risk.agent import RiskAgent
        return RiskAgent("risk", bus, db, router)
    if name == "execution":
        from agents.execution.agent import ExecutionAgent
        return ExecutionAgent("execution", bus, db, router)
    raise ValueError(f"Unknown agent: {name}")


class BacktestRunner:
    def __init__(
        self,
        run_id: int,
        clock: BacktestClock,
        db: BacktestDB,
        bus: InMemoryBus,
        agent_names: list[str],
    ):
        self._run_id = run_id
        self._clock = clock
        self._db = db
        self._bus = bus
        self._tiers = self._build_tiers(agent_names, db, bus)

    def _build_tiers(
        self, agent_names: list[str], db: BacktestDB, bus: InMemoryBus
    ) -> list[list]:
        name_set = set(agent_names)
        tiers = []
        for tier_names in AGENT_TIERS:
            tier = []
            for name in tier_names:
                if name in name_set:
                    agent = _build_agent(name, db, bus)
                    agent._now = lambda: self._db.current_tick
                    tier.append(agent)
            if tier:
                tiers.append(tier)
        return tiers

    async def run(self):
        first_tick = True
        for tick in self._clock.ticks():
            await self._db.set_tick(tick)
            if first_tick:
                await self._seed_portfolio(tick)
                first_tick = False
            for tier in self._tiers:
                for agent in tier:
                    try:
                        await agent.run_once()
                    except Exception as exc:
                        logger.warning(
                            "agent_error",
                            extra={"agent": agent.name, "tick": tick.isoformat(), "error": str(exc)},
                        )

    async def _seed_portfolio(self, tick: datetime):
        await self._db.execute(
            """
            INSERT INTO portfolio_state (time, cash, total_value, peak_value, open_positions)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tick,
            settings.initial_capital,
            settings.initial_capital,
            settings.initial_capital,
            0,
        )

    async def _fire_tier(self, agents: list):
        for agent in agents:
            try:
                await agent.run_once()
            except Exception as exc:
                logger.warning("agent_error", extra={"agent": getattr(agent, 'name', '?'), "error": str(exc)})
