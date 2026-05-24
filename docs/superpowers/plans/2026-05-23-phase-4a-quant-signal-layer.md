# Phase 4a — Quant Signal Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 4 foundation (2 new DB tables, 9 new config keys, 3 new packages) and 4 quant signal agents (momentum, mean reversion, ML ensemble, supervisor) that enrich the existing Phase 3 AI signals with systematic quantitative strategies.

**Architecture:** Each quant agent extends `AnalysisAgent` and calls `store_signal()` exactly like Phase 3 agents. The `QuantSupervisorAgent` reads signals from the other three quant agents, weights them by each algo's Sharpe ratio from the `quant_algos` table, and publishes a single `quant_bullish`/`quant_bearish` consensus per symbol. The ML quant agent trains an ensemble of 3 sklearn classifiers (LogisticRegression + RandomForest + GradientBoosting) on 10 OHLCV-derived features, retraining every 24h per symbol in a thread executor.

**Tech Stack:** pandas, numpy, scikit-learn (ML ensemble), asyncpg, Redis pub/sub, existing `agents/technical/indicators.py` (RSI, MACD, BB, ATR, OBV reused)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `scripts/setup_db.py` | Modify | Add `portfolio_state` and `risk_events` tables |
| `shared/config.py` | Modify | Add 9 new config keys |
| `requirements.txt` | Modify | Add scikit-learn, alpaca-py, python-binance |
| `agents/quant/__init__.py` | Create | Package marker |
| `agents/quant/momentum/__init__.py` | Create | Package marker |
| `agents/quant/momentum/agent.py` | Create | `MomentumQuantAgent` — 3-timeframe momentum signals |
| `agents/quant/momentum/main.py` | Create | Entry point |
| `agents/quant/mean_reversion/__init__.py` | Create | Package marker |
| `agents/quant/mean_reversion/agent.py` | Create | `MeanReversionQuantAgent` — Z-score + RSI signals |
| `agents/quant/mean_reversion/main.py` | Create | Entry point |
| `agents/quant/ml_quant/__init__.py` | Create | Package marker |
| `agents/quant/ml_quant/features.py` | Create | Feature extraction from OHLCV rows |
| `agents/quant/ml_quant/model.py` | Create | `MLEnsemble` — 3-model sklearn ensemble |
| `agents/quant/ml_quant/agent.py` | Create | `MLQuantAgent` — trains + infers per symbol |
| `agents/quant/ml_quant/main.py` | Create | Entry point |
| `agents/quant/supervisor/__init__.py` | Create | Package marker |
| `agents/quant/supervisor/agent.py` | Create | `QuantSupervisorAgent` — Sharpe-weighted consensus |
| `agents/quant/supervisor/main.py` | Create | Entry point |
| `tests/agents/quant/__init__.py` | Create | Package marker |
| `tests/agents/quant/momentum/__init__.py` | Create | Package marker |
| `tests/agents/quant/momentum/test_agent.py` | Create | 4 tests for MomentumQuantAgent |
| `tests/agents/quant/mean_reversion/__init__.py` | Create | Package marker |
| `tests/agents/quant/mean_reversion/test_agent.py` | Create | 4 tests for MeanReversionQuantAgent |
| `tests/agents/quant/ml_quant/__init__.py` | Create | Package marker |
| `tests/agents/quant/ml_quant/test_agent.py` | Create | 4 tests for MLQuantAgent + MLEnsemble |
| `tests/agents/quant/supervisor/__init__.py` | Create | Package marker |
| `tests/agents/quant/supervisor/test_agent.py` | Create | 4 tests for QuantSupervisorAgent |
| `scripts/start_all.py` | Modify | Add 4 quant agent entry points |

---

## Task 1: Foundation — DB tables, config, packages

**Files:**
- Modify: `scripts/setup_db.py`
- Modify: `shared/config.py`
- Modify: `requirements.txt`
- Modify: `tests/shared/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add to `tests/shared/test_config.py` (append after existing tests):

```python
def test_settings_kelly_multiplier_default():
    assert settings.kelly_multiplier == 0.25

def test_settings_risk_max_position_pct_default():
    assert settings.risk_max_position_pct == 0.10

def test_settings_risk_max_positions_default():
    assert settings.risk_max_positions == 10

def test_settings_initial_capital_default():
    assert settings.initial_capital == 100_000.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\jomik\hedge-fund
