import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock, call


def _make_mock_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


async def test_connect_sets_search_path():
    mock_conn = _make_mock_conn()
    with patch("backtest.db.asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=42)
        await db.connect()

    calls = [str(c) for c in mock_conn.execute.call_args_list]
    assert any("bt_42" in c and "search_path" in c for c in calls)


async def test_set_tick_stores_current_tick():
    mock_conn = _make_mock_conn()
    with patch("backtest.db.asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    dt = datetime(2024, 3, 15, 10, 30, tzinfo=timezone.utc)
    await db.set_tick(dt)

    assert db.current_tick == dt


async def test_set_tick_executes_session_variable():
    mock_conn = _make_mock_conn()
    with patch("backtest.db.asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    mock_conn.execute.reset_mock()
    await db.set_tick(dt)

    all_sql = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    assert "backtest.now" in all_sql


async def test_fetch_delegates_to_connection():
    mock_conn = _make_mock_conn()
    mock_conn.fetch = AsyncMock(return_value=[{"id": 1}])
    with patch("backtest.db.asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    result = await db.fetch("SELECT 1")
    assert result == [{"id": 1}]


async def test_fetchrow_delegates_to_connection():
    mock_conn = _make_mock_conn()
    mock_conn.fetchrow = AsyncMock(return_value={"cash": 100.0})
    with patch("backtest.db.asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    result = await db.fetchrow("SELECT cash FROM portfolio_state LIMIT 1")
    assert result == {"cash": 100.0}


async def test_create_schema_creates_tables():
    mock_conn = _make_mock_conn()
    with patch("backtest.db.asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=7)
        await db.connect()

    mock_conn.execute.reset_mock()
    await db.create_schema()

    all_sql = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    for table in ("signals", "trades", "positions", "portfolio_state", "risk_events"):
        assert table in all_sql, f"Expected {table} in schema DDL"
