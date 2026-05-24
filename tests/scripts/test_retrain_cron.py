# tests/scripts/test_retrain_cron.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_retrain_cron_once_calls_retrain_and_exits():
    """--once flag: retrain is called exactly once then loop exits."""
    call_count = 0

    async def fake_retrain():
        nonlocal call_count
        call_count += 1

    with patch("scripts.retrain_models.main", new=fake_retrain):
        from scripts.retrain_cron import main as cron_main
        await cron_main.__wrapped__ if hasattr(cron_main, "__wrapped__") else None

    # Run via argv injection
    with patch("scripts.retrain_models.main", new=fake_retrain), \
         patch("sys.argv", ["retrain_cron.py", "--once"]):
        import importlib
        import scripts.retrain_cron as cron_mod
        importlib.reload(cron_mod)
        await cron_mod.main()

    assert call_count == 1


@pytest.mark.asyncio
async def test_retrain_cron_continues_after_error():
    """If retrain raises, the cron loop catches it and doesn't crash (--once exits after 1 try)."""
    async def bad_retrain():
        raise RuntimeError("DB down")

    with patch("scripts.retrain_models.main", new=bad_retrain), \
         patch("sys.argv", ["retrain_cron.py", "--once"]):
        import importlib
        import scripts.retrain_cron as cron_mod
        importlib.reload(cron_mod)
        # Should not raise
        await cron_mod.main()