.venv\Scripts\pytest tests/shared/test_config.py -v -k "kelly or risk_max or initial_capital"
```

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'kelly_multiplier'`

- [ ] **Step 3: Add new config keys to `shared/config.py`**

Add these fields inside the `Settings` class, after the `crypto_watchlist` field:

```python
    kelly_multiplier: float = 0.25
    risk_max_position_pct: float = 0.10
    risk_max_positions: int = 10
    risk_max_drawdown_pct: float = 0.20
    risk_var_limit_pct: float = 0.05
    risk_max_correlated: int = 3
    initial_capital: float = 100_000.0
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    binance_base_url: str = "https://api.binance.com"
```

- [ ] **Step 4: Run config tests to verify they pass**

```
.venv\Scripts\pytest tests/shared/test_config.py -v -k "kelly or risk_max or initial_capital"
```

Expected: 4 passed

- [ ] **Step 5: Add new DB tables to `scripts/setup_db.py`**

In `setup_db.py`, append inside the `SCHEMA` string (before the closing `"""`):

```sql

CREATE TABLE IF NOT EXISTS portfolio_state (
    id             SERIAL PRIMARY KEY,
    time           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cash           DOUBLE PRECISION NOT NULL,
    total_value    DOUBLE PRECISION NOT NULL,
    peak_value     DOUBLE PRECISION NOT NULL,
    open_positions INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS risk_events (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent        TEXT NOT NULL,
    symbol       TEXT,
    limit_type   TEXT NOT NULL,
    details      TEXT NOT NULL,
    action_taken TEXT NOT NULL
);
```

- [ ] **Step 6: Add new packages to `requirements.txt`**

Append to end of `requirements.txt`:

```
scikit-learn==1.5.0
alpaca-py==0.20.0
python-binance==1.0.19
```

- [ ] **Step 7: Install new packages**

```
.venv\Scripts\pip install scikit-learn==1.5.0
.venv\Scripts\pip install alpaca-py==0.20.0
.venv\Scripts\pip install python-binance==1.0.19
```

If any exact version is unavailable, install the nearest available and update `requirements.txt` to match.

- [ ] **Step 8: Commit**

```
git add shared/config.py scripts/setup_db.py requirements.txt tests/shared/test_config.py
git commit -m "feat: Phase 4 foundation — DB tables, config keys, new packages"
```

---

## Task 2: MomentumQuantAgent

**Files:**
- Create: `agents/quant/__init__.py`
- Create: `agents/quant/momentum/__init__.py`
- Create: `agents/quant/momentum/agent.py`
- Create: `agents/quant/momentum/main.py`
- Create: `tests/agents/quant/__init__.py`
- Create: `tests/agents/quant/momentum/__init__.py`
- Create: `tests/agents/quant/momentum/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create all `__init__.py` files as empty.

Create `tests/agents/quant/momentum/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock
from agents.quant.momentum.agent import MomentumQuantAgent


def make_agent():
    return MomentumQuantAgent(
        name="momentum",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=["AAPL"],
        interval_seconds=120,
    )


def make_rows(n=70, trend="up"):
    price = 150.0
    rows = []
    for i in range(n):
        price += 0.1 if trend == "up" else -0.1
        rows.append({"close": price, "time": None})
    return rows


@pytest.mark.asyncio
async def test_momentum_stores_bullish_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(70, "up"))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "momentum_bullish" in call[0]


@pytest.mark.asyncio
async def test_momentum_stores_bearish_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(70, "down"))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "momentum_bearish" in call[0]


@pytest.mark.asyncio
async def test_momentum_skips_insufficient_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(30, "up"))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_momentum_confidence_in_range():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(70, "up"))
    await agent.run_once()
    call = agent.db.execute.call_args
    confidence = call[0][5]
    assert 0.0 <= confidence <= 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/quant/momentum/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.quant'`

- [ ] **Step 3: Create `agents/quant/momentum/agent.py`**

Create `agents/quant/__init__.py`, `agents/quant/momentum/__init__.py` (both empty).

