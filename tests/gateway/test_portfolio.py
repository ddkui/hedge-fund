# tests/gateway/test_portfolio.py
import pytest


@pytest.mark.asyncio
async def test_get_portfolio_returns_summary(client, mock_db):
    mock_db.fetchrow.return_value = {
        "cash": 95000.0,
        "total_value": 102000.0,
        "peak_value": 105000.0,
        "open_positions": 2,
        "time": "2026-05-24T10:00:00+00:00",
    }
    # Endpoint computes total_value dynamically via MTM; with no open positions fetched,
    # total_value = cash
    mock_db.fetch.return_value = []
    resp = await client.get("/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_value"] == 95000.0
    assert data["cash"] == 95000.0
    assert data["open_positions"] == 0


@pytest.mark.asyncio
async def test_get_portfolio_no_state_returns_initial_capital(client, mock_db):
    mock_db.fetchrow.return_value = None
    resp = await client.get("/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_value"] == 100000.0


@pytest.mark.asyncio
async def test_get_positions_returns_list(client, mock_db):
    positions = [
        {"id": 1, "symbol": "AAPL", "direction": "long", "quantity": 10.0,
         "entry_price": 180.0, "status": "open", "asset_class": "stock",
         "entry_time": "2026-05-24T09:00:00+00:00", "entry_thesis": "bullish",
         "exit_price": None, "exit_time": None},
    ]
    prices = [{"symbol": "AAPL", "close": 185.0}]
    # First fetch returns positions, second fetch returns prices
    mock_db.fetch.side_effect = [positions, prices]
    resp = await client.get("/portfolio/positions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_get_trades_returns_list(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "symbol": "AAPL", "action": "long", "quantity": 10.0,
         "price": 180.0, "paper": True, "status": "executed",
         "confidence": 80.0, "pm_reasoning": "bullish signal",
         "time": "2026-05-24T09:00:00+00:00", "position_id": None},
    ]
    resp = await client.get("/portfolio/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
