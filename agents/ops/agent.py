import asyncio
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from shared.agent_base import BaseAgent
from shared.config import settings

KNOWN_AGENT_INTERVALS: dict[str, int] = {
    "ingest":          60,
    "technical":       120,
    "sentiment":       300,
    "macro":           300,
    "research":        600,
    "aggregator":      120,
    "momentum":        120,
    "mean_reversion":  120,
    "ml_quant":        120,
    "quant_supervisor":300,
    "portfolio_mgr":   120,
    "risk":            120,
    "execution":       5,
    "cio":             3600,
}


class OpsAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_seen: dict[str, datetime] = {}
        self._known_agents: dict[str, int] = KNOWN_AGENT_INTERVALS.copy()
        self._email_sent_at: dict[str, datetime] = {}

    async def run(self):
        self.logger.info("ops_starting")
        check_task = asyncio.create_task(self._check_loop())
        subscribe_task = asyncio.create_task(self._subscribe_loop())
        await asyncio.gather(check_task, subscribe_task)

    async def _subscribe_loop(self):
        async for msg in self.bus.subscribe("ops.heartbeat"):
            agent_name = msg.get("agent")
            if not agent_name:
                continue
            self._last_seen[agent_name] = datetime.now(timezone.utc)
            status = msg.get("status", "healthy")
            now = datetime.now(timezone.utc)
            await self.db.execute(
                """
                INSERT INTO agent_health (time, agent, status, metadata)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (agent) DO UPDATE SET time=$1, status=$3, metadata=$4
                """,
                now, agent_name, status, '{}',
            )

    async def _check_loop(self):
        while self._running:
            await self._check_agents()
            await asyncio.sleep(self.interval_seconds)

    async def _check_agents(self):
        now = datetime.now(timezone.utc)
        for agent_name, interval in self._known_agents.items():
            last = self._last_seen.get(agent_name)
            if last is None:
                continue

            gap = (now - last).total_seconds()
            if gap > 5 * interval:
                await self._write_health(agent_name, "down", gap)
                await self._maybe_alert(agent_name, gap)
            elif gap > 2 * interval:
                await self._write_health(agent_name, "degraded", gap)

    async def _write_health(self, agent_name: str, status: str, gap_seconds: float):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO agent_health (time, agent, status, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (agent) DO UPDATE SET time=$1, status=$3, metadata=$4
            """,
            now, agent_name, status, f'{{"gap_seconds": {gap_seconds:.0f}}}',
        )
        self.logger.warning("agent_health_changed", agent=agent_name, status=status, gap=gap_seconds)

    async def _maybe_alert(self, agent_name: str, gap_seconds: float):
        if not settings.gmail_sender:
            return
        last_sent = self._email_sent_at.get(agent_name)
        now = datetime.now(timezone.utc)
        if last_sent and (now - last_sent).total_seconds() < 3600:
            return

        self._email_sent_at[agent_name] = now
        subject = f"[HedgeFund] Agent DOWN: {agent_name}"
        body = f"Agent '{agent_name}' has not sent a heartbeat for {gap_seconds:.0f} seconds."
        self._send_email(subject, body)

    def _send_email(self, subject: str, body: str):
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = settings.gmail_sender
            msg["To"] = settings.gmail_sender
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(settings.gmail_sender, settings.gmail_sender)
                server.send_message(msg)
        except Exception as exc:
            self.logger.error("email_failed", error=str(exc))

    async def run_once(self):
        await self._check_agents()