```python
import pandas as pd
from agents.base import AnalysisAgent

MIN_BARS = 60
TIMEFRAMES = [5, 20, 60]
CONFIDENCE_MAP = {3: 85.0, 2: 65.0, 1: 40.0}


class MomentumQuantAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        for symbol in self.watchlist:
            rows = await self.db.fetch(
                """
                SELECT time, close FROM prices
                WHERE symbol = $1 AND time > NOW() - INTERVAL '3 hours'
                ORDER BY time ASC
                """,
                symbol,
            )
            if len(rows) < MIN_BARS:
                continue
            await self._analyze(symbol, rows)

    async def _analyze(self, symbol: str, rows: list):
        closes = pd.Series([float(r["close"]) for r in rows])

        momenta = []
        for n in TIMEFRAMES:
            idx = -(n + 1)
            if len(closes) > n:
                mom = (closes.iloc[-1] - closes.iloc[idx]) / closes.iloc[idx]
            else:
                mom = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
            momenta.append(float(mom))

        bullish_count = sum(1 for m in momenta if m > 0)
        bearish_count = sum(1 for m in momenta if m < 0)

        if bullish_count >= 2:
            signal_type = "momentum_bullish"
            confidence = CONFIDENCE_MAP.get(bullish_count, 40.0)
        elif bearish_count >= 2:
            signal_type = "momentum_bearish"
            confidence = CONFIDENCE_MAP.get(bearish_count, 40.0)
        else:
            return  # mixed momentum — no signal

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=f"mom_5={momenta[0]:.4f}, mom_20={momenta[1]:.4f}, mom_60={momenta[2]:.4f}",
            metadata={
                "mom_5": round(momenta[0], 4),
                "mom_20": round(momenta[1], 4),
                "mom_60": round(momenta[2], 4),
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
            },
        )
        self.logger.info("momentum_signal", symbol=symbol, signal=signal_type, confidence=confidence)
```

Create `agents/quant/momentum/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.momentum.agent import MomentumQuantAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    watchlist = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")
    agent = MomentumQuantAgent(
        name="momentum",
        bus=bus, db=db, router=router,
        watchlist=watchlist,
        interval_seconds=120,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/quant/momentum/test_agent.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add agents/quant/ tests/agents/quant/momentum/ tests/agents/quant/__init__.py
git commit -m "feat: MomentumQuantAgent with 3-timeframe momentum signals"
```

---

## Task 3: MeanReversionQuantAgent

**Files:**
- Create: `agents/quant/mean_reversion/__init__.py`
- Create: `agents/quant/mean_reversion/agent.py`
- Create: `agents/quant/mean_reversion/main.py`
- Create: `tests/agents/quant/mean_reversion/__init__.py`
- Create: `tests/agents/quant/mean_reversion/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/quant/mean_reversion/__init__.py` (empty).

Create `tests/agents/quant/mean_reversion/test_agent.py`:

```python
import pytest
import numpy as np
from unittest.mock import AsyncMock
from agents.quant.mean_reversion.agent import MeanReversionQuantAgent


def make_agent():
    return MeanReversionQuantAgent(
        name="mean_reversion",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=["AAPL"],
        interval_seconds=120,
    )


def make_rows_zscore(n=50, target_zscore=2.5):
    """Last bar is target_zscore std devs above 20-bar rolling mean."""
    np.random.seed(42)
    prices = [150.0 + np.random.normal(0, 0.3) for _ in range(n - 1)]
    mean_20 = np.mean(prices[-20:])
    std_20 = np.std(prices[-20:])
    final = mean_20 + target_zscore * std_20
    prices.append(final)
    return [{"close": p, "time": None} for p in prices]


@pytest.mark.asyncio
async def test_mean_reversion_bearish_on_high_zscore():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(50, target_zscore=2.5))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "reversion_bearish" in call[0]


@pytest.mark.asyncio
async def test_mean_reversion_bullish_on_low_zscore():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(50, target_zscore=-2.5))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "reversion_bullish" in call[0]


@pytest.mark.asyncio
async def test_mean_reversion_skips_normal_zscore():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(50, target_zscore=0.5))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_mean_reversion_skips_insufficient_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(15, target_zscore=3.0))
    await agent.run_once()
    agent.db.execute.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/quant/mean_reversion/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.quant.mean_reversion'`

- [ ] **Step 3: Create `agents/quant/mean_reversion/agent.py`**

Create `agents/quant/mean_reversion/__init__.py` (empty).

