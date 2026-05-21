import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from shared.model_router import ModelRouter

@pytest.mark.asyncio
async def test_router_returns_primary_when_healthy():
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value=MagicMock(
        message=MagicMock(content="response")
    ))
    with patch("shared.model_router.AsyncClient", return_value=mock_client):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434"
        )
        result = await router.chat("portfolio_mgr", [{"role": "user", "content": "hello"}])
        assert result == "response"
        call_model = mock_client.chat.call_args[1]["model"]
        assert call_model == "llama3.1:8b"

@pytest.mark.asyncio
async def test_router_falls_back_to_shadow_on_failure():
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(side_effect=[
        Exception("primary model unavailable"),
        MagicMock(message=MagicMock(content="fallback response"))
    ])
    with patch("shared.model_router.AsyncClient", return_value=mock_client):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434"
        )
        result = await router.chat("portfolio_mgr", [{"role": "user", "content": "hello"}])
        assert result == "fallback response"
        assert mock_client.chat.call_count == 2
        fallback_model = mock_client.chat.call_args[1]["model"]
        assert fallback_model == "phi3:mini"

@pytest.mark.asyncio
async def test_router_model_for_agent_type():
    router = ModelRouter(
        primary="llama3.1:8b",
        shadow="phi3:mini",
        host="http://localhost:11434",
        research_model="mistral:7b"
    )
    assert router.model_for("research") == "mistral:7b"
    assert router.model_for("portfolio_mgr") == "llama3.1:8b"
    assert router.model_for("unknown") == "llama3.1:8b"
