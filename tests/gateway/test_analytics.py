# tests/gateway/test_analytics.py
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_summary_returns_metrics(client, mock_db):
    mock_db.fetch.side_effect = [
        [
            {"time": "2026-06-01T00:00:00+00:00", "total_value": 100000.0},
            {"time": "2026-06-02T00:00:00+00:00", "total_value": 101500.0},
            {"time": "2026-06-03T00:00:00+00:00", "total_value": 103000.0},
            {"time": "2026-06-04T00:00:00+00:00", "total_value": 102000.0},
            {"time": "2026-06-05T00:00:00+00:00", "total_value": 104000.0},
        ],
        [
            {"symbol": "AAPL", "action": "long", "quantity": 10.0, "price": 180.0,
             "entry_price": 175.0, "time": "2026-06-03T00:00:00+00:00"},
            {"symbol": "MSFT", "action": "long", "quantity": 5.0, "price": 420.0,
             "entry_price": 430.0, "time": "2026-06-04T00:00:00+00:00"},
        ],
    ]
    resp = await client.get("/analytics/summary?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    assert "sharpe" in data
    assert "max_drawdown" in data
    assert "win_rate" in data
    assert "total_pnl" in data
    assert "trade_count" in data
    assert data["trade_count"] == 2
    assert data["win_rate"] == 0.5


@pytest.mark.asyncio
async def test_summary_insufficient_data_returns_error(client, mock_db):
    mock_db.fetch.side_effect = [[], []]
    resp = await client.get("/analytics/summary?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("error") == "insufficient_data"


@pytest.mark.asyncio
async def test_equity_curve_returns_time_series(client, mock_db):
    mock_db.fetch.return_value = [
        {"time": "2026-06-01T00:00:00+00:00", "total_value": 100000.0},
        {"time": "2026-06-02T00:00:00+00:00", "total_value": 101000.0},
    ]
    resp = await client.get("/analytics/equity-curve?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    assert "equity" in data
    assert "daily_returns" in data
    assert "drawdown" in data
    assert len(data["equity"]) == 2


@pytest.mark.asyncio
async def test_pnl_by_symbol_aggregates(client, mock_db):
    mock_db.fetch.return_value = [
        {"symbol": "AAPL", "action": "long", "quantity": 10.0,
         "price": 185.0, "entry_price": 180.0},
        {"symbol": "AAPL", "action": "long", "quantity": 5.0,
         "price": 185.0, "entry_price": 183.0},
        {"symbol": "MSFT", "action": "long", "quantity": 3.0,
         "price": 400.0, "entry_price": 420.0},
    ]
    resp = await client.get("/analytics/pnl-by-symbol?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    symbols = {d["symbol"] for d in data}
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    aapl = next(d for d in data if d["symbol"] == "AAPL")
    assert aapl["pnl"] > 0


@pytest.mark.asyncio
async def test_monthly_returns_grid(client, mock_db):
    mock_db.fetch.return_value = [
        {"time": "2026-06-01T00:00:00+00:00", "total_value": 100000.0},
        {"time": "2026-06-30T00:00:00+00:00", "total_value": 104000.0},
    ]
    resp = await client.get("/analytics/monthly-returns")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["year"] == 2026
    assert data[0]["month"] == 6
    assert abs(data[0]["return_pct"] - 4.0) < 0.01
