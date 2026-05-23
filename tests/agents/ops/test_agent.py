import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from agents.ops.agent import OpsAgent

KNOWN_AGENTS = {
    "technical": 120,
    "sentiment": 300,
    "macro": 300,
}


def make_agent():
    with patch("agents.ops.agent.settings") as mock_settings:
        mock_settings.gmail_sender = "alerts@example.com"
        agent = OpsAgent(
            name="ops",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=60,
        )
    agent._known_agents = KNOWN_AGENTS.copy()
    return agent


@pytest.mark.asyncio
async def test_ops_marks_agent_healthy_on_heartbeat():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen["technical"] = now

    await agent._check_agents()

    healthy_calls = [c for c in agent.db.execute.call_args_list if "agent_health" in str(c)]
    assert len(healthy_calls) == 0  # healthy = only written on heartbeat receive, not check cycle


@pytest.mark.asyncio
async def test_ops_detects_degraded_agent():
    agent = make_agent()
    # technical has interval 120s; if last seen > 2*120 = 240s ago → degraded
    agent._last_seen["technical"] = datetime.now(timezone.utc) - timedelta(seconds=300)

    await agent._check_agents()

    degraded_calls = [c for c in agent.db.execute.call_args_list if "degraded" in str(c)]
    assert len(degraded_calls) >= 1


@pytest.mark.asyncio
async def test_ops_detects_down_agent():
    agent = make_agent()
    # technical has interval 120s; if last seen > 5*120 = 600s ago → down
    agent._last_seen["technical"] = datetime.now(timezone.utc) - timedelta(seconds=700)

    with patch("agents.ops.agent.settings") as mock_settings, \
         patch("agents.ops.agent.smtplib") as mock_smtp:
        mock_settings.gmail_sender = "alerts@example.com"
        mock_smtp.SMTP_SSL.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_smtp.SMTP_SSL.return_value.__exit__ = MagicMock(return_value=False)
        await agent._check_agents()

    down_calls = [c for c in agent.db.execute.call_args_list if "'down'" in str(c)]
    assert len(down_calls) >= 1
