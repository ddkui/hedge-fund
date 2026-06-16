import pytest
from unittest.mock import MagicMock, patch
from shared.agent_memory import AgentStats, AgentMemory


def test_agent_stats_win_rate():
    stats = AgentStats(agent="research", regime="expansion", winning_signals=7, losing_signals=3, total_signals=10)
    assert stats.win_rate == pytest.approx(0.7)


def test_agent_stats_win_rate_no_signals():
    stats = AgentStats(agent="research", regime="expansion")
    assert stats.win_rate == 0.0


def test_agent_stats_confidence_multiplier_insufficient_data():
    stats = AgentStats(agent="research", regime="expansion", total_signals=5, winning_signals=5, losing_signals=0)
    assert stats.confidence_multiplier == 1.0


def test_agent_stats_confidence_multiplier_in_valid_range():
    stats = AgentStats(
        agent="research", regime="expansion",
        winning_signals=70, losing_signals=30, total_signals=100,
    )
    mult = stats.confidence_multiplier
    assert 0.6 <= mult <= 1.4


def test_agent_memory_update_and_retrieve():
    memory = AgentMemory()
    memory.update_signal_outcome("research", "expansion", won=True)
    memory.update_signal_outcome("research", "expansion", won=False)
    stats_list = memory.get_stats("research", "expansion")
    assert len(stats_list) == 1
    assert stats_list[0].total_signals == 2
    assert stats_list[0].winning_signals == 1
    assert stats_list[0].losing_signals == 1


def test_agent_memory_get_confidence_multiplier_no_data():
    memory = AgentMemory()
    assert memory.get_confidence_multiplier("unknown_agent", "expansion") == 1.0


def test_agent_memory_confidence_interval_sufficient_data():
    memory = AgentMemory()
    for _ in range(70):
        memory.update_signal_outcome("research", "expansion", won=True)
    for _ in range(30):
        memory.update_signal_outcome("research", "expansion", won=False)
    lower, upper = memory.get_confidence_interval("research", "expansion")
    assert lower < upper
    assert 0.0 <= lower <= 1.0
    assert 0.0 <= upper <= 1.0


def test_agent_memory_confidence_interval_no_data():
    memory = AgentMemory()
    lower, upper = memory.get_confidence_interval("unknown", "expansion")
    assert lower == pytest.approx(0.0)
    assert upper == pytest.approx(1.0)


def test_agent_memory_redis_fallback_on_unavailable():
    memory = AgentMemory(redis_url="redis://nonexistent-host-12345:9999")
    memory.update_signal_outcome("research", "expansion", won=True)
    assert memory.get_confidence_multiplier("research", "expansion") == 1.0  # <10 signals


def test_agent_memory_redis_persists_on_update():
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.hgetall.return_value = {}
    mock_redis.hset.return_value = 1

    with patch("shared.agent_memory.redis.from_url", return_value=mock_redis):
        memory = AgentMemory(redis_url="redis://localhost:6379")
        memory.update_signal_outcome("research", "expansion", won=True)

    mock_redis.hset.assert_called_once()
    call_kwargs = mock_redis.hset.call_args
    assert "mapping" in call_kwargs[1]
    mapping = call_kwargs[1]["mapping"]
    assert int(mapping["total_signals"]) == 1
    assert int(mapping["winning_signals"]) == 1


def test_agent_memory_loads_from_redis_on_miss():
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.hgetall.return_value = {
        "total_signals": "100",
        "winning_signals": "65",
        "losing_signals": "35",
        "last_updated": "2024-01-01T00:00:00+00:00",
    }

    with patch("shared.agent_memory.redis.from_url", return_value=mock_redis):
        memory = AgentMemory(redis_url="redis://localhost:6379")
        stats_list = memory.get_stats("research", "expansion")

    assert len(stats_list) == 1
    assert stats_list[0].winning_signals == 65
