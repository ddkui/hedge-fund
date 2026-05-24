# tests/gateway/test_signals.py
import pytest


@pytest.mark.asyncio
async def test_get_signals_returns_recent(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "aggregator", "symbol": "AAPL", "signal_type": "bullish",
         "confidence": 72.0, "reasoning": "strong trend", "time": "2026-05-24T10:00:00+00:00",
         "metadata": None},
    ]
    resp = await client.get("/signals")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_signals_for_symbol(client, mock_db):
    mock_db.fetch.return_value = []
    resp = await client.get("/signals/AAPL")
    assert resp.status_code == 200
    assert resp.json() == []
