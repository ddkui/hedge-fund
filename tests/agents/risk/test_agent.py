import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.risk.agent import RiskAgent


def make_agent():
    settings = MagicMock()
    settings.risk_max_position_pct = 0.10
    settings.risk_max_positions = 10
    settings.risk_max_drawdown_pct = 0.20
    settings.risk_var_limit_pct = 0.05
    settings.risk_max_correlated = 3
    with patch("agents.risk.agent.settings", settings):
        agent = RiskAgent(
            name="risk",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=120,
        )
    agent._settings = settings
    return agent


OPEN_POSITIONS = [
    {"symbol": "AAPL", "quantity": 10.0, "direction": "long", "entry_price": 150.0},
]

PORTFOLIO_ROW = {"cash": 90_000.0, "total_value": 95_000.0, "peak_value": 100_000.0, "open_positions": 1}


@pytest.mark.asyncio
async def test_risk_agent_no_breach_no_trade():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.fetch = AsyncMock(side_effect=[
        OPEN_POSITIONS,
        [{"symbol": "AAPL", "close": 150.0}],  # current prices
        [],  # var fetch — empty → skip var
    ])
    agent.bus.get = AsyncMock(return_value=None)
    await agent.run_once()
    # No drawdown breach (5% < 20%), no trade inserted
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 0


@pytest.mark.asyncio
async def test_risk_agent_force_closes_on_drawdown():
    agent = make_agent()
    # 25% drawdown → force close
    agent.db.fetchrow = AsyncMock(return_value={
        "cash": 75_000.0, "total_value": 75_000.0, "peak_value": 100_000.0, "open_positions": 1
    })
    agent.db.fetch = AsyncMock(side_effect=[
        OPEN_POSITIONS,
        [{"symbol": "AAPL", "close": 150.0}],
        [],
    ])
    agent.bus.get = AsyncMock(return_value=None)
    await agent.run_once()
    # Should insert a close trade for the largest loser
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1


@pytest.mark.asyncio
async def test_risk_agent_logs_breach_to_risk_events():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "cash": 75_000.0, "total_value": 75_000.0, "peak_value": 100_000.0, "open_positions": 1
    })
    agent.db.fetch = AsyncMock(side_effect=[
        OPEN_POSITIONS,
        [{"symbol": "AAPL", "close": 150.0}],
        [],
    ])
    agent.bus.get = AsyncMock(return_value=None)
    await agent.run_once()
    risk_event_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO risk_events" in str(c)]
    assert len(risk_event_calls) >= 1
