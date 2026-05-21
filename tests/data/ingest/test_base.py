import pytest
from unittest.mock import AsyncMock
from data.ingest.base import DataIngestAgent
from datetime import datetime, timezone


class ConcreteIngestAgent(DataIngestAgent):
    async def run_once(self):
        pass


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return ConcreteIngestAgent(
        name="test_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
    )


@pytest.mark.asyncio
async def test_store_prices_calls_executemany():
    agent = make_agent()
    rows = [
        {
            "time": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            "symbol": "AAPL",
            "asset_class": "stock",
            "open": 150.0,
            "high": 151.0,
            "low": 149.0,
            "close": 150.5,
            "volume": 1_000_000.0,
        }
    ]
    await agent.store_prices(rows)
    agent.db.executemany.assert_called_once()
    call_args = agent.db.executemany.call_args
    assert "INSERT INTO prices" in call_args[0][0]
    assert len(call_args[0][1]) == 1
    record = call_args[0][1][0]
    assert record[1] == "AAPL"
    assert record[2] == "stock"
    assert record[6] == 150.5


@pytest.mark.asyncio
async def test_store_prices_empty_list_skips_db():
    agent = make_agent()
    await agent.store_prices([])
    agent.db.executemany.assert_not_called()


@pytest.mark.asyncio
async def test_store_prices_with_missing_optional_fields():
    agent = make_agent()
    rows = [
        {
            "time": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            "symbol": "BTC",
            "asset_class": "crypto",
            "close": 42000.0,
        }
    ]
    await agent.store_prices(rows)
    agent.db.executemany.assert_called_once()
    record = agent.db.executemany.call_args[0][1][0]
    assert record[3] is None   # open
    assert record[4] is None   # high
    assert record[5] is None   # low
    assert record[7] is None   # volume
    assert record[6] == 42000.0  # close is present
