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
async def test_capital_com_fill_long_calls_place_order():
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"
    mock_settings.capital_com_base_url = "https://demo-api-capital.backend.gbksoft.net"
    mock_settings.capital_com_identifier = "test@example.com"
    mock_settings.capital_com_password = "pass"

    trade = {
        "id": 10,
        "symbol": "GOLD",
        "action": "long",
        "quantity": 2.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "commodities",
    }

    mock_session = AsyncMock()
    mock_session.place_order = AsyncMock(return_value=1900.5)

    with patch("agents.execution.agent.settings", mock_settings), \
         patch("agents.execution.agent.CapitalComSession", return_value=mock_session):
        price = await agent._capital_com_fill(trade)

    assert price == 1900.5
    # commodities leverage = 5 (from mock_settings), effective_size = 2.0 * 5 = 10.0
    mock_session.place_order.assert_called_once_with("GOLD", "BUY", 10.0)


@pytest.mark.asyncio
async def test_capital_com_fill_close_uses_sell_direction():
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"
    mock_settings.capital_com_base_url = "https://demo-api-capital.backend.gbksoft.net"
    mock_settings.capital_com_identifier = "test@example.com"
    mock_settings.capital_com_password = "pass"

    trade = {
        "id": 11,
        "symbol": "EURUSD",
        "action": "close",
        "quantity": 1.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "forex",
    }

    mock_session = AsyncMock()
    mock_session.place_order = AsyncMock(return_value=1.0821)

    with patch("agents.execution.agent.settings", mock_settings), \
         patch("agents.execution.agent.CapitalComSession", return_value=mock_session):
        price = await agent._capital_com_fill(trade)

    assert price == 1.0821
    call_args = mock_session.place_order.call_args[0]
    assert call_args[1] == "SELL"


@pytest.mark.asyncio
async def test_capital_com_fill_fails_trade_on_none():
    """When place_order returns None, _fail_trade is called."""
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"
    mock_settings.capital_com_base_url = "https://demo-api-capital.backend.gbksoft.net"
    mock_settings.capital_com_identifier = "test@example.com"
    mock_settings.capital_com_password = "pass"

    trade = {
        "id": 12,
        "symbol": "GOLD",
        "action": "long",
        "quantity": 1.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "commodities",
    }
    agent.db.execute = AsyncMock()

    mock_session = AsyncMock()
    mock_session.place_order = AsyncMock(return_value=None)

    with patch("agents.execution.agent.settings", mock_settings), \
         patch("agents.execution.agent.CapitalComSession", return_value=mock_session):
        price = await agent._capital_com_fill(trade)

    assert price is None
    # _fail_trade makes 2 db.execute calls: UPDATE trades SET status='failed' + INSERT INTO risk_events
    fail_calls = [c for c in agent.db.execute.call_args_list if "failed" in str(c)]
    assert len(fail_calls) == 2


@pytest.mark.asyncio
async def test_get_fill_price_routes_capital_com_trade():
    """_get_fill_price routes broker='capital_com' to _capital_com_fill."""
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"

    trade = {
        "id": 20,
        "symbol": "GOLD",
        "action": "long",
        "quantity": 1.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "commodities",
    }

    with patch("agents.execution.agent.settings", mock_settings), \
         patch.object(agent, "_capital_com_fill", new_callable=AsyncMock, return_value=1900.0) as mock_fill:
        price = await agent._get_fill_price(trade)

    mock_fill.assert_called_once_with(trade)
    assert price == 1900.0
