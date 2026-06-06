# tests/agents/optimizer/test_optimizer.py
import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock


def make_optimizer(yaml_path=None):
    from agents.optimizer.agent import AgentOptimizer
    agent = AgentOptimizer.__new__(AgentOptimizer)
    agent.name = "optimizer"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent._running = True
    agent.interval_seconds = 86400
    agent.params_path = yaml_path or "agent_params.yaml"
    return agent


@pytest.mark.asyncio
async def test_compute_accuracy_returns_correct_ratio():
    agent = make_optimizer()
    agent.db.fetch = AsyncMock(return_value=[
        {"was_correct": True, "pnl": 50.0},
        {"was_correct": True, "pnl": 30.0},
        {"was_correct": False, "pnl": -20.0},
        {"was_correct": False, "pnl": -10.0},
    ] * 3)  # 12 rows, ratio still 0.5
    accuracy, avg_pnl = await agent._compute_accuracy("technical", "expansion")
    assert accuracy == 0.5


@pytest.mark.asyncio
async def test_small_change_auto_applied(tmp_path):
    yaml_content = {
        "vwap": {"expansion": {"deviation_threshold_pct": 1.5}},
        "_meta": {"alpha_tier": "learning"}
    }
    params_file = tmp_path / "agent_params.yaml"
    params_file.write_text(yaml.dump(yaml_content))

    agent = make_optimizer(str(params_file))
    agent.db.execute = AsyncMock()

    await agent._apply_change(
        agent_name="vwap", regime="expansion",
        param_name="deviation_threshold_pct",
        current_val=1.5, new_val=1.6,
        reason="accuracy below threshold"
    )

    updated = yaml.safe_load(params_file.read_text())
    assert updated["vwap"]["expansion"]["deviation_threshold_pct"] == 1.6
    agent.db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_large_change_creates_proposal():
    agent = make_optimizer()
    agent.db.execute = AsyncMock()

    await agent._propose_change(
        agent_name="vwap", regime="expansion",
        param_name="deviation_threshold_pct",
        current_val=1.5, new_val=3.0,
        reason="accuracy 35% over 30d"
    )

    agent.db.execute.assert_called_once()
    sql = agent.db.execute.call_args[0][0]
    assert "optimizer_proposals" in sql


@pytest.mark.asyncio
async def test_skips_when_exceptional_alpha():
    agent = make_optimizer()
    agent.bus.get = AsyncMock(return_value={"tier": "exceptional_alpha"})
    agent.db.fetch = AsyncMock()
    await agent.run_once()
    # No regime queries should have run
    agent.db.fetch.assert_not_called()
