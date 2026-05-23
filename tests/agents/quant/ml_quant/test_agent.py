import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from agents.quant.ml_quant.model import MLEnsemble
from agents.quant.ml_quant.agent import MLQuantAgent


def make_agent():
    return MLQuantAgent(
        name="ml_quant",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=["AAPL"],
        interval_seconds=120,
    )


def make_price_rows(n=600):
    np.random.seed(42)
    rows = []
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = 150.0
    for i in range(n):
        price += np.random.normal(0.05, 0.5)
        rows.append({
            "time": base + timedelta(minutes=i),
            "open": price - 0.2,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": float(np.random.randint(50_000, 200_000)),
        })
    return rows


def test_ml_ensemble_fit_and_predict():
    model = MLEnsemble()
    X = np.random.randn(300, 10)
    y = np.random.choice([-1, 0, 1], 300)
    model.fit(X, y)
    direction, confidence = model.predict(X[-1:])
    assert direction in {-1, 0, 1}
    assert 0.0 <= confidence <= 1.0


def test_ml_ensemble_untrained_returns_neutral():
    model = MLEnsemble()
    direction, confidence = model.predict(np.random.randn(1, 10))
    assert direction == 0
    assert confidence == 0.5


@pytest.mark.asyncio
async def test_ml_agent_skips_when_insufficient_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_price_rows(100))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_ml_agent_infers_after_training():
    agent = make_agent()
    rows = make_price_rows(600)
    # Inject a pre-trained mock model
    mock_model = MagicMock()
    mock_model.trained = True
    mock_model.predict = MagicMock(return_value=(1, 0.82))
    agent._models["AAPL"] = mock_model
    # Set last_trained so retrain is skipped
    from datetime import datetime, timezone
    agent._last_trained["AAPL"] = datetime.now(timezone.utc)
    agent.db.fetch = AsyncMock(return_value=rows[-60:])
    await agent.run_once()
    # With direction=1 and confidence=0.82, a ml_bullish signal should be stored
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "ml_bullish" in call[0]
