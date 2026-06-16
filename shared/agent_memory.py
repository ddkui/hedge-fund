# shared/agent_memory.py
"""
Persistent agent memory - stores signal win rates per agent per regime.
Confidence adjusted via Thompson Sampling (Beta posterior); stats persisted in Redis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]


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
        total = self.winning_signals + self.losing_signals
        if total == 0:
            return 0.0
        return self.winning_signals / total

    @property
    def confidence_multiplier(self) -> float:
        """Thompson Sampling: draw from Beta(wins+1, losses+1), map to [0.6, 1.4]."""
        if self.total_signals < 10:
            return 1.0
        from scipy.stats import beta as beta_dist
        sampled = float(beta_dist.rvs(self.winning_signals + 1, self.losing_signals + 1))
        return round(0.6 + 0.8 * sampled, 4)


class AgentMemory:
    def __init__(self, redis_url: Optional[str] = None):
        self.stats: dict[tuple[str, str], AgentStats] = {}
        self._redis = None
        if redis_url and redis is not None:
            try:
                client = redis.from_url(redis_url, decode_responses=True)
                client.ping()
                self._redis = client
            except Exception:
                pass  # graceful fallback to in-memory

    def _redis_key(self, agent: str, regime: str) -> str:
        return f"agent_memory:{agent}:{regime}"

    def _load_from_redis(self, agent: str, regime: str) -> Optional[AgentStats]:
        if not self._redis:
            return None
        try:
            data = self._redis.hgetall(self._redis_key(agent, regime))
            if not data:
                return None
            return AgentStats(
                agent=agent,
                regime=regime,
                total_signals=int(data.get("total_signals", 0)),
                winning_signals=int(data.get("winning_signals", 0)),
                losing_signals=int(data.get("losing_signals", 0)),
            )
        except Exception:
            return None

    def _persist(self, s: AgentStats) -> None:
        if not self._redis:
            return
        try:
            self._redis.hset(
                self._redis_key(s.agent, s.regime),
                mapping={
                    "total_signals": s.total_signals,
                    "winning_signals": s.winning_signals,
                    "losing_signals": s.losing_signals,
                    "last_updated": s.last_updated.isoformat(),
                },
            )
        except Exception:
            pass

    def update_signal_outcome(self, agent: str, regime: str, won: bool) -> None:
        key = (agent, regime)
        if key not in self.stats:
            loaded = self._load_from_redis(agent, regime)
            self.stats[key] = loaded or AgentStats(agent=agent, regime=regime)
        s = self.stats[key]
        s.total_signals += 1
        if won:
            s.winning_signals += 1
        else:
            s.losing_signals += 1
        s.last_updated = datetime.now(timezone.utc)
        self._persist(s)

    def get_confidence_multiplier(self, agent: str, regime: str) -> float:
        key = (agent, regime)
        if key not in self.stats:
            loaded = self._load_from_redis(agent, regime)
            if loaded:
                self.stats[key] = loaded
        if key not in self.stats:
            return 1.0
        return self.stats[key].confidence_multiplier

    def get_stats(self, agent: Optional[str] = None, regime: Optional[str] = None) -> list[AgentStats]:
        if agent and regime:
            key = (agent, regime)
            if key not in self.stats:
                loaded = self._load_from_redis(agent, regime)
                if loaded:
                    self.stats[key] = loaded
        result = list(self.stats.values())
        if agent:
            result = [s for s in result if s.agent == agent]
        if regime:
            result = [s for s in result if s.regime == regime]
        return result

    def get_confidence_interval(self, agent: str, regime: str) -> tuple[float, float]:
        """95% credible interval from Beta posterior over win probability."""
        key = (agent, regime)
        if key not in self.stats:
            loaded = self._load_from_redis(agent, regime)
            if loaded:
                self.stats[key] = loaded
        s = self.stats.get(key)
        if s is None or s.total_signals < 2:
            return (0.0, 1.0)
        from scipy.stats import beta as beta_dist
        lo = float(beta_dist.ppf(0.025, s.winning_signals + 1, s.losing_signals + 1))
        hi = float(beta_dist.ppf(0.975, s.winning_signals + 1, s.losing_signals + 1))
        return (round(lo, 4), round(hi, 4))
