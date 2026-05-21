import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.social import SocialIngestAgent

FAKE_POSTS = [
    {"id": "abc123", "title": "GME to the moon", "score": 5000, "subreddit": "wallstreetbets", "url": "https://reddit.com/abc", "created_utc": 1704067200.0},
    {"id": "def456", "title": "Bitcoin analysis", "score": 1200, "subreddit": "CryptoCurrency", "url": "https://reddit.com/def", "created_utc": 1704070800.0},
]


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return SocialIngestAgent(
        name="social_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        client_id="test_id",
        client_secret="test_secret",
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_social_agent_publishes_posts():
    agent = make_agent()
    agent._fetch_posts = MagicMock(return_value=FAKE_POSTS)

    await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.social.updated"
    assert call[0][1]["post_count"] == 2
    assert call[0][1]["source"] == "reddit"


@pytest.mark.asyncio
async def test_social_agent_publishes_posts_content():
    agent = make_agent()
    agent._fetch_posts = MagicMock(return_value=FAKE_POSTS)

    await agent.run_once()

    call = agent.bus.publish.call_args
    posts = call[0][1]["posts"]
    assert posts[0]["title"] == "GME to the moon"
    assert posts[1]["subreddit"] == "CryptoCurrency"


@pytest.mark.asyncio
async def test_social_agent_handles_empty_feed():
    agent = make_agent()
    agent._fetch_posts = MagicMock(return_value=[])

    await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][1]["post_count"] == 0
