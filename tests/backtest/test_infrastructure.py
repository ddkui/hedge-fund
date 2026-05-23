import pytest
import importlib
import asyncpg
import scripts.setup_backtest_db as sbd
from unittest.mock import AsyncMock, patch

async def test_setup_backtest_db_runs_schema():
    """setup_backtest_db creates the now_or_backtest function and backtest_runs table."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch("scripts.setup_backtest_db.asyncpg.connect", return_value=mock_conn) as mock_connect:
        importlib.reload(sbd)  # force re-execution under mock
        await sbd.main()

    mock_connect.assert_awaited_once()
    # Should have called execute at least once with a CREATE TABLE statement
    all_sql = " ".join(call.args[0] for call in mock_conn.execute.call_args_list)
    assert "backtest_runs" in all_sql
    assert "now_or_backtest" in all_sql
