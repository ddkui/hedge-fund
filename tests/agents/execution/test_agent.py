import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.execution.agent import ExecutionAgent

PENDING_TRADE = {
    "id": 1,
    "symbol": "AAPL",
    "action": "long",
    "quantity": 5.0,
    "paper": True,
}
PRICE_ROW = {"close": 151.0}
PORTFOLIO_ROW = {"cash": 100_000.0, "total_value": 100_000.0, "peak_value": 100_000.0, "open_positions": 0}


def make_agent(paper=True):
    settings = MagicMock()
    settings.paper_trading = paper
    settings.initial_capital = 100_000.0
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)  # kill switch not active by default
    agent = ExecutionAgent(
        name="execution",
        bus=bus,
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=5,
    )
    return settings, agent


@pytest.mark.asyncio
async def test_execution_fills_paper_trade():
    mock_settings, agent = make_agent(paper=True)
    agent.db.fetch = AsyncMock(side_effect=[
        [PENDING_TRADE],          # pending trades
        [PRICE_ROW],              # latest price
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    with patch("agents.execution.agent.settings", mock_settings):
        await agent.run_once()

    update_calls = [c for c in agent.db.execute.call_args_list if "UPDATE trades" in str(c)]
    assert len(update_calls) == 1
    args = update_calls[0][0]
    assert "executed" in args
    assert 151.0 in args


@pytest.mark.asyncio
async def test_execution_updates_portfolio_state_on_fill():
    mock_settings, agent = make_agent(paper=True)
    agent.db.fetch = AsyncMock(side_effect=[
        [PENDING_TRADE],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    with patch("agents.execution.agent.settings", mock_settings):
        await agent.run_once()

    state_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO portfolio_state" in str(c)]
    assert len(state_calls) == 1


@pytest.mark.asyncio
async def test_execution_skips_when_no_pending():
    mock_settings, agent = make_agent(paper=True)
    agent.db.fetch = AsyncMock(return_value=[])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    with patch("agents.execution.agent.settings", mock_settings):
        await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execution_closes_position_on_close_trade():
    mock_settings, agent = make_agent(paper=True)
    close_trade = {**PENDING_TRADE, "action": "close"}
    agent.db.fetch = AsyncMock(side_effect=[
        [close_trade],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    with patch("agents.execution.agent.settings", mock_settings):
        await agent.run_once()

    position_calls = [c for c in agent.db.execute.call_args_list if "UPDATE positions" in str(c)]
    assert len(position_calls) == 1
    args = position_calls[0][0]
    assert "closed" in args
