# tests/gateway/test_auth_otp.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_request_otp_sends_email_and_stores_redis(client, mock_bus):
    with patch("gateway.routers.auth.settings") as mock_settings:
        mock_settings.allowed_login_emails = "test@example.com"
        mock_settings.otp_expiry_seconds = 600
        mock_settings.gmail_sender = "sender@gmail.com"
        mock_settings.gmail_app_password = "app-pass"
        mock_bus.set = AsyncMock()
        with patch("gateway.routers.auth._send_otp_email") as mock_send:
            resp = await client.post("/auth/request-otp", json={"email": "test@example.com"})
            assert resp.status_code == 200
            assert resp.json()["message"] == "OTP sent"
            mock_bus.set.assert_called_once()
            mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_request_otp_rejects_unlisted_email(client):
    with patch("gateway.routers.auth.settings") as mock_settings:
        mock_settings.allowed_login_emails = "allowed@example.com"
        resp = await client.post("/auth/request-otp", json={"email": "hacker@evil.com"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verify_otp_issues_jwt_on_correct_code(client, mock_bus):
    mock_bus.get = AsyncMock(return_value={"otp": "123456", "email": "test@example.com"})
    mock_bus.delete = AsyncMock()
    with patch("gateway.routers.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret"
        mock_settings.allowed_login_emails = "test@example.com"
        resp = await client.post(
            "/auth/verify-otp",
            json={"email": "test@example.com", "otp": "123456"}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_verify_otp_rejects_wrong_code(client, mock_bus):
    mock_bus.get = AsyncMock(return_value={"otp": "123456", "email": "test@example.com"})
    resp = await client.post(
        "/auth/verify-otp",
        json={"email": "test@example.com", "otp": "999999"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_otp_rejects_expired_code(client, mock_bus):
    mock_bus.get = AsyncMock(return_value=None)
    resp = await client.post(
        "/auth/verify-otp",
        json={"email": "test@example.com", "otp": "123456"}
    )
    assert resp.status_code == 401
