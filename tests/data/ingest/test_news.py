import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.news import NewsIngestAgent

NEWSAPI_RESPONSE = {
    "articles": [
        {
            "source": {"name": "Reuters"},
            "title": "Markets rally on rate cut hopes",
            "url": "https://reuters.com/article/1",
            "publishedAt": "2024-01-15T10:30:00Z",
        },
        {
            "source": {"name": "Bloomberg"},
            "title": "Bitcoin surges past 50k",
            "url": "https://bloomberg.com/article/2",
            "publishedAt": "2024-01-15T09:00:00Z",
        },
    ]
}


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return NewsIngestAgent(
        name="news_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        api_key="testkey",
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_news_agent_stores_articles():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = NEWSAPI_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.news.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_called_once()
    call = agent.db.executemany.call_args
    assert "INSERT INTO news_items" in call[0][0]
    records = call[0][1]
    assert len(records) == 2
    assert records[0][2] == "Markets rally on rate cut hopes"
    assert records[1][1] == "Bloomberg"


@pytest.mark.asyncio
async def test_news_agent_publishes_update():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = NEWSAPI_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.news.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.news.updated"
    assert call[0][1]["article_count"] == 2


@pytest.mark.asyncio
async def test_news_agent_handles_empty_response():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"articles": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.news.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_not_called()
    agent.bus.publish.assert_called_once()
