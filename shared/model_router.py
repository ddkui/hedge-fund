import litellm
from litellm import Router
from shared.logging import get_logger

logger = get_logger("model_router")

litellm.drop_params = True  # silently ignore unsupported provider params

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

        def _entry(slot: str, model_name: str) -> dict:
            return {
                "model_name": slot,
                "litellm_params": {
                    "model": f"ollama/{model_name}",
                    "api_base": host,
                },
            }

        self._router = Router(
            model_list=[
                _entry("primary", primary),
                _entry("shadow", shadow),
                _entry("research_model", self._research),
            ],
            fallbacks=[{"primary": ["shadow"]}, {"research_model": ["shadow"]}],
            num_retries=3,
        )

    def model_for(self, agent_type: str) -> str:
        slot = AGENT_MODEL_MAP.get(agent_type, "primary")
        return {"primary": self._primary, "research_model": self._research}.get(slot, self._primary)

    async def chat(self, agent_type: str, messages: list[dict], **kwargs) -> str:
        slot = AGENT_MODEL_MAP.get(agent_type, "primary")
        response = await self._router.acompletion(model=slot, messages=messages)
        content = response.choices[0].message.content
        try:
            cost = litellm.completion_cost(completion_response=response)
            logger.info("llm_cost", agent=agent_type, cost_usd=round(cost, 6))
        except Exception:
            pass
        return content
