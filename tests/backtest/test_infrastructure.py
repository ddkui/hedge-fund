import pytest
import asyncpg
from unittest.mock import AsyncMock, patch, MagicMock

async def test_setup_backtest_db_runs_schema():
    """setup_backtest_db creates the now_or_backtest function and backtest_runs table."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", return_value=mock_conn) as mock_connect:
        import importlib, sys
        sys.path.insert(0, ".")
        import scripts.setup_backtest_db as sbd
        await sbd.main()

    # Should have called execute at least once with a CREATE TABLE statement
    all_sql = " ".join(call.args[0] for call in mock_conn.execute.call_args_list)
    assert "backtest_runs" in all_sql
    assert "now_or_backtest" in all_sql
