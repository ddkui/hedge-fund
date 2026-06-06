# tests/gateway/test_brokers_router.py
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_list_accounts(client):
    with patch("gateway.routers.brokers.broker_config.list_brokers",
               return_value=[{"name": "x", "type": "alpaca", "api_key": "****1234", "enabled": True}]):
        resp = await client.get("/brokers/accounts")
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "x"
        assert resp.json()[0]["api_key"] == "****1234"


@pytest.mark.asyncio
async def test_add_account(client):
    with patch("gateway.routers.brokers.broker_config.add_broker",
               return_value={"name": "investor-john", "type": "alpaca"}) as mock_add:
        resp = await client.post("/brokers/accounts", json={
            "name": "investor-john", "type": "alpaca",
            "api_key": "PK123", "secret_key": "S456", "paper": False,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "investor-john"
        mock_add.assert_called_once()


@pytest.mark.asyncio
async def test_add_account_duplicate_returns_400(client):
    with patch("gateway.routers.brokers.broker_config.add_broker",
               side_effect=ValueError("broker 'dup' already exists")):
        resp = await client.post("/brokers/accounts", json={
            "name": "dup", "type": "alpaca", "api_key": "k", "secret_key": "s", "paper": True,
        })
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_account(client):
    with patch("gateway.routers.brokers.broker_config.remove_broker", return_value=True):
        resp = await client.delete("/brokers/accounts/x")
        assert resp.status_code == 200
        assert resp.json()["removed"] == "x"


@pytest.mark.asyncio
async def test_delete_missing_returns_404(client):
    with patch("gateway.routers.brokers.broker_config.remove_broker", return_value=False):
        resp = await client.delete("/brokers/accounts/missing")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toggle_account(client):
    with patch("gateway.routers.brokers.broker_config.toggle_broker", return_value=True):
        resp = await client.patch("/brokers/accounts/x/toggle", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
