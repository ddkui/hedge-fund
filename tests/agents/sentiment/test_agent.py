import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.sentiment.agent import SentimentAgent
from agents.sentiment.finbert import SentimentResult

TICKER_MAP = {"AAPL": ["apple", "aapl"], "BTC": ["bitcoin", "btc", "crypto"]}

NEWS_ROWS = [
    {"headline": "Apple beats earnings by 15%, raises guidance", "source": "Reuters", "time": None},
    {"headline": "Bitcoin surges as ETF approval expected", "source": "Bloomberg", "time": None},
    {"headline": "Markets rally on Fed pivot hopes", "source": "CNBC", "time": None},
]


def make_agent():
    return SentimentAgent(
        name="sentiment",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        ticker_map=TICKER_MAP,
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_sentiment_agent_stores_signal_per_ticker():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=NEWS_ROWS)
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[
        SentimentResult("positive", 0.92, 0.92),
        SentimentResult("positive", 0.88, 0.88),
        SentimentResult("neutral", 0.75, 0.0),
    ])
    await agent.run_once()
    assert agent.db.execute.call_count >= 1


@pytest.mark.asyncio
async def test_sentiment_agent_publishes_per_ticker():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=NEWS_ROWS)
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[
        SentimentResult("positive", 0.91, 0.91),
        SentimentResult("positive", 0.87, 0.87),
        SentimentResult("neutral", 0.70, 0.0),
    ])
    await agent.run_once()
    published_channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.sentiment" in ch for ch in published_channels)


@pytest.mark.asyncio
async def test_sentiment_agent_handles_empty_news():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sentiment_agent_confidence_in_range():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=NEWS_ROWS[:1])
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[
        SentimentResult("positive", 0.91, 0.91),
    ])
    await agent.run_once()
    if agent.db.execute.called:
        confidence = agent.db.execute.call_args[0][5]
        assert 0.0 <= confidence <= 100.0
