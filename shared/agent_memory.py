# shared/agent_memory.py
"""
Persistent agent memory - stores signal win rates per agent per regime.
Agents adjust confidence dynamically based on historical accuracy.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AgentStats:
    agent: str
    regime: str
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def win_rate(self) -> float:
        """Calculate win rate (0.0 to 1.0)."""
        total = self.winning_signals + self.losing_signals
        if total == 0:
            return 0.0
        return self.winning_signals / total

    @property
    def confidence_multiplier(self) -> float:
        """
        Adjust agent confidence based on historical win rate.
        Agents with poor record get penalized.
        """
        if self.total_signals < 10:
            # Not enough data yet, neutral multiplier
            return 1.0

        if self.win_rate >= 0.70:
            return 1.3  # Strong track record: boost confidence
        elif self.win_rate >= 0.60:
            return 1.1  # Good: slight boost
        elif self.win_rate >= 0.45:
            return 1.0  # Average: neutral
        elif self.win_rate >= 0.35:
            return 0.8  # Poor: reduce confidence
        else:
            return 0.6  # Very poor: significant penalty


class AgentMemory:
    def __init__(self):
        self.stats: dict[tuple[str, str], AgentStats] = {}

    def update_signal_outcome(
        self,
        agent: str,
        regime: str,
        won: bool,
    ) -> None:
        """Record signal outcome (win or loss)."""
        key = (agent, regime)
        if key not in self.stats:
            self.stats[key] = AgentStats(agent=agent, regime=regime)

        stats = self.stats[key]
        stats.total_signals += 1
        if won:
            stats.winning_signals += 1
        else:
            stats.losing_signals += 1
        stats.last_updated = datetime.now(timezone.utc)

    def get_confidence_multiplier(self, agent: str, regime: str) -> float:
        """Get multiplier for agent confidence in regime."""
        key = (agent, regime)
        if key not in self.stats:
            return 1.0
        return self.stats[key].confidence_multiplier

    def get_stats(self, agent: str = None, regime: str = None) -> list[AgentStats]:
        """Get stats filtered by agent/regime."""
        stats = list(self.stats.values())
        if agent:
            stats = [s for s in stats if s.agent == agent]
        if regime:
            stats = [s for s in stats if s.regime == regime]
        return stats
