from shared.agent_base import BaseAgent
from agents.hermes.nous_bridge import NousBridge


class HermesAgent(BaseAgent):
    """
    Self-improvement meta-agent.

    With NOUS_ENABLED=1: uses Nous Hermes AIAgent to analyse win rates,
    tune aggregator weights, and propose code improvements via tool calls.
    Without it (default): falls back to the rule-based analyzer + coder.
    """

    def __init__(self, *args, params_path: str = "agent_params.yaml", **kwargs):
        super().__init__(*args, **kwargs)
        self._bridge = NousBridge(
            db=self.db,
            bus=self.bus,
            router=self.router,
            logger=self.logger,
            params_path=params_path,
        )

    async def run_once(self) -> None:
        result = await self._bridge.run_cycle()

        await self.bus.publish("ops.hermes", {
            "agent": self.name,
            "cycle_time": self._now().isoformat(),
            **result,
        })

        self.logger.info(
            "hermes_cycle_complete",
            outcomes_analyzed=result["outcomes_analyzed"],
            weights_applied=result["weights_applied"],
            proposals_queued=result["proposals_queued"],
            patches_queued=result["patches_queued"],
        )
