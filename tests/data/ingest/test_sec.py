import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.sec import SecIngestAgent

TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}

SUBMISSIONS_JSON = {
    "filings": {
        "recent": {
            "form": ["10-K", "8-K", "10-Q"],
            "filingDate": ["2024-01-01", "2024-01-15", "2023-10-01"],
            "accessionNumber": ["0000320193-24-000001", "0000320193-24-000002", "0000320193-23-000003"],
            "reportDate": ["2023-09-30", "", "2023-06-30"],
        }
    }
}


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return SecIngestAgent(
        name="sec_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        watchlist=["AAPL"],
        interval_seconds=3600,
    )


def make_mock_client(tickers_json, submissions_json):
    mock_client = AsyncMock()

    async def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = 200
        if "company_tickers" in url:
            resp.json.return_value = tickers_json
        else:
            resp.json.return_value = submissions_json
        return resp

    mock_client.get = mock_get
    return mock_client


@pytest.mark.asyncio
async def test_sec_agent_loads_cik_on_first_run():
    agent = make_agent()
    mock_client = make_mock_client(TICKERS_JSON, SUBMISSIONS_JSON)

    with patch("data.ingest.sec.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    assert agent._ticker_cik.get("AAPL") == "0000320193"


@pytest.mark.asyncio
async def test_sec_agent_stores_filings():
    agent = make_agent()
    mock_client = make_mock_client(TICKERS_JSON, SUBMISSIONS_JSON)

    with patch("data.ingest.sec.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_called_once()
    call_args = agent.db.executemany.call_args
    assert "INSERT INTO sec_filings" in call_args[0][0]
    records = call_args[0][1]
    form_types = {r[2] for r in records}
    assert "10-K" in form_types
    assert "10-Q" in form_types
    assert "8-K" in form_types


@pytest.mark.asyncio
async def test_sec_agent_publishes_update():
    agent = make_agent()
    mock_client = make_mock_client(TICKERS_JSON, SUBMISSIONS_JSON)

    with patch("data.ingest.sec.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.sec.updated"
    assert "AAPL" in call[0][1]["tickers"]
