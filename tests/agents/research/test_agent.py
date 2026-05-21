import pytest
from unittest.mock import AsyncMock
from agents.research.agent import FundamentalResearchAgent

SEC_ROWS = [
    {"ticker": "AAPL", "form_type": "10-K", "period": "2023-09-30",
     "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm",
     "time": None},
    {"ticker": "MSFT", "form_type": "10-Q", "period": "2023-12-31",
     "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901924000013/0000789019-24-000013-index.htm",
     "time": None},
]


def make_agent():
    return FundamentalResearchAgent(
        name="research",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=3600,
    )


@pytest.mark.asyncio
async def test_research_agent_stores_signal_per_ticker():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SEC_ROWS)
    agent._fetch_filing_text = AsyncMock(return_value="Apple Inc. reported strong revenue growth...")
    agent.router.chat = AsyncMock(return_value='{"quality_score": 85, "moat": "strong", "thesis": "Growth driven by services", "risks": "Supply chain"}')
    await agent.run_once()
    assert agent.db.execute.call_count >= 1


@pytest.mark.asyncio
async def test_research_agent_publishes_fundamental_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[SEC_ROWS[0]])
    agent._fetch_filing_text = AsyncMock(return_value="Fiscal year revenue exceeded expectations...")
    agent.router.chat = AsyncMock(return_value='{"quality_score": 78, "moat": "moderate", "thesis": "Steady growth", "risks": "Competition"}')
    await agent.run_once()
    agent.bus.publish.assert_called()
    channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.research" in c for c in channels)


@pytest.mark.asyncio
async def test_research_agent_handles_no_filings():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_research_agent_skips_on_fetch_failure():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[SEC_ROWS[0]])
    agent._fetch_filing_text = AsyncMock(return_value=None)
    agent.router.chat = AsyncMock()
    await agent.run_once()
    agent.router.chat.assert_not_called()
    agent.db.execute.assert_not_called()
