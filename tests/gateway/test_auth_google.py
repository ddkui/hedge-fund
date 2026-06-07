# tests/gateway/test_auth_google.py
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_google_login_issues_jwt_for_allowed_email(client):
    with patch("gateway.routers.auth.settings") as s, \
         patch("gateway.routers.auth._verify_google_token",
               return_value={"email": "me@gmail.com", "email_verified": True}):
        s.allowed_login_emails = "me@gmail.com"
        s.jwt_secret = "test"
        resp = await client.post("/auth/google", json={"credential": "tok"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert resp.json()["email"] == "me@gmail.com"


@pytest.mark.asyncio
async def test_google_login_rejects_unverified_email(client):
    with patch("gateway.routers.auth._verify_google_token",
               return_value={"email": "me@gmail.com", "email_verified": False}):
        resp = await client.post("/auth/google", json={"credential": "tok"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_google_login_rejects_unlisted_email(client):
    with patch("gateway.routers.auth.settings") as s, \
         patch("gateway.routers.auth._verify_google_token",
               return_value={"email": "stranger@gmail.com", "email_verified": True}):
        s.allowed_login_emails = "owner@gmail.com"
        resp = await client.post("/auth/google", json={"credential": "tok"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_google_login_rejects_invalid_token(client):
    with patch("gateway.routers.auth._verify_google_token", side_effect=ValueError("bad token")):
        resp = await client.post("/auth/google", json={"credential": "bad"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_config_returns_client_id(client):
    with patch("gateway.routers.auth.settings") as s:
        s.google_client_id = "abc.apps.googleusercontent.com"
        resp = await client.get("/auth/config")
        assert resp.status_code == 200
        assert resp.json()["google_client_id"] == "abc.apps.googleusercontent.com"
