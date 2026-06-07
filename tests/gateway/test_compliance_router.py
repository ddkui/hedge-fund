# tests/gateway/test_compliance_router.py
import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_get_compliance_check_endpoint(client):
    """Test: POST /api/compliance/check returns violation status."""
    response = await client.post(
        "/api/compliance/check",
        json={
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.0,
            "action": "BUY",
            "portfolio_value": 1_000_000,
            "current_position_qty": 0,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "passes" in data
    assert "violations" in data or data["passes"] is True


@pytest.mark.asyncio
async def test_compliance_violation_response(client):
    """Test: Compliance check returns violation details."""
    response = await client.post(
        "/api/compliance/check",
        json={
            "symbol": "AAPL",
            "quantity": 300000,  # Exceeds 25% limit
            "price": 100.0,
            "action": "BUY",
            "portfolio_value": 1_000_000,
            "current_position_qty": 0,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["passes"] is False
    assert "position_limit" in data.get("violations", [])


@pytest.mark.asyncio
async def test_get_violation_history(client):
    """Test: GET /api/compliance/violations returns history."""
    response = await client.get("/api/compliance/violations?symbol=AAPL&limit=50")

    assert response.status_code == 200
    data = response.json()
    assert "violations" in data
    assert "count" in data
    assert "symbol_filter" in data


@pytest.mark.asyncio
async def test_pdt_violation_detection(client):
    """Test: Compliance check detects Pattern Day Trader violation."""
    response = await client.post(
        "/api/compliance/check",
        json={
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.0,
            "action": "BUY",
            "portfolio_value": 10_000,  # < $25k minimum
            "current_position_qty": 0,
            "day_trades_today": 3,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["passes"] is False
    assert "pdt_violation" in data.get("violations", [])
