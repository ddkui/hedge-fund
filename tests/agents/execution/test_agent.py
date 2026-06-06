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


@pytest.mark.asyncio
async def test_fan_out_paper_returns_price_fill():
    """Paper trades go through price lookup, not real brokers."""
    mock_settings, agent = make_agent(paper=True)
    trade = {**PENDING_TRADE, "paper": True}
    agent.db.fetch = AsyncMock(return_value=[{"close": 185.0}])
    with patch("agents.execution.agent.settings", mock_settings):
        fills = await agent._fan_out(trade)
    assert len(fills) == 1
    assert fills[0].broker_name == "paper"
    assert fills[0].fill_price == 185.0
    assert fills[0].status == "filled"


@pytest.mark.asyncio
async def test_fan_out_live_uses_registry():
    """Live trades fan out to all available brokers."""
    mock_settings, agent = make_agent(paper=False)
    mock_settings.paper_trading = False

    from shared.brokers.base import BrokerFill
    mock_broker = AsyncMock()
    mock_broker.is_available = AsyncMock(return_value=True)
    mock_broker.fill = AsyncMock(return_value=BrokerFill(
        broker_name="mock-broker", trade_id=1, status="filled",
        fill_price=185.0, fill_qty=5.0, error_msg=None
    ))
    agent._registry._adapters = [mock_broker]

    trade = {**PENDING_TRADE, "paper": False}
    with patch("agents.execution.agent.settings", mock_settings):
        fills = await agent._fan_out(trade)

    assert len(fills) == 1
    assert fills[0].broker_name == "mock-broker"
    assert fills[0].fill_price == 185.0


@pytest.mark.asyncio
async def test_fan_out_continues_if_one_broker_fails():
    """If one broker errors, others still execute."""
    mock_settings, agent = make_agent(paper=False)
    mock_settings.paper_trading = False

    from shared.brokers.base import BrokerFill
    good_broker = AsyncMock()
    good_broker.is_available = AsyncMock(return_value=True)
    good_broker.fill = AsyncMock(return_value=BrokerFill(
        broker_name="good", trade_id=1, status="filled",
        fill_price=185.0, fill_qty=5.0, error_msg=None
    ))
    bad_broker = AsyncMock()
    bad_broker.is_available = AsyncMock(return_value=True)
    bad_broker.fill = AsyncMock(side_effect=Exception("connection error"))
    agent._registry._adapters = [good_broker, bad_broker]

    trade = {**PENDING_TRADE, "paper": False}
    with patch("agents.execution.agent.settings", mock_settings):
        fills = await agent._fan_out(trade)

    # Only the good broker's fill returned; bad broker exception is swallowed
    assert len(fills) == 1
    assert fills[0].broker_name == "good"


def test_median_fill_price_uses_median():
    """Median fill price is used when multiple brokers fill at different prices."""
    mock_settings, agent = make_agent()
    from shared.brokers.base import BrokerFill
    fills = [
        BrokerFill("a", 1, "filled", 184.0, 5.0, None),
        BrokerFill("b", 1, "filled", 186.0, 5.0, None),
        BrokerFill("c", 1, "filled", 185.0, 5.0, None),
    ]
    trade = {**PENDING_TRADE}
    price = agent._median_fill_price(fills, trade)
    assert price == 185.0


@pytest.mark.asyncio
async def test_store_broker_fills_writes_one_row_per_fill():
    mock_settings, agent = make_agent()
    agent.db.execute = AsyncMock()
    from shared.brokers.base import BrokerFill
    fills = [
        BrokerFill("alpaca", 1, "filled", 185.0, 5.0, None),
        BrokerFill("ib", 1, "filled", 185.5, 5.0, None),
    ]
    await agent._store_broker_fills(fills)
    assert agent.db.execute.call_count == 2
    sql = agent.db.execute.call_args_list[0][0][0]
    assert "broker_fills" in sql
