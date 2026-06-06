# shared/notifications.py
"""
NotificationService — subscribes to Redis alert channels and fires Gmail emails.

Events handled:
  trade_executed, trade_pending, risk_breach, agent_down, feed_failure,
  algo_approved, multi_sell, position_closed, daily_brief, weekly_report
"""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
import structlog


EVENT_SUBJECTS = {
    "trade_executed":  "[HedgeFund] Trade Executed: {symbol} {action}",
    "trade_pending":   "[HedgeFund] ⏳ Trade Awaiting Approval: {symbol}",
    "risk_breach":     "[HedgeFund] 🚨 URGENT: Risk Limit Breached",
    "agent_down":      "[HedgeFund] 🚨 URGENT: Agent DOWN — {agent}",
    "feed_failure":    "[HedgeFund] ⚠️ Data Feed Failure: {feed}",
    "algo_approved":   "[HedgeFund] ✅ New Algo Approved: {name}",
    "multi_sell":      "[HedgeFund] 🚨 URGENT: Multiple Positions Flagged SELL",
    "position_closed": "[HedgeFund] Position Closed: {symbol}",
    "daily_brief":     "[HedgeFund] 📊 Daily Briefing",
    "weekly_report":   "[HedgeFund] 📈 Weekly Performance Report",
}


class NotificationService:
    def __init__(self, sender: str, recipient: str, app_password: str):
        self.sender = sender
        self.recipient = recipient
        self.app_password = app_password
        self.logger = structlog.get_logger()

    def _format_email(self, event: str, data: dict[str, Any]) -> tuple[str, str]:
        """Return (subject, body) for an event."""
        # Daily brief: use the pre-formatted report and subject from the CIO
        if event == "daily_brief" and "report" in data:
            subject = data.get("subject", EVENT_SUBJECTS["daily_brief"])
            return subject, data["report"]

        template = EVENT_SUBJECTS.get(event, "[HedgeFund] Notification: {event}")
        try:
            subject = template.format(**{**data, "event": event})
        except KeyError:
            subject = template.split("{")[0].strip() + f" — {event}"

        lines = [f"**Event:** {event}", ""]
        for key, value in data.items():
            lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
        body = "\n".join(lines)
        return subject, body

    def _send_email(self, subject: str, body: str):
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = self.recipient
            msg.attach(MIMEText(body, "plain"))
            html_body = f"<html><body><pre style='font-family:monospace'>{body}</pre></body></html>"
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                server.login(self.sender, self.app_password)
                server.send_message(msg)
            self.logger.info("notification_sent", subject=subject)
        except Exception as exc:
            self.logger.error("notification_failed", error=str(exc))

    async def _handle_event(self, event: str, data: dict[str, Any]):
        # Skip auto-denied trades (< 30% confidence) — no email needed
        if event == "trade_denied" and float(data.get("confidence", 0)) < 30:
            return
        subject, body = self._format_email(event, data)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_email, subject, body)

    async def run(self, bus):
        """Subscribe to all relevant Redis channels and fire emails."""
        CHANNEL_EVENT_MAP = {
            "trade.executed":    "trade_executed",
            "trade.pending":     "trade_pending",
            "ops.alert":         "agent_down",
            "risk.breach":       "risk_breach",
            "feed.failure":      "feed_failure",
            "algo.approved":     "algo_approved",
            "cio.multi_sell":    "multi_sell",
            "trade.closed":      "position_closed",
            "cio.daily_brief":   "daily_brief",
            "cio.weekly_report": "weekly_report",
        }
        tasks = [
            asyncio.create_task(self._subscribe(bus, channel, event))
            for channel, event in CHANNEL_EVENT_MAP.items()
        ]
        await asyncio.gather(*tasks)

    async def _subscribe(self, bus, channel: str, event: str):
        try:
            async for msg in bus.subscribe(channel):
                await self._handle_event(event, msg)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.logger.error("notification_subscribe_failed", channel=channel, error=str(exc))