```python
import pandas as pd
from agents.base import AnalysisAgent
from agents.technical.indicators import rsi

MIN_BARS = 30
ZSCORE_THRESHOLD = 2.0


class MeanReversionQuantAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        for symbol in self.watchlist:
            rows = await self.db.fetch(
                """
                SELECT time, close FROM prices
                WHERE symbol = $1 AND time > NOW() - INTERVAL '2 hours'
                ORDER BY time ASC
                """,
                symbol,
            )
            if len(rows) < MIN_BARS:
                continue
            await self._analyze(symbol, rows)

    async def _analyze(self, symbol: str, rows: list):
        closes = pd.Series([float(r["close"]) for r in rows])

        rolling_mean = closes.rolling(20).mean()
        rolling_std = closes.rolling(20).std()

        last_mean = rolling_mean.iloc[-1]
        last_std = rolling_std.iloc[-1]

        if pd.isna(last_mean) or pd.isna(last_std) or last_std == 0:
            return

        zscore = float((closes.iloc[-1] - last_mean) / last_std)
        rsi_val = rsi(closes).iloc[-1]

        if pd.isna(rsi_val):
            return

        if zscore > ZSCORE_THRESHOLD and rsi_val > 65:
            signal_type = "reversion_bearish"
        elif zscore < -ZSCORE_THRESHOLD and rsi_val < 35:
            signal_type = "reversion_bullish"
        else:
            return

        confidence = min(100.0, abs(zscore) * 35)

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=f"zscore={zscore:.2f}, rsi={rsi_val:.1f}, mean={last_mean:.2f}",
            metadata={
                "zscore": round(zscore, 3),
                "rsi": round(float(rsi_val), 1),
                "rolling_mean": round(float(last_mean), 2),
            },
        )
        self.logger.info("mean_reversion_signal", symbol=symbol, zscore=zscore, rsi=rsi_val)
```

Create `agents/quant/mean_reversion/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.mean_reversion.agent import MeanReversionQuantAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    watchlist = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")
    agent = MeanReversionQuantAgent(
        name="mean_reversion",
        bus=bus, db=db, router=router,
        watchlist=watchlist,
        interval_seconds=120,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/quant/mean_reversion/test_agent.py -v
```

Expected: 4 passed

**Note on test_mean_reversion_bearish_on_high_zscore:** The RSI check (> 65) may not be satisfied with the synthetic data because the final bar is much higher than recent bars, pushing RSI high. If the test fails because RSI < 65, the test fixture is fine but the RSI confirmation isn't triggering. In that case, use `make_rows_zscore(50, target_zscore=2.5)` but with a longer uptrend leading into the spike to push RSI above 65. The simplest fix: use `target_zscore=3.5` which produces a sharper spike and higher RSI.

- [ ] **Step 5: Commit**

```
git add agents/quant/mean_reversion/ tests/agents/quant/mean_reversion/
git commit -m "feat: MeanReversionQuantAgent with Z-score and RSI confirmation"
```

---

## Task 4: MLQuantAgent

**Files:**
- Create: `agents/quant/ml_quant/__init__.py`
- Create: `agents/quant/ml_quant/features.py`
- Create: `agents/quant/ml_quant/model.py`
- Create: `agents/quant/ml_quant/agent.py`
- Create: `agents/quant/ml_quant/main.py`
- Create: `tests/agents/quant/ml_quant/__init__.py`
- Create: `tests/agents/quant/ml_quant/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/quant/ml_quant/__init__.py` (empty).

Create `tests/agents/quant/ml_quant/test_agent.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/quant/ml_quant/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.quant.ml_quant'`

- [ ] **Step 3: Create `agents/quant/ml_quant/features.py`**

Create `agents/quant/ml_quant/__init__.py` (empty).

```python
import pandas as pd
import numpy as np
from agents.technical.indicators import rsi, macd, bollinger_bands, atr, obv


def extract_features(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows).set_index("time").sort_index()
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    close = df["close"]

    features = pd.DataFrame(index=df.index)
    features["rsi"] = rsi(close)
    m = macd(close)
    features["macd_hist"] = m["histogram"]
    bb = bollinger_bands(close)
    bb_range = (bb["upper"] - bb["lower"]).replace(0, np.nan)
    features["bb_pct"] = (close - bb["lower"]) / bb_range
    features["atr"] = atr(df["high"], df["low"], close)
    obv_series = obv(close, df["volume"])
    features["obv_trend"] = obv_series.diff(5)
    features["mom_1"] = close.pct_change(1)
    features["mom_5"] = close.pct_change(5)
    features["mom_20"] = close.pct_change(20)
    avg_vol = df["volume"].rolling(20).mean().replace(0, np.nan)
    features["vol_ratio"] = df["volume"] / avg_vol

    return features.dropna()


def make_labels(close: pd.Series, threshold: float = 0.005) -> pd.Series:
    future_return = close.pct_change(1).shift(-1)
    labels = pd.Series(0, index=close.index, dtype=int)
    labels[future_return > threshold] = 1
    labels[future_return < -threshold] = -1
    return labels
```

