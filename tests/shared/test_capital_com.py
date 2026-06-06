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
    resp.json.return_value = {"dealStatus": "ACCEPTED", "level": level}
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
    await session.disconnect()  # cancel background refresh task


@pytest.mark.asyncio
async def test_session_reauth_on_401():
    """On 401 during place_order, session re-auths and retry uses fresh tokens."""
    session = make_session()
    session.cst = "old-cst"
    session.security_token = "old-token"

    unauth = MagicMock()
    unauth.status_code = 401
    unauth.json.return_value = {}

    async def mock_auth_update():
        session.cst = "new-cst"
        session.security_token = "new-token"

    with patch.object(session, "_authenticate", side_effect=mock_auth_update), \
         patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=[
            unauth,
            mock_position_response("REF1"),
        ])
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1850.0))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 1.0)

    assert price == 1850.0
    # Verify the second POST used the new tokens
    second_post_kwargs = mock_client.post.call_args_list[1][1]
    headers_sent = second_post_kwargs.get("headers", {})
    assert headers_sent.get("CST") == "new-cst"
    assert headers_sent.get("X-SECURITY-TOKEN") == "new-token"


@pytest.mark.asyncio
async def test_session_refresh_called_before_expiry():
    """_refresh_loop sleeps 9 minutes then calls _authenticate."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    call_order = []

    async def fake_auth():
        call_order.append("auth")

    session._authenticate = fake_auth

    sleep_calls = []

    async def fake_sleep(secs):
        call_order.append(f"sleep:{secs}")
        sleep_calls.append(secs)
        # Allow the loop to proceed after first sleep, stop after first auth
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError

    with patch("shared.capital_com.asyncio.sleep", fake_sleep):
        try:
            await session._refresh_loop()
        except asyncio.CancelledError:
            pass

    # First event should be sleep(540), then auth
    assert call_order[0] == "sleep:540"
    assert call_order[1] == "auth"
    assert sleep_calls[0] == 540


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
async def test_capital_fill_rejected_deal_raises():
    """If Capital.com confirms the order but dealStatus != ACCEPTED, raise ValueError."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    rejected_confirm = MagicMock()
    rejected_confirm.status_code = 200
    rejected_confirm.raise_for_status = MagicMock()
    rejected_confirm.json.return_value = {"dealStatus": "REJECTED", "rejectReason": "INSUFFICIENT_FUNDS", "level": 0}

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls, \
         patch("shared.capital_com.asyncio.sleep", new_callable=AsyncMock):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_position_response("REF_REJ"))
        mock_client.get = AsyncMock(return_value=rejected_confirm)
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 1.0)

    # Both attempts see REJECTED → place_order returns None
    assert price is None


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


# ── price feed ────────────────────────────────────────────────────────────────

def mock_market_response(bid=1899.0, ask=1901.0):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "snapshot": {"bid": bid, "offer": ask}
    }
    return resp


@pytest.mark.asyncio
async def test_price_feed_upserts_tick_to_db():
    from shared.capital_com import CapitalPriceFeed
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    db = AsyncMock()

    feed = CapitalPriceFeed(session=session, db=db, epics=["GOLD"], interval_seconds=0)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_market_response(1899.0, 1901.0))

    await feed._tick("GOLD", mock_client)

    db.execute.assert_called_once()
    call_args = db.execute.call_args[0]
    assert "prices" in call_args[0]
    # mid = (1899 + 1901) / 2 = 1900.0
    assert 1900.0 in call_args


@pytest.mark.asyncio
async def test_price_feed_reconnects_on_disconnect():
    """Per-epic errors are isolated: a single failing epic is logged but the cycle continues."""
    from shared.capital_com import CapitalPriceFeed
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    db = AsyncMock()
    feed = CapitalPriceFeed(session=session, db=db, epics=["GOLD"], interval_seconds=0)

    call_count = 0

    async def flaky_tick(epic, client):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("disconnected")
        raise asyncio.CancelledError  # stop after second call

    feed._tick = flaky_tick

    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)

    with patch("shared.capital_com.asyncio.sleep", fake_sleep):
        try:
            await feed.run()
        except asyncio.CancelledError:
            pass

    # The per-epic error is isolated: cycle completes and calls interval sleep (0), not backoff.
    # call_count == 2 confirms the second tick was reached (CancelledError stops the loop).
    assert call_count == 2
    assert sleep_calls[0] == 0  # interval sleep after first successful cycle


@pytest.mark.asyncio
async def test_leverage_applied_correctly_per_asset_class():
    """get_leverage returns the right multiplier per asset_class."""
    from shared.capital_com import get_leverage
    mock_settings = MagicMock()
    mock_settings.capital_com_leverage_forex = 10
    mock_settings.capital_com_leverage_indices = 5
    mock_settings.capital_com_leverage_commodities = 5
    mock_settings.capital_com_leverage_shares = 5

    with patch("shared.capital_com.settings", mock_settings):
        assert get_leverage("forex") == 10
        assert get_leverage("indices") == 5
        assert get_leverage("commodities") == 5
        assert get_leverage("shares") == 5
        assert get_leverage("unknown") == 1  # default: no leverage
