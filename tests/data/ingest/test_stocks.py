import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from data.ingest.stocks import StocksIngestAgent


def make_agent(watchlist=None):
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return StocksIngestAgent(
        name="stocks_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        watchlist=watchlist or ["AAPL", "MSFT"],
        interval_seconds=60,
    )


def make_fake_df():
    return pd.DataFrame(
        [{"Open": 150.0, "High": 151.0, "Low": 149.0, "Close": 150.5, "Volume": 1_000_000.0}],
        index=pd.DatetimeIndex(["2024-01-01 10:00:00+00:00"]),
    )


@pytest.mark.asyncio
async def test_stocks_agent_stores_prices():
    agent = make_agent(["AAPL"])
    agent._fetch_ticker_history = MagicMock(return_value=make_fake_df())
    await agent.run_once()
    agent.db.executemany.assert_called_once()
    records = agent.db.executemany.call_args[0][1]
    assert len(records) == 1
    assert records[0][1] == "AAPL"
    assert records[0][2] == "stock"
    assert records[0][6] == 150.5


@pytest.mark.asyncio
async def test_stocks_agent_publishes_update():
    agent = make_agent(["AAPL", "MSFT"])
    agent._fetch_ticker_history = MagicMock(return_value=make_fake_df())
    await agent.run_once()
    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.stocks.updated"
    assert call[0][1]["symbols"] == ["AAPL", "MSFT"]


@pytest.mark.asyncio
async def test_stocks_agent_skips_empty_history():
    agent = make_agent(["AAPL"])
    agent._fetch_ticker_history = MagicMock(return_value=pd.DataFrame())
    await agent.run_once()
    agent.db.executemany.assert_not_called()
    agent.bus.publish.assert_called_once()