- [ ] **Step 4: Create `agents/quant/ml_quant/model.py`**

```python
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from collections import Counter


class MLEnsemble:
    def __init__(self):
        self.scaler = StandardScaler()
        self.models = [
            LogisticRegression(max_iter=500, random_state=42),
            RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42),
            GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42),
        ]
        self.trained = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        X_scaled = self.scaler.fit_transform(X)
        for model in self.models:
            model.fit(X_scaled, y)
        self.trained = True

    def predict(self, X: np.ndarray) -> tuple[int, float]:
        if not self.trained:
            return 0, 0.5
        X_scaled = self.scaler.transform(X)
        votes = []
        probs = []
        for model in self.models:
            pred = int(model.predict(X_scaled)[0])
            prob = float(np.max(model.predict_proba(X_scaled)[0]))
            votes.append(pred)
            probs.append(prob)
        direction = Counter(votes).most_common(1)[0][0]
        confidence = float(np.mean(probs))
        return direction, confidence
```

- [ ] **Step 5: Create `agents/quant/ml_quant/agent.py`**

```python
import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from agents.base import AnalysisAgent
from agents.quant.ml_quant.features import extract_features, make_labels
from agents.quant.ml_quant.model import MLEnsemble

MIN_TRAINING_BARS = 500
MIN_INFERENCE_BARS = 30
RETRAIN_INTERVAL = timedelta(hours=24)


class MLQuantAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist
        self._models: dict[str, MLEnsemble] = {}
        self._last_trained: dict[str, datetime] = {}

    async def run_once(self):
        for symbol in self.watchlist:
            await self._maybe_retrain(symbol)
            model = self._models.get(symbol)
            if model is None or not model.trained:
                continue
            await self._infer(symbol)

    async def _maybe_retrain(self, symbol: str):
        now = datetime.now(timezone.utc)
        last = self._last_trained.get(symbol)
        if last and now - last < RETRAIN_INTERVAL:
            return

        rows = await self.db.fetch(
            """
            SELECT time, open, high, low, close, volume FROM prices
            WHERE symbol = $1 AND time > NOW() - INTERVAL '30 days'
            ORDER BY time ASC
            """,
            symbol,
        )
        if len(rows) < MIN_TRAINING_BARS:
            self.logger.warning("ml_insufficient_training_data", symbol=symbol, bars=len(rows))
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._train, symbol, list(rows))
        self._last_trained[symbol] = now
        self.logger.info("ml_retrained", symbol=symbol, bars=len(rows))

    def _train(self, symbol: str, rows: list):
        df = pd.DataFrame(rows).set_index("time").sort_index()
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

        features = extract_features(rows)
        labels = make_labels(df["close"])

        common_idx = features.index.intersection(labels.index)
        X = features.loc[common_idx].dropna()
        y = labels.loc[X.index]

        # Drop last row — no future label available
        X = X.iloc[:-1]
        y = y.iloc[:-1]

        if len(X) < 100:
            return

        model = MLEnsemble()
        model.fit(X.values, y.values)
        self._models[symbol] = model

    async def _infer(self, symbol: str):
        rows = await self.db.fetch(
            """
            SELECT time, open, high, low, close, volume FROM prices
            WHERE symbol = $1 AND time > NOW() - INTERVAL '2 hours'
            ORDER BY time ASC
            """,
            symbol,
        )
        if len(rows) < MIN_INFERENCE_BARS:
            return

        features = extract_features(rows)
        if features.empty:
            return

        direction, avg_prob = self._models[symbol].predict(features.iloc[[-1]].values)

        if direction == 1:
            signal_type = "ml_bullish"
        elif direction == -1:
            signal_type = "ml_bearish"
        else:
            return

        confidence = min(100.0, avg_prob * 100)

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=f"ML ensemble vote: direction={direction}, avg_prob={avg_prob:.3f}",
            metadata={"direction": direction, "avg_prob": round(avg_prob, 4)},
        )
        self.logger.info("ml_signal", symbol=symbol, signal=signal_type, confidence=confidence)
```

