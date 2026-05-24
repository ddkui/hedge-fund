# tests/gateway/test_trades.py
import pytest


@pytest.mark.asyncio
async def test_get_pending_trades(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 5, "symbol": "TSLA", "action": "long", "quantity": 5.0,
         "price": 200.0, "paper": True, "status": "pending",
         "confidence": 55.0, "pm_reasoning": "moderate signal",
         "time": "2026-05-24T10:00:00+00:00", "position_id": None},
    ]
    resp = await client.get("/trades/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_trade_updates_status(client, mock_db):
    mock_db.fetchrow.return_value = {"id": 5, "status": "pending"}
    resp = await client.post("/trades/5/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_deny_trade_updates_status(client, mock_db):
    mock_db.fetchrow.return_value = {"id": 5, "status": "pending"}
    resp = await client.post("/trades/5/deny")
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


@pytest.mark.asyncio
async def test_approve_nonexistent_trade_returns_404(client, mock_db):
    mock_db.fetchrow.return_value = None
    resp = await client.post("/trades/999/approve")
    assert resp.status_code == 404
