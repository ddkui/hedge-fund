import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from shared.model_router import ModelRouter, AGENT_MODEL_MAP


@pytest.mark.asyncio
async def test_router_returns_primary_when_healthy():
    mock_router = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="response"))]
    mock_router.acompletion = AsyncMock(return_value=mock_response)

    with patch("shared.model_router.Router", return_value=mock_router):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434",
        )
        result = await router.chat("portfolio_mgr", [{"role": "user", "content": "hello"}])
        assert result == "response"
        called_model = mock_router.acompletion.call_args[1]["model"]
        assert called_model == "primary"


@pytest.mark.asyncio
async def test_router_uses_research_slot_for_research_agents():
    mock_router = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="research response"))]
    mock_router.acompletion = AsyncMock(return_value=mock_response)

    with patch("shared.model_router.Router", return_value=mock_router):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434",
            research_model="mistral:7b",
        )
        result = await router.chat("research", [{"role": "user", "content": "hello"}])
        assert result == "research response"
        called_model = mock_router.acompletion.call_args[1]["model"]
        assert called_model == "research_model"


def test_router_model_for_agent_type():
    with patch("shared.model_router.Router"):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434",
            research_model="mistral:7b",
        )
    assert router.model_for("research") == "mistral:7b"
    assert router.model_for("portfolio_mgr") == "llama3.1:8b"
    assert router.model_for("unknown") == "llama3.1:8b"


@pytest.mark.asyncio
async def test_router_raises_when_all_models_fail():
    mock_router = MagicMock()
    mock_router.acompletion = AsyncMock(side_effect=Exception("all models unavailable"))

    with patch("shared.model_router.Router", return_value=mock_router):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434",
        )
        with pytest.raises(Exception, match="all models unavailable"):
            await router.chat("portfolio_mgr", [{"role": "user", "content": "hello"}])


def test_router_agent_map_coverage():
    """Every agent type in AGENT_MODEL_MAP routes to a valid model slot."""
    with patch("shared.model_router.Router"):
        router = ModelRouter(
            primary="llama3.1:8b",
            shadow="phi3:mini",
            host="http://localhost:11434",
            research_model="mistral:7b",
        )
    for agent in AGENT_MODEL_MAP:
        model = router.model_for(agent)
        assert model in {"llama3.1:8b", "mistral:7b"}, f"{agent} mapped to unexpected model {model}"
