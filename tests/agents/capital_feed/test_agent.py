# tests/agents/capital_feed/test_agent.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_capital_feed_agent_starts_feed():
    """main() creates CapitalPriceFeed and calls run()."""
    mock_settings = MagicMock()
    mock_settings.capital_com_api_key = "key"
    mock_settings.capital_com_identifier = "test@example.com"
    mock_settings.capital_com_password = "pass"
    mock_settings.capital_com_demo = True
    mock_settings.capital_com_base_url = "https://demo-api-capital.backend.gbksoft.net"
    mock_settings.capital_com_watchlist = "GOLD,EURUSD"
    mock_settings.db_dsn = "postgresql://x"

    mock_session = AsyncMock()
    mock_feed = AsyncMock()
    mock_feed.run = AsyncMock(side_effect=asyncio.CancelledError)
    mock_db = AsyncMock()

    with patch("agents.capital_feed.agent.settings", mock_settings), \
         patch("agents.capital_feed.agent.CapitalComSession", return_value=mock_session), \
         patch("agents.capital_feed.agent.CapitalPriceFeed", return_value=mock_feed), \
         patch("agents.capital_feed.agent.Database", return_value=mock_db):
        try:
            from agents.capital_feed.agent import main
            await main()
        except asyncio.CancelledError:
            pass

    mock_session.connect.assert_called_once()
    mock_feed.run.assert_called_once()


@pytest.mark.asyncio
async def test_capital_feed_agent_exits_if_not_configured():
    """main() exits early when capital_com_api_key is empty."""
    mock_settings = MagicMock()
    mock_settings.capital_com_api_key = ""

    with patch("agents.capital_feed.agent.settings", mock_settings), \
         patch("agents.capital_feed.agent.CapitalComSession") as mock_session_cls:
        from agents.capital_feed.agent import main
        await main()

    mock_session_cls.assert_not_called()
