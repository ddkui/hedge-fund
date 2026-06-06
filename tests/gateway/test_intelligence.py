# tests/gateway/test_intelligence.py
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_intelligence_status_returns_tier(client, mock_bus):
    mock_bus.get = AsyncMock(return_value={
        "tier": "learning", "sharpe": 0.87, "jensens_alpha": 1.2,
        "beta": 0.94, "portfolio_annual_pct": 12.0, "spy_annual_pct": 10.0
    })
    resp = await client.get("/intelligence/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "learning"
    assert data["sharpe"] == 0.87


@pytest.mark.asyncio
async def test_intelligence_proposals_returns_pending(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "agent": "vwap", "regime": "expansion", "param_name": "deviation_threshold_pct",
         "current_value": 1.5, "proposed_value": 2.1, "change_pct": 40.0,
         "reason": "accuracy 38%", "status": "pending", "time": "2026-06-06T00:00:00+00:00"}
    ]
    resp = await client.get("/intelligence/proposals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["agent"] == "vwap"


@pytest.mark.asyncio
async def test_approve_nonexistent_proposal_returns_404(client, mock_db):
    mock_db.fetchrow = AsyncMock(return_value=None)
    resp = await client.post("/intelligence/proposals/999/approve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_proposal_updates_status(client, mock_db):
    mock_db.fetchrow = AsyncMock(return_value={"id": 1})
    mock_db.execute = AsyncMock()
    resp = await client.post("/intelligence/proposals/1/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_accuracy_returns_list(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "vwap", "signals": 50, "accuracy": 0.6, "avg_pnl": 25.0},
    ]
    resp = await client.get("/intelligence/accuracy")
    assert resp.status_code == 200
    assert resp.json()[0]["agent"] == "vwap"