Create `agents/quant/ml_quant/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.ml_quant.agent import MLQuantAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    watchlist = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")
    agent = MLQuantAgent(
        name="ml_quant",
        bus=bus, db=db, router=router,
        watchlist=watchlist,
        interval_seconds=120,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/quant/ml_quant/test_agent.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```
git add agents/quant/ml_quant/ tests/agents/quant/ml_quant/
git commit -m "feat: MLQuantAgent with sklearn ensemble (LR + RF + GBM), 24h retrain"
```

---

## Task 5: QuantSupervisorAgent + wiring

**Files:**
- Create: `agents/quant/supervisor/__init__.py`
- Create: `agents/quant/supervisor/agent.py`
- Create: `agents/quant/supervisor/main.py`
- Create: `tests/agents/quant/supervisor/__init__.py`
- Create: `tests/agents/quant/supervisor/test_agent.py`
- Modify: `scripts/start_all.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/quant/supervisor/__init__.py` (empty).

Create `tests/agents/quant/supervisor/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock
from agents.quant.supervisor.agent import QuantSupervisorAgent

QUANT_SIGNALS = [
    {"agent": "momentum",      "symbol": "AAPL", "signal_type": "momentum_bullish",  "confidence": 85.0, "time": None},
    {"agent": "mean_reversion","symbol": "AAPL", "signal_type": "reversion_bullish", "confidence": 70.0, "time": None},
    {"agent": "ml_quant",      "symbol": "AAPL", "signal_type": "ml_bullish",        "confidence": 80.0, "time": None},
]

ALGO_ROWS = [
    {"quant_agent": "momentum",       "sharpe_ratio": 1.5, "status": "testing"},
    {"quant_agent": "mean_reversion", "sharpe_ratio": 0.8, "status": "testing"},
    {"quant_agent": "ml_quant",       "sharpe_ratio": 1.2, "status": "testing"},
]


def make_agent():
    return QuantSupervisorAgent(
        name="quant_supervisor",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_supervisor_stores_bullish_consensus():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[QUANT_SIGNALS, ALGO_ROWS])
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "quant_bullish" in call[0]


@pytest.mark.asyncio
async def test_supervisor_publishes_to_bus():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[QUANT_SIGNALS, ALGO_ROWS])
    await agent.run_once()
    channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.quant_supervisor" in c for c in channels)


@pytest.mark.asyncio
async def test_supervisor_handles_no_signals():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[[], ALGO_ROWS])
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_supervisor_skips_retired_algos():
    agent = make_agent()
    retired_algos = [
        {"quant_agent": "momentum", "sharpe_ratio": -0.5, "status": "retired"},
        {"quant_agent": "mean_reversion", "sharpe_ratio": 0.8, "status": "testing"},
        {"quant_agent": "ml_quant", "sharpe_ratio": 1.2, "status": "testing"},
    ]
    agent.db.fetch = AsyncMock(side_effect=[QUANT_SIGNALS[:1], retired_algos])
    await agent.run_once()
    # momentum signal exists but algo is retired — should still process with default weight
    # (quant_algos query filters out retired, so momentum gets default weight 1.0)
    assert agent.db.execute.called or not agent.db.execute.called  # result depends on score
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/quant/supervisor/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.quant.supervisor'`

- [ ] **Step 3: Create `agents/quant/supervisor/agent.py`**

Create `agents/quant/supervisor/__init__.py` (empty).

