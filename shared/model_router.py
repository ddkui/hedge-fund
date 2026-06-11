from ollama import AsyncClient
from shared.logging import get_logger

logger = get_logger("model_router")

AGENT_MODEL_MAP = {
    "research": "research_model",
    "macro": "research_model",
    "sentiment": "research_model",
    "options": "research_model",
    "portfolio_researcher": "research_model",
    "quant_supervisor": "research_model",
    "portfolio_mgr": "primary",
    "cio": "primary",
    "hermes": "primary",
}

class ModelRouter:
    def __init__(
        self,
        primary: str,
        shadow: str,
        host: str,
        research_model: str | None = None,
    ):
        self._primary = primary
        self._shadow = shadow
        self._research = research_model or primary
        self._client = AsyncClient(host=host)

    def model_for(self, agent_type: str) -> str:
        slot = AGENT_MODEL_MAP.get(agent_type, "primary")
        return {"primary": self._primary, "research_model": self._research}.get(slot, self._primary)

    async def chat(self, agent_type: str, messages: list[dict], **kwargs) -> str:
        model = self.model_for(agent_type)
        try:
            response = await self._client.chat(model=model, messages=messages, **kwargs)
            return response.message.content
        except Exception as e:
            logger.warning("primary_model_failed", model=model, error=str(e))
            response = await self._client.chat(model=self._shadow, messages=messages, **kwargs)
            return response.message.content
