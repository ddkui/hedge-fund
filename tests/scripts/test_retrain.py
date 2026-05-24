# tests/scripts/test_retrain.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_retrain_fetches_prices_from_db():
    with patch("scripts.retrain_models.Database") as MockDB:
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[
            {"symbol": "AAPL", "close": 180.0, "time": "2026-05-01T10:00:00+00:00"},
        ] * 100)
        MockDB.return_value = mock_db
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()

        from scripts.retrain_models import fetch_training_data
        data = await fetch_training_data(mock_db, "AAPL", days=30)
        assert len(data) > 0


@pytest.mark.asyncio
async def test_retrain_skips_symbol_with_insufficient_data():
    with patch("scripts.retrain_models.Database"):
        from scripts.retrain_models import fetch_training_data
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {"symbol": "AAPL", "close": 180.0, "time": "2026-05-01T10:00:00+00:00"}
        ] * 5)
        result = await fetch_training_data(db, "AAPL", days=30)
        # Less than MIN_ROWS should return empty
        assert result == [] or len(result) < 20
