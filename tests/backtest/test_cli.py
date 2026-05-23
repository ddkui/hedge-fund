import pytest
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


async def test_cli_parses_start_end():
    """CLI correctly parses --start and --end into aware datetimes."""
    from backtest.cli import parse_args
    args = parse_args([
        "--start", "2024-01-01",
        "--end", "2024-03-31",
        "--step", "1h",
        "--output", "out.html",
    ])
    assert args.start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert args.end == datetime(2024, 3, 31, tzinfo=timezone.utc)


async def test_cli_parses_step_1h():
    from backtest.cli import parse_step
    assert parse_step("1h") == 3600


async def test_cli_parses_step_30m():
    from backtest.cli import parse_step
    assert parse_step("30m") == 1800


async def test_cli_parses_step_1d():
    from backtest.cli import parse_step
    assert parse_step("1d") == 86400


async def test_cli_parse_step_invalid_raises():
    from backtest.cli import parse_step
    with pytest.raises(ValueError):
        parse_step("2x")


async def test_cli_default_agents():
    """When --agents is omitted, default agent list is used."""
    from backtest.cli import parse_args, DEFAULT_AGENTS
    args = parse_args([
        "--start", "2024-01-01",
        "--end", "2024-01-31",
        "--output", "out.html",
    ])
    assert args.agents == DEFAULT_AGENTS