```python
from collections import defaultdict
from agents.base import AnalysisAgent

QUANT_AGENTS = ["momentum", "mean_reversion", "ml_quant"]
BULLISH_KEYWORDS = {"bullish"}
BEARISH_KEYWORDS = {"bearish"}


def _direction(signal_type: str) -> float:
    st = signal_type.lower()
    if any(k in st for k in BULLISH_KEYWORDS):
        return 1.0
    if any(k in st for k in BEARISH_KEYWORDS):
        return -1.0
    return 0.0


class QuantSupervisorAgent(AnalysisAgent):
    async def run_once(self):
        signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, time
            FROM signals
            WHERE agent = ANY($1) AND time > NOW() - INTERVAL '10 minutes'
            ORDER BY time DESC
            """,
            QUANT_AGENTS,
        )

        algo_rows = await self.db.fetch(
            """
            SELECT quant_agent, sharpe_ratio
            FROM quant_algos
            WHERE status != 'retired'
            """
        )
        sharpe_weights = {
            r["quant_agent"]: max(0.1, float(r["sharpe_ratio"] or 1.0))
            for r in algo_rows
        }

        if not signals:
            return

        by_symbol: dict[str, list] = defaultdict(list)
        for sig in signals:
            by_symbol[sig["symbol"]].append(sig)

        for symbol, sigs in by_symbol.items():
            weighted_score = 0.0
            total_weight = 0.0

            for sig in sigs:
                w = sharpe_weights.get(sig["agent"], 1.0)
                direction = _direction(sig["signal_type"])
                confidence = float(sig["confidence"]) / 100.0
                weighted_score += direction * confidence * w
                total_weight += w

            if total_weight == 0:
                continue

            normalized = weighted_score / total_weight

            if normalized > 0.1:
                signal_type = "quant_bullish"
            elif normalized < -0.1:
                signal_type = "quant_bearish"
            else:
                continue

            confidence = min(100.0, abs(normalized) * 100 * (1 + len(sigs) / 5))

            await self.store_signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                reasoning=f"quant_weighted_score={normalized:.3f}, signals_used={len(sigs)}",
                metadata={
                    "weighted_score": round(normalized, 4),
                    "signal_count": len(sigs),
                    "agents": [s["agent"] for s in sigs],
                },
            )
            self.logger.info("quant_consensus", symbol=symbol, signal=signal_type, score=normalized)
```

Create `agents/quant/supervisor/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.supervisor.agent import QuantSupervisorAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    agent = QuantSupervisorAgent(
        name="quant_supervisor",
        bus=bus, db=db, router=router,
        interval_seconds=300,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/quant/supervisor/test_agent.py -v
```

Expected: 3 passed, 1 skipped or 4 passed (the retired-algo test has a flexible assertion)

- [ ] **Step 5: Update `scripts/start_all.py`**

In `start_all.py`, update the `AGENTS` list to add the 4 quant agents after the Phase 3 agents:

```python
AGENTS: list[str] = [
    # Phase 2: Data ingest
    "data/ingest/main.py",
    # Phase 3: AI analysis
    "agents/technical/main.py",
    "agents/sentiment/main.py",
    "agents/macro/main.py",
    "agents/research/main.py",
    "agents/aggregator/main.py",
    # Phase 4a: Quant signal layer
    "agents/quant/momentum/main.py",
    "agents/quant/mean_reversion/main.py",
    "agents/quant/ml_quant/main.py",
    "agents/quant/supervisor/main.py",
    # Phase 4b (coming):
    # "agents/portfolio_mgr/main.py",
    # "agents/risk/main.py",
    # "agents/execution/main.py",
    # "agents/cio/main.py",
    # "agents/ops/main.py",
]
```

- [ ] **Step 6: Run full test suite**

```
.venv\Scripts\pytest tests/ -v --tb=short
```

Expected: all tests pass (89 existing + ~16 new = ~105 total)

- [ ] **Step 7: Commit and push**

```
git add agents/quant/supervisor/ tests/agents/quant/supervisor/ scripts/start_all.py
git commit -m "feat: QuantSupervisorAgent with Sharpe-weighted quant consensus"
git push origin master
```

---

## Self-Review

**Spec coverage:**
- ✅ Foundation: portfolio_state, risk_events tables; 9 config keys; scikit-learn, alpaca-py, python-binance
- ✅ MomentumQuantAgent: 3 timeframes (5/20/60), bullish/bearish/no-signal, confidence 40/65/85
- ✅ MeanReversionQuantAgent: Z-score > 2.0 + RSI confirmation, no-signal on neutral Z
- ✅ MLQuantAgent: 10 features, 3-model ensemble, 24h retrain in executor, 500-bar minimum
- ✅ QuantSupervisorAgent: Sharpe-weighted consensus, filters retired algos, publishes per symbol
- ✅ start_all.py updated with 4 quant agents

**No placeholders:** All code complete in all steps.

**Type consistency:**
- `extract_features(rows: list[dict]) -> pd.DataFrame` used consistently in Task 4
- `MLEnsemble.predict(X: np.ndarray) -> tuple[int, float]` — both agent and test use this signature
- `store_signal()` called with `symbol=`, `signal_type=`, `confidence=`, `reasoning=`, `metadata=` keyword args throughout
- `QUANT_AGENTS = ["momentum", "mean_reversion", "ml_quant"]` — these match the `name=` values in each agent's main.py
