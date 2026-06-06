# tests/gateway/test_metrics.py
import pytest
from unittest.mock import AsyncMock


def _make_fetch_side_effect(agent_rows, trade_rows=None, signal_rows=None, pending=None):
    """Return side_effect list for the 4 db.fetch calls in _collect()."""
    return [
        agent_rows,
        trade_rows or [],
        signal_rows or [],
        pending or [{"cnt": 0}],
    ]


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(client, mock_db):
    mock_db.fetch.side_effect = _make_fetch_side_effect(
        agent_rows=[{"agent": "technical", "status": "healthy"}],
    )
    mock_db.fetchrow.return_value = {
        "total_value": 105000.0, "cash": 80000.0, "open_positions": 3, "peak_value": 106000.0
    }
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "hf_agent_up" in body
    assert "hf_portfolio_value_usd" in body
    assert "hf_open_positions_count" in body


@pytest.mark.asyncio
async def test_metrics_agent_up_reflects_health(client, mock_db):
    mock_db.fetch.side_effect = _make_fetch_side_effect(
        agent_rows=[
            {"agent": "technical", "status": "healthy"},
            {"agent": "execution", "status": "down"},
        ],
    )
    mock_db.fetchrow.return_value = {
        "total_value": 100000.0, "cash": 100000.0,
        "open_positions": 0, "peak_value": 100000.0
    }
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert 'hf_agent_up{agent="technical"} 1.0' in body
    assert 'hf_agent_up{agent="execution"} 0.0' in body


@pytest.mark.asyncio
async def test_metrics_portfolio_value_present(client, mock_db):
    mock_db.fetch.side_effect = _make_fetch_side_effect(agent_rows=[])
    mock_db.fetchrow.return_value = {
        "total_value": 123456.78, "cash": 50000.0, "open_positions": 2, "peak_value": 125000.0
    }
    resp = await client.get("/metrics")
    assert "123456.78" in resp.text
