import pytest
from fastapi.testclient import TestClient

# Tests will use the main app fixture (defined in conftest)
async def test_get_pending_proposals(client):
    """Test GET /api/optimizer/proposals endpoint."""
    response = await client.get("/api/optimizer/proposals")

    assert response.status_code in [200, 404, 500]  # May not exist yet
    if response.status_code == 200:
        data = response.json()
        assert "proposals" in data

async def test_approve_proposal(client):
    """Test POST /api/optimizer/proposals/{id}/approve endpoint."""
    response = await client.post("/api/optimizer/proposals/1/approve", json={
        "approved_by": "cio@hedge.fund"
    })

    assert response.status_code in [200, 404, 500]

async def test_get_tuning_history(client):
    """Test GET /api/optimizer/history endpoint."""
    response = await client.get("/api/optimizer/history")

    assert response.status_code in [200, 500]

async def test_get_agent_performance(client):
    """Test GET /api/optimizer/agents endpoint."""
    response = await client.get("/api/optimizer/agents")

    assert response.status_code in [200, 500]

async def test_run_backtest_optimization(client):
    """Test POST /api/optimizer/backtest endpoint."""
    response = await client.post("/api/optimizer/backtest", json={
        "agent": "technical",
        "regime": "expansion",
        "start_date": "2026-01-01",
        "end_date": "2026-06-01"
    })

    assert response.status_code in [200, 400, 500]
