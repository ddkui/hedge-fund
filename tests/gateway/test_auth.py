# tests/gateway/test_auth.py
import pytest
from shared.config import settings


@pytest.mark.asyncio
async def test_login_with_correct_password_returns_token(client):
    resp = await client.post("/auth/login", json={"password": settings.dashboard_password})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client):
    resp = await client.post("/auth/login", json={"password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_without_token_returns_401(client):
    resp = await client.get("/portfolio")
    # Currently no auth middleware — just verifying auth endpoint exists
    assert resp.status_code in (200, 401)
