# tests/gateway/test_compliance_router.py
"""
Integration tests for compliance router endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from gateway.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestComplianceRouter:
    """Test compliance router endpoints."""

    def test_check_trade_valid(self, client):
        """Should return passes=True for valid trade."""
        response = client.post(
            "/api/compliance/check-trade",
            json={
                "symbol": "AAPL",
                "action": "long",
                "quantity": 100,
                "position_limit_pct": 0.05,
                "day_trades_today": 0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is True
        assert data["violations"] == []

    def test_check_trade_invalid_quantity(self, client):
        """Should reject request with invalid quantity (validation error)."""
        response = client.post(
            "/api/compliance/check-trade",
            json={
                "symbol": "AAPL",
                "action": "long",
                "quantity": -100,  # Negative quantity fails FastAPI validation
                "position_limit_pct": 0.05,
                "day_trades_today": 0,
            },
        )
        # FastAPI validation rejects negative quantities
        assert response.status_code == 422

    def test_check_trade_pdt_violation(self, client):
        """Should reject trade when PDT limit exceeded."""
        response = client.post(
            "/api/compliance/check-trade",
            json={
                "symbol": "AAPL",
                "action": "long",
                "quantity": 100,
                "position_limit_pct": 0.05,
                "day_trades_today": 4,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is False
        assert any("PDT" in v for v in data["violations"])

    def test_check_trade_all_parameters(self, client):
        """Should accept all parameters."""
        response = client.post(
            "/api/compliance/check-trade",
            json={
                "symbol": "MSFT",
                "action": "short",
                "quantity": 50,
                "position_limit_pct": 0.10,
                "day_trades_today": 2,
                "last_short_price": 350.0,
                "broker_limits": {"max_single_order": 5000},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "passes" in data
        assert "violations" in data

    def test_check_short_sale_valid(self, client):
        """Should validate short sale."""
        response = client.post(
            "/api/compliance/check-short-sale",
            json={
                "symbol": "AAPL",
                "quantity": 100,
                "current_price": 150.0,
                "last_short_price": 150.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is True

    def test_check_short_sale_uptick_violation(self, client):
        """Should reject short below last short price."""
        response = client.post(
            "/api/compliance/check-short-sale",
            json={
                "symbol": "AAPL",
                "quantity": 100,
                "current_price": 145.0,
                "last_short_price": 150.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is False
        assert any("uptick" in v.lower() for v in data["violations"])

    def test_check_pdt_status_valid(self, client):
        """Should validate PDT status."""
        response = client.post(
            "/api/compliance/check-pdt-status",
            json={
                "account_type": "margin",
                "equity": 25000,
                "day_trades_count": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is True

    def test_check_pdt_status_insufficient_equity(self, client):
        """Should reject margin account with insufficient equity."""
        response = client.post(
            "/api/compliance/check-pdt-status",
            json={
                "account_type": "margin",
                "equity": 20000,
                "day_trades_count": 4,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passes"] is False

    def test_missing_required_fields(self, client):
        """Should return error for missing required fields."""
        response = client.post(
            "/api/compliance/check-trade",
            json={
                "symbol": "AAPL",
                # Missing action and quantity
            },
        )
        assert response.status_code == 422  # Validation error
