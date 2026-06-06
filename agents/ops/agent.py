# agents/ops/agent.py
"""
The Engineer — full SRE agent.
Monitors all agents, self-heals crashes, writes incident reports to Obsidian,
publishes alerts to CIO, and tracks restart counts.
"""
import asyncio
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from shared.agent_base import BaseAgent
from shared.config import settings
from shared.memory import MemoryMixin

KNOWN_AGENT_INTERVALS: dict[str, int] = {
    "ingest":               60,
    "technical":           120,
    "sentiment":           300,
    "macro":               300,
    "research":            600,
    "aggregator":          120,
    "portfolio_researcher": 1800,
    "momentum":            120,
    "mean_reversion":      120,
    "ml_quant":            120,
    "news_momentum":       120,
    "vwap":                120,
    "supply_demand":       120,
    "quant_supervisor":    300,
    "portfolio_mgr":       120,
    "risk":                120,
    "execution":             5,
    "cio":                3600,
}

AGENT_SCRIPTS: dict[str, str] = {
    "ingest":               "data/ingest/main.py",
    "technical":           "agents/technical/main.py",
    "sentiment":           "agents/sentiment/main.py",
    "macro":               "agents/macro/main.py",
    "research":            "agents/research/main.py",
    "aggregator":          "agents/aggregator/main.py",
    "portfolio_researcher":"agents/portfolio_researcher/main.py",
    "momentum":            "agents/quant/momentum/main.py",
    "mean_reversion":      "agents/quant/mean_reversion/main.py",
    "ml_quant":            "agents/quant/ml_quant/main.py",
    "news_momentum":       "agents/quant/news_momentum/main.py",
    "vwap":                "agents/quant/vwap/main.py",
    "supply_demand":       "agents/quant/supply_demand/main.py",
    "quant_supervisor":    "agents/quant/supervisor/main.py",
    "portfolio_mgr":       "agents/portfolio_mgr/main.py",
    "risk":                "agents/risk/main.py",
    "execution":           "agents/execution/main.py",
    "cio":                 "agents/cio/main.py",
}

MAX_RESTARTS = 3


class EngineerAgent(MemoryMixin, BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_seen: dict[str, datetime] = {}
        self._restart_counts: dict[str, int] = {}
        self._email_sent_at: dict[str, datetime] = {}

    async def run(self):
        self.logger.info("engineer_starting")
        check_task = asyncio.create_task(self._check_loop())
        subscribe_task = asyncio.create_task(self._subscribe_loop())
        try:
            await asyncio.gather(check_task, subscribe_task)
        except asyncio.CancelledError:
            check_task.cancel()
            subscribe_task.cancel()
            await asyncio.gather(check_task, subscribe_task, return_exceptions=True)
            raise

    async def _subscribe_loop(self):
        try:
            async for msg in self.bus.subscribe("ops.heartbeat"):
                agent_name = msg.get("agent")
                if not agent_name:
                    continue
                self._last_seen[agent_name] = self._now()
                status = msg.get("status", "healthy")
                now = self._now()
                await self.db.execute(
                    "INSERT INTO agent_health (time, agent, status, metadata) VALUES ($1, $2, $3, $4)",
                    now, agent_name, status, '{}',
                )
                if status == "healthy" and agent_name in self._restart_counts:
                    self._restart_counts[agent_name] = 0
        except asyncio.CancelledError:
            pass

    async def _check_loop(self):
        while self._running:
            await self._check_agents()
            await asyncio.sleep(self.interval_seconds)

    async def _check_agents(self):
        now = self._now()
        for agent_name, interval in KNOWN_AGENT_INTERVALS.items():
            last = self._last_seen.get(agent_name)
            if last is None:
                continue
            gap = (now - last).total_seconds()
            if gap > 5 * interval:
                await self._handle_down(agent_name, gap)
            elif gap > 2 * interval:
                await self._write_health(agent_name, "degraded", gap)

    async def _handle_down(self, agent_name: str, gap_seconds: float):
        await self._write_health(agent_name, "down", gap_seconds)
        restart_count = self._restart_counts.get(agent_name, 0)

        if restart_count < MAX_RESTARTS:
            self._restart_counts[agent_name] = restart_count + 1
            self.logger.warning("engineer_restarting_agent", agent=agent_name, attempt=restart_count + 1)
            await self._restart_agent(agent_name)
            await self.bus.publish("ops.alert", {
                "agent": agent_name,
                "level": "warning",
                "message": f"Agent {agent_name} was down — restart attempt {restart_count + 1}/{MAX_RESTARTS}",
            })
        else:
            await self.bus.publish("cio.alert", {
                "level": "urgent",
                "agent": agent_name,
                "message": f"Agent {agent_name} failed {MAX_RESTARTS} restart attempts — manual intervention required",
            })
            await self._write_incident(agent_name, "down", gap_seconds)
            await self._maybe_send_email(agent_name, gap_seconds)

    async def _restart_agent(self, agent_name: str):
        script = AGENT_SCRIPTS.get(agent_name)
        if not script:
            return
        try:
            subprocess.Popen([sys.executable, script])
        except Exception as exc:
            self.logger.error("engineer_restart_failed", agent=agent_name, error=str(exc))

    async def _write_health(self, agent_name: str, status: str, gap_seconds: float):
        now = self._now()
        await self.db.execute(
            "INSERT INTO agent_health (time, agent, status, metadata) VALUES ($1, $2, $3, $4)",
            now, agent_name, status, f'{{"gap_seconds": {gap_seconds:.0f}}}',
        )
        self.logger.warning("agent_health_changed", agent=agent_name, status=status, gap=gap_seconds)

    async def _write_incident(self, agent_name: str, status: str, gap_seconds: float):
        await self.write_to_obsidian(
            title=f"Incident: {agent_name} {status}",
            body=(
                f"## Incident Report\n\n"
                f"**Agent:** {agent_name}\n"
                f"**Status:** {status}\n"
                f"**Gap:** {gap_seconds:.0f}s\n"
                f"**Restart attempts:** {self._restart_counts.get(agent_name, 0)}\n"
                f"**Time:** {self._now().isoformat()}\n\n"
                f"Engineer exhausted {MAX_RESTARTS} restart attempts. Manual intervention required."
            ),
            tags=["incident", "ops", agent_name],
        )

    async def _maybe_send_email(self, agent_name: str, gap_seconds: float):
        if not settings.gmail_sender:
            return
        last_sent = self._email_sent_at.get(agent_name)
        now = self._now()
        if last_sent and (now - last_sent).total_seconds() < 3600:
            return
        self._email_sent_at[agent_name] = now
        import smtplib
        from email.mime.text import MIMEText
        try:
            msg = MIMEText(
                f"Agent '{agent_name}' has been down for {gap_seconds:.0f}s.\n"
                f"Engineer made {MAX_RESTARTS} restart attempts — all failed.\n"
                f"Manual intervention required."
            )
            msg["Subject"] = f"[HedgeFund] URGENT: Agent {agent_name} DOWN"
            msg["From"] = settings.gmail_sender
            msg["To"] = settings.gmail_sender
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(settings.gmail_sender, settings.gmail_app_password)
                server.send_message(msg)
        except Exception as exc:
            self.logger.error("email_failed", error=str(exc))

    async def run_once(self):
        await self._check_agents()
