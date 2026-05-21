import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from data.ingest.crypto import CryptoIngestAgent

BINANCE_KLINE = [
    1704067200000,  # open time ms
    "42000.00",     # open
    "42500.00",     # high
    "41800.00",     # low
    "42200.00",     # close
    "100.5",        # volume
    1704067259999,  # close time ms
    "4221000.00",   # quote asset volume
    150,            # number of trades
    "60.0",         # taker buy base
    "2532000.00",   # taker buy quote
    "0",            # ignore
]


def make_agent(watchlist=None):
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return CryptoIngestAgent(
        name="crypto_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        watchlist=watchlist or ["BTCUSDT"],
        interval_seconds=30,
    )


@pytest.mark.asyncio
async def test_crypto_agent_fetches_binance_and_stores():
    agent = make_agent(["BTCUSDT"])

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [BINANCE_KLINE]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.crypto.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_called_once()
    records = agent.db.executemany.call_args[0][1]
    assert len(records) == 1
    assert records[0][1] == "BTCUSDT"
    assert records[0][2] == "crypto"
    assert records[0][6] == 42200.0


@pytest.mark.asyncio
async def test_crypto_agent_publishes_update():
    agent = make_agent(["BTCUSDT", "ETHUSDT"])

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [BINANCE_KLINE]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.crypto.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.crypto.updated"
    assert set(call[0][1]["symbols"]) == {"BTCUSDT", "ETHUSDT"}


@pytest.mark.asyncio
async def test_crypto_agent_calls_correct_url():
    agent = make_agent(["SOLUSDT"])

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = []

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.crypto.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    call = mock_client.get.call_args
    assert "binance.com" in call[0][0]
    assert call[1]["params"]["symbol"] == "SOLUSDT"
    assert call[1]["params"]["interval"] == "1m"
