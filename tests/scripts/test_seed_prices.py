# tests/scripts/test_seed_prices.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _make_yahoo_payload(n: int = 5) -> dict:
    """Build a minimal Yahoo Finance v8 chart API response."""
    base_ts = 1700000000
    return {
        "chart": {
            "result": [{
                "timestamp": [base_ts + i * 86400 for i in range(n)],
                "indicators": {
                    "quote": [{
                        "open":   [100.0 + i for i in range(n)],
                        "high":   [105.0 + i for i in range(n)],
                        "low":    [95.0  + i for i in range(n)],
                        "close":  [102.0 + i for i in range(n)],
                        "volume": [1_000_000.0 for _ in range(n)],
                    }]
                },
            }],
            "error": None,
        }
    }


@pytest.mark.asyncio
async def test_seed_symbol_inserts_rows():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _make_yahoo_payload(10)

    mock_conn = AsyncMock()

    with patch("scripts.seed_prices.requests.get", return_value=mock_resp):
        from scripts.seed_prices import seed_symbol
        count = await seed_symbol(mock_conn, "AAPL", "2y", dry_run=False)

    assert count == 10
    mock_conn.executemany.assert_called_once()
    # Verify the INSERT sql is correct
    sql = mock_conn.executemany.call_args[0][0]
    assert "INSERT INTO prices" in sql
    assert "ON CONFLICT" in sql


@pytest.mark.asyncio
async def test_seed_symbol_dry_run_does_not_insert():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _make_yahoo_payload(5)

    mock_conn = AsyncMock()

    with patch("scripts.seed_prices.requests.get", return_value=mock_resp):
        from scripts.seed_prices import seed_symbol
        count = await seed_symbol(mock_conn, "AAPL", "2y", dry_run=True)

    assert count == 5
    mock_conn.executemany.assert_not_called()


@pytest.mark.asyncio
async def test_seed_symbol_skips_on_http_error():
    import requests as req

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req.HTTPError("404")

    mock_conn = AsyncMock()

    with patch("scripts.seed_prices.requests.get", return_value=mock_resp):
        from scripts.seed_prices import seed_symbol
        count = await seed_symbol(mock_conn, "UNKNOWN", "2y", dry_run=False)

    assert count == 0
    mock_conn.executemany.assert_not_called()


@pytest.mark.asyncio
async def test_seed_symbol_skips_incomplete_bars():
    """Bars with None open/high/low/close should be skipped."""
    payload = _make_yahoo_payload(5)
    # Corrupt first 2 bars
    payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][0] = None
    payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][1] = None

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = payload

    mock_conn = AsyncMock()

    with patch("scripts.seed_prices.requests.get", return_value=mock_resp):
        from scripts.seed_prices import seed_symbol
        count = await seed_symbol(mock_conn, "AAPL", "2y", dry_run=False)

    assert count == 3  # only 3 complete bars


def test_yahoo_ticker_maps_crypto_symbols():
    from scripts.seed_prices import _yahoo_ticker
    assert _yahoo_ticker("BTCUSDT") == "BTC-USD"
    assert _yahoo_ticker("ETHUSDT") == "ETH-USD"
    assert _yahoo_ticker("AAPL") == "AAPL"


def test_asset_class_detection():
    from scripts.seed_prices import _asset_class
    assert _asset_class("BTCUSDT") == "crypto"
    assert _asset_class("AAPL") == "stock"
    assert _asset_class("SPY") == "stock"
