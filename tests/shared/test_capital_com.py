# tests/shared/test_capital_com.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def make_session():
    from shared.capital_com import CapitalComSession
    return CapitalComSession(
        base_url="https://demo-api-capital.backend.gbksoft.net",
        api_key="test-key",
        identifier="test@example.com",
        password="test-pass",
    )


def mock_auth_response():
    """httpx.Response mock with CST and X-SECURITY-TOKEN headers."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"CST": "cst-token", "X-SECURITY-TOKEN": "sec-token"}
    resp.json.return_value = {}
    return resp


def mock_position_response(deal_ref="DEAL123"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"dealReference": deal_ref}
    return resp


def mock_confirm_response(level=1900.5):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": "ACCEPTED", "level": level}
    return resp


# ── session auth ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_auth_creates_tokens():
    session = make_session()
    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_auth_response())
        mock_client_cls.return_value = mock_client

        await session.connect()

    assert session.cst == "cst-token"
    assert session.security_token == "sec-token"


@pytest.mark.asyncio
async def test_session_reauth_on_401():
    """On 401 during place_order, session re-auths and retries."""
    session = make_session()
    session.cst = "old-cst"
    session.security_token = "old-token"

    unauth = MagicMock()
    unauth.status_code = 401
    unauth.json.return_value = {}

    with patch.object(session, "_authenticate", new_callable=AsyncMock) as mock_auth, \
         patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=[
            unauth,                              # first attempt → 401
            mock_position_response("REF1"),       # retry after reauth
        ])
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1850.0))
        mock_client_cls.return_value = mock_client

        mock_auth.return_value = None

        price = await session.place_order("GOLD", "BUY", 1.0)

    mock_auth.assert_called_once()
    assert price == 1850.0


@pytest.mark.asyncio
async def test_session_refresh_called_before_expiry():
    """_refresh_loop calls _authenticate before the 9-minute mark."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    call_count = 0

    async def fake_auth():
        nonlocal call_count
        call_count += 1

    session._authenticate = fake_auth

    # Patch asyncio.sleep to skip the 9-minute wait
    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)
        raise asyncio.CancelledError  # stop after first tick

    with patch("shared.capital_com.asyncio.sleep", fake_sleep):
        try:
            await session._refresh_loop()
        except asyncio.CancelledError:
            pass

    assert sleep_calls == [540]   # 9 minutes = 540 seconds
    assert call_count == 1


# ── order placement ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capital_fill_long_returns_fill_price():
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_position_response("REF1"))
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1900.5))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 2.0)

    assert price == 1900.5


@pytest.mark.asyncio
async def test_capital_fill_short_returns_fill_price():
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_position_response("REF2"))
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1880.0))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "SELL", 1.0)

    assert price == 1880.0


@pytest.mark.asyncio
async def test_capital_fill_retries_on_failure():
    """First place_order call raises, second succeeds."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls, \
         patch("shared.capital_com.asyncio.sleep", new_callable=AsyncMock):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=[
            Exception("network error"),
            mock_position_response("REF3"),
        ])
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1910.0))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 1.0)

    assert price == 1910.0


@pytest.mark.asyncio
async def test_capital_fill_fails_trade_on_double_failure():
    """Both attempts raise — place_order returns None."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls, \
         patch("shared.capital_com.asyncio.sleep", new_callable=AsyncMock):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 1.0)

    assert price is None
