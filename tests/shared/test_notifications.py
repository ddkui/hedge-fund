# tests/shared/test_notifications.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_service():
    from shared.notifications import NotificationService
    svc = NotificationService.__new__(NotificationService)
    svc.sender = "test@gmail.com"
    svc.recipient = "test@gmail.com"
    svc.app_password = "test-password"
    svc.logger = MagicMock()
    return svc


def test_format_trade_executed_email():
    svc = make_service()
    subject, body = svc._format_email("trade_executed", {
        "symbol": "AAPL", "action": "long", "quantity": 10.0,
        "price": 180.0, "paper": True,
    })
    assert "AAPL" in subject
    assert "long" in body
    assert "10.0" in body


def test_format_risk_breach_email():
    svc = make_service()
    subject, body = svc._format_email("risk_breach", {
        "limit_type": "drawdown", "details": "portfolio down 20%",
    })
    assert "URGENT" in subject.upper() or "Risk" in subject
    assert "drawdown" in body


def test_format_agent_down_email():
    svc = make_service()
    subject, body = svc._format_email("agent_down", {"agent": "technical"})
    assert "technical" in body


def test_format_unknown_event_has_fallback():
    svc = make_service()
    subject, body = svc._format_email("unknown_event", {"foo": "bar"})
    assert len(subject) > 0
    assert len(body) > 0


@pytest.mark.asyncio
async def test_handle_trade_executed_sends_email():
    svc = make_service()
    with patch.object(svc, "_send_email") as mock_send:
        await svc._handle_event("trade_executed", {
            "symbol": "AAPL", "action": "long", "quantity": 10.0,
            "price": 180.0, "paper": True,
        })
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_low_confidence_trade_does_not_email():
    """Trades < 30% confidence are auto-denied — no email needed."""
    svc = make_service()
    with patch.object(svc, "_send_email") as mock_send:
        await svc._handle_event("trade_denied", {"confidence": 20.0, "symbol": "AAPL"})
        mock_send.assert_not_called()
