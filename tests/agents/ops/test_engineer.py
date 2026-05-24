# tests/agents/ops/test_engineer.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta


def make_agent():
    from agents.ops.agent import EngineerAgent
    agent = EngineerAgent.__new__(EngineerAgent)
    agent.name = "ops"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.bus.get = AsyncMock(return_value=None)
    agent.bus.publish = AsyncMock()
    agent.logger = MagicMock()
    agent._running = True
    agent._last_seen = {}
    agent._restart_counts = {}
    agent._email_sent_at = {}
    agent.interval_seconds = 60
    return agent


@pytest.mark.asyncio
async def test_engineer_detects_down_agent_and_publishes_alert():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen = {"technical": now - timedelta(seconds=700)}
    agent.db.execute = AsyncMock()
    await agent._check_agents()
    agent.bus.publish.assert_called()
    call_args = agent.bus.publish.call_args
    assert call_args[0][0] == "ops.alert"
    assert "technical" in str(call_args[0][1])


@pytest.mark.asyncio
async def test_engineer_increments_restart_count_on_down():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen = {"technical": now - timedelta(seconds=700)}
    agent.db.execute = AsyncMock()
    await agent._check_agents()
    assert agent._restart_counts.get("technical", 0) >= 1


@pytest.mark.asyncio
async def test_engineer_escalates_to_cio_after_max_restarts():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen = {"technical": now - timedelta(seconds=700)}
    agent._restart_counts = {"technical": 3}  # already at max
    agent.db.execute = AsyncMock()
    await agent._check_agents()
    # Should publish to cio.alert (escalation)
    calls = [str(c) for c in agent.bus.publish.call_args_list]
    assert any("cio.alert" in c for c in calls)


@pytest.mark.asyncio
async def test_engineer_writes_incident_to_obsidian(tmp_path):
    agent = make_agent()
    agent.obsidian_root = str(tmp_path)
    with patch.object(type(agent), "write_to_obsidian", new_callable=AsyncMock) as mock_write:
        await agent._write_incident("technical", "down", 700)
        mock_write.assert_called_once()
        call = mock_write.call_args
        assert "technical" in call.kwargs.get("title", "") or "technical" in str(call.args)
