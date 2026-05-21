import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.macro import MacroIngestAgent

FRED_RESPONSE = {
    "observations": [
        {"date": "2024-01-01", "value": "5.33"},
        {"date": "2023-12-01", "value": "5.33"},
    ]
}


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return MacroIngestAgent(
        name="macro_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        api_key="testkey",
        interval_seconds=3600,
    )


@pytest.mark.asyncio
async def test_macro_agent_stores_observations():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = FRED_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.macro.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    assert agent.db.executemany.call_count >= 1
    first_call = agent.db.executemany.call_args_list[0]
    assert "INSERT INTO macro_data" in first_call[0][0]
    records = first_call[0][1]
    assert len(records) == 2
    assert records[0][1] == "FEDFUNDS"
    assert records[0][2] == 5.33


@pytest.mark.asyncio
async def test_macro_agent_skips_missing_values():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {"date": "2024-01-01", "value": "."},
            {"date": "2023-12-01", "value": "5.33"},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.macro.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    first_call = agent.db.executemany.call_args_list[0]
    records = first_call[0][1]
    assert len(records) == 1
    assert records[0][2] == 5.33


@pytest.mark.asyncio
async def test_macro_agent_publishes_update():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = FRED_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.macro.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.macro.updated"
    assert "FEDFUNDS" in call[0][1]["series"]
