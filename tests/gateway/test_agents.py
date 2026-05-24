# tests/gateway/test_agents.py
import pytest


@pytest.mark.asyncio
async def test_get_agent_health(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "technical", "status": "healthy",
         "time": "2026-05-24T10:00:00+00:00", "message": None, "metadata": None},
    ]
    resp = await client.get("/agents/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["agent"] == "technical"
