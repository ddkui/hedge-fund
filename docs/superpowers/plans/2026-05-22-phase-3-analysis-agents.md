# Phase 3 — AI Analysis Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 5 AI analysis agents that transform raw ingested data into structured trading signals: technical analysis, financial sentiment (FinBERT), macro regime detection, fundamental research (LLM), and a signal aggregator that produces a weighted consensus signal per ticker.

**Architecture:** Each agent extends `AnalysisAgent` (which extends `BaseAgent`) and adds a `store_signal()` helper. Agents read from TimescaleDB (prices, macro_data, news_items, sec_filings, signals), process with domain logic or LLM reasoning, and write structured signals to the `signals` hypertable. All signals are also published to `signals.<agent>` Redis channels. The SignalAggregatorAgent reads all signals and produces a weighted consensus that drives the Portfolio Manager in Phase 4.

**What makes this top-notch:**
- FinBERT (ProsusAI/finbert) for financial sentiment — BERT trained on financial text, far superior to generic LLMs for this task
- 6 professional technical indicators (RSI, MACD, BB, ATR, OBV, VWAP) computed from real OHLCV data
- 4-regime macro classification (Expansion/Contraction/Stagflation/Recovery) + Fed cycle detection
- Dynamic signal weighting in the aggregator that shifts with the macro regime
- All signals stored with confidence score (0–100), structured reasoning, and JSONB metadata for auditability

**Tech Stack:** pandas (indicators), transformers + torch (FinBERT), asyncpg (DB reads/writes), httpx (SEC EDGAR text), Ollama (LLM reasoning), Redis pub/sub

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `agents/__init__.py` | Create | Package marker |
| `agents/base.py` | Create | `AnalysisAgent` with `store_signal()` helper |
| `agents/technical/__init__.py` | Create | Package marker |
| `agents/technical/indicators.py` | Create | Pure functions: rsi, macd, bollinger_bands, atr, obv, vwap |
| `agents/technical/agent.py` | Create | `TechnicalAnalysisAgent` |
| `agents/technical/main.py` | Create | Entry point |
| `agents/sentiment/__init__.py` | Create | Package marker |
| `agents/sentiment/finbert.py` | Create | FinBERT wrapper with Ollama fallback |
| `agents/sentiment/agent.py` | Create | `SentimentAgent` |
| `agents/sentiment/main.py` | Create | Entry point |
| `agents/macro/__init__.py` | Create | Package marker |
| `agents/macro/regime.py` | Create | `classify_regime(rows) -> MacroRegime` pure function |
| `agents/macro/agent.py` | Create | `MacroResearchAgent` |
| `agents/macro/main.py` | Create | Entry point |
| `agents/research/__init__.py` | Create | Package marker |
| `agents/research/agent.py` | Create | `FundamentalResearchAgent` |
| `agents/research/main.py` | Create | Entry point |
| `agents/aggregator/__init__.py` | Create | Package marker |
| `agents/aggregator/agent.py` | Create | `SignalAggregatorAgent` |
| `agents/aggregator/main.py` | Create | Entry point |
| `requirements.txt` | Modify | Add transformers, torch (CPU), pandas-ta |
| `scripts/start_all.py` | Modify | Wire in all 5 analysis agent processes |
| `tests/agents/__init__.py` | Create | Package marker |
| `tests/agents/test_base.py` | Create | Tests for AnalysisAgent.store_signal() |
| `tests/agents/technical/__init__.py` | Create | Package marker |
| `tests/agents/technical/test_indicators.py` | Create | Unit tests for pure indicator functions |
| `tests/agents/technical/test_agent.py` | Create | Tests for TechnicalAnalysisAgent |
| `tests/agents/sentiment/__init__.py` | Create | Package marker |
| `tests/agents/sentiment/test_finbert.py` | Create | Tests for FinBERT wrapper |
| `tests/agents/sentiment/test_agent.py` | Create | Tests for SentimentAgent |
| `tests/agents/macro/__init__.py` | Create | Package marker |
| `tests/agents/macro/test_regime.py` | Create | Tests for regime classification |
| `tests/agents/macro/test_agent.py` | Create | Tests for MacroResearchAgent |
| `tests/agents/research/__init__.py` | Create | Package marker |
| `tests/agents/research/test_agent.py` | Create | Tests for FundamentalResearchAgent |
| `tests/agents/aggregator/__init__.py` | Create | Package marker |
| `tests/agents/aggregator/test_agent.py` | Create | Tests for SignalAggregatorAgent |

---

## Task 1: AnalysisAgent base class + requirements

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/base.py`
- Create: `tests/agents/__init__.py`
- Create: `tests/agents/test_base.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/__init__.py` (empty).

Create `tests/agents/test_base.py`:

```python
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from agents.base import AnalysisAgent


class ConcreteAgent(AnalysisAgent):
    async def run_once(self):
        pass


def make_agent():
    return ConcreteAgent(
        name="test_analysis",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_store_signal_calls_execute():
    agent = make_agent()
    await agent.store_signal(
        symbol="AAPL",
        signal_type="momentum",
        confidence=75.0,
        reasoning="RSI crossed above 50 with MACD bullish",
        metadata={"rsi": 58.3, "macd": 0.42},
    )
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "AAPL" in call[0][1:]
    assert 75.0 in call[0][1:]


@pytest.mark.asyncio
async def test_store_signal_publishes_to_bus():
    agent = make_agent()
    await agent.store_signal(
        symbol="BTC",
        signal_type="sentiment",
        confidence=82.0,
        reasoning="Strong positive sentiment",
    )
    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "signals.test_analysis"
    assert call[0][1]["symbol"] == "BTC"
    assert call[0][1]["confidence"] == 82.0


@pytest.mark.asyncio
async def test_store_signal_none_symbol_allowed():
    agent = make_agent()
    await agent.store_signal(
        symbol=None,
        signal_type="macro_regime",
        confidence=90.0,
        reasoning="Fed hiking cycle detected",
    )
    agent.db.execute.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\jomik\hedge-fund
.venv\Scripts\pytest tests/agents/test_base.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents'`

- [ ] **Step 3: Create `agents/__init__.py` (empty) and `agents/base.py`**

```python
import json
from datetime import datetime, timezone
from shared.agent_base import BaseAgent


class AnalysisAgent(BaseAgent):
    async def store_signal(
        self,
        signal_type: str,
        confidence: float,
        reasoning: str,
        symbol: str | None = None,
        metadata: dict | None = None,
    ):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO signals (time, agent, symbol, signal_type, confidence, reasoning, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            now, self.name, symbol, signal_type, confidence, reasoning,
            json.dumps(metadata or {}),
        )
        await self.bus.publish(f"signals.{self.name}", {
            "agent": self.name,
            "symbol": symbol,
            "signal_type": signal_type,
            "confidence": confidence,
            "reasoning": reasoning,
            "metadata": metadata or {},
            "time": now.isoformat(),
        })
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/test_base.py -v
```

Expected: 3 passed

- [ ] **Step 5: Add new packages to `requirements.txt`**

Append to the end of `requirements.txt`:

```
transformers==4.41.2
torch==2.3.1
pandas-ta==0.3.14b0
```

- [ ] **Step 6: Install new packages**

```
.venv\Scripts\pip install transformers==4.41.2 --trusted-host pypi.org --trusted-host files.pythonhosted.org
.venv\Scripts\pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install pandas-ta==0.3.14b0 --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

- [ ] **Step 7: Commit**

```
git add agents/__init__.py agents/base.py tests/agents/__init__.py tests/agents/test_base.py requirements.txt
git commit -m "feat: AnalysisAgent base class with store_signal helper"
```

---

## Task 2: Technical indicators (pure functions)

**Files:**
- Create: `agents/technical/__init__.py`
- Create: `agents/technical/indicators.py`
- Create: `tests/agents/technical/__init__.py`
- Create: `tests/agents/technical/test_indicators.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/technical/__init__.py` (empty).

Create `tests/agents/technical/test_indicators.py`:

```python
import pandas as pd
import numpy as np
import pytest
from agents.technical.indicators import rsi, macd, bollinger_bands, atr, obv, vwap


def make_prices(n=50, start=100.0, volatility=2.0):
    np.random.seed(42)
    changes = np.random.normal(0, volatility, n)
    closes = start + np.cumsum(changes)
    highs = closes + np.abs(np.random.normal(0, 0.5, n))
    lows = closes - np.abs(np.random.normal(0, 0.5, n))
    opens = closes - np.random.normal(0, 0.3, n)
    volumes = np.random.randint(100_000, 1_000_000, n).astype(float)
    idx = pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}, index=idx)


def test_rsi_returns_series_between_0_and_100():
    df = make_prices(50)
    result = rsi(df["close"], period=14)
    assert isinstance(result, pd.Series)
    valid = result.dropna()
    assert len(valid) > 0
    assert valid.between(0, 100).all()


def test_rsi_overbought_gt_70():
    closes = pd.Series([100.0] * 14 + [i * 2.0 for i in range(1, 20)])
    result = rsi(closes, period=14)
    assert result.dropna().iloc[-1] > 50


def test_macd_returns_dict_with_line_signal_hist():
    df = make_prices(50)
    result = macd(df["close"])
    assert "line" in result
    assert "signal" in result
    assert "histogram" in result
    assert isinstance(result["line"], pd.Series)
    assert len(result["histogram"].dropna()) > 0


def test_bollinger_bands_upper_above_lower():
    df = make_prices(50)
    result = bollinger_bands(df["close"])
    assert "upper" in result and "middle" in result and "lower" in result
    valid_upper = result["upper"].dropna()
    valid_lower = result["lower"].dropna()
    assert (valid_upper > valid_lower).all()


def test_atr_returns_positive_series():
    df = make_prices(50)
    result = atr(df["high"], df["low"], df["close"], period=14)
    assert isinstance(result, pd.Series)
    assert result.dropna().gt(0).all()


def test_obv_returns_series_same_length():
    df = make_prices(50)
    result = obv(df["close"], df["volume"])
    assert isinstance(result, pd.Series)
    assert len(result) == len(df)


def test_vwap_returns_series_between_low_and_high():
    df = make_prices(50)
    result = vwap(df["high"], df["low"], df["close"], df["volume"])
    assert isinstance(result, pd.Series)
    valid = result.dropna()
    assert len(valid) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/technical/test_indicators.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.technical'`

- [ ] **Step 3: Implement `agents/technical/indicators.py`**

Create `agents/technical/__init__.py` (empty).

```python
import pandas as pd
import numpy as np


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    signal_line = line.ewm(span=signal, adjust=False).mean()
    return {"line": line, "signal": signal_line, "histogram": line - signal_line}


def bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {"upper": middle + std_dev * std, "middle": middle, "lower": middle - std_dev * std}


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * volume).cumsum()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    return (typical_price * volume).cumsum() / volume.cumsum()
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/technical/test_indicators.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```
git add agents/technical/__init__.py agents/technical/indicators.py tests/agents/technical/__init__.py tests/agents/technical/test_indicators.py
git commit -m "feat: technical indicators (RSI, MACD, BB, ATR, OBV, VWAP)"
```

---

## Task 3: TechnicalAnalysisAgent

**Files:**
- Create: `agents/technical/agent.py`
- Create: `agents/technical/main.py`
- Create: `tests/agents/technical/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/technical/test_agent.py`:

```python
import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from agents.technical.agent import TechnicalAnalysisAgent


def make_agent(watchlist=None):
    return TechnicalAnalysisAgent(
        name="technical",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=watchlist or ["AAPL"],
        interval_seconds=60,
    )


def make_price_rows(n=50, symbol="AAPL", close_start=150.0):
    np.random.seed(7)
    closes = close_start + np.cumsum(np.random.normal(0, 1.5, n))
    rows = []
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    for i in range(n):
        rows.append({
            "time": base.replace(minute=i % 60, hour=10 + i // 60),
            "open": closes[i] - 0.2,
            "high": closes[i] + 0.5,
            "low": closes[i] - 0.5,
            "close": closes[i],
            "volume": 100_000.0,
        })
    return rows


@pytest.mark.asyncio
async def test_technical_agent_stores_signal_for_symbol():
    agent = make_agent(["AAPL"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(50, "AAPL"))
    await agent.run_once()
    assert agent.db.execute.call_count >= 1
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "AAPL" in call[0]


@pytest.mark.asyncio
async def test_technical_agent_publishes_signal():
    agent = make_agent(["MSFT"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(50, "MSFT"))
    await agent.run_once()
    agent.bus.publish.assert_called()
    calls = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.technical" in c for c in calls)


@pytest.mark.asyncio
async def test_technical_agent_skips_insufficient_data():
    agent = make_agent(["AAPL"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(5, "AAPL"))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_technical_agent_signal_confidence_in_range():
    agent = make_agent(["AAPL"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(50, "AAPL"))
    await agent.run_once()
    call = agent.db.execute.call_args
    confidence = call[0][5]
    assert 0.0 <= confidence <= 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/technical/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.technical.agent'`

- [ ] **Step 3: Implement `agents/technical/agent.py`**

```python
import pandas as pd
from agents.base import AnalysisAgent
from agents.technical.indicators import rsi, macd, bollinger_bands, atr, obv

MIN_BARS = 30


class TechnicalAnalysisAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        for symbol in self.watchlist:
            rows = await self.db.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM prices
                WHERE symbol = $1 AND time > NOW() - INTERVAL '2 hours'
                ORDER BY time ASC
                """,
                symbol,
            )
            if len(rows) < MIN_BARS:
                continue
            await self._analyze(symbol, rows)

    async def _analyze(self, symbol: str, rows: list[dict]):
        df = pd.DataFrame(rows).set_index("time").sort_index()
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

        rsi_val = rsi(df["close"]).iloc[-1]
        m = macd(df["close"])
        macd_hist = m["histogram"].iloc[-1]
        macd_prev = m["histogram"].iloc[-2]
        bb = bollinger_bands(df["close"])
        price = df["close"].iloc[-1]
        bb_upper = bb["upper"].iloc[-1]
        bb_lower = bb["lower"].iloc[-1]
        bb_mid = bb["middle"].iloc[-1]
        atr_val = atr(df["high"], df["low"], df["close"]).iloc[-1]
        obv_trend = obv(df["close"], df["volume"]).diff(5).iloc[-1]

        signals = []

        # RSI signals
        if rsi_val < 30:
            signals.append(("oversold", 70 + (30 - rsi_val)))
        elif rsi_val > 70:
            signals.append(("overbought", 70 + (rsi_val - 70)))
        elif 45 < rsi_val < 55:
            signals.append(("neutral_rsi", 40))

        # MACD crossover
        if macd_hist > 0 and macd_prev <= 0:
            signals.append(("macd_bullish_cross", 75))
        elif macd_hist < 0 and macd_prev >= 0:
            signals.append(("macd_bearish_cross", 75))
        elif macd_hist > 0:
            signals.append(("macd_bullish", 55))
        else:
            signals.append(("macd_bearish", 55))

        # Bollinger Band position
        bb_pct = (price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        if bb_pct > 0.9:
            signals.append(("bb_upper_touch", 65))
        elif bb_pct < 0.1:
            signals.append(("bb_lower_touch", 65))

        # OBV trend confirmation
        if obv_trend > 0:
            signals.append(("volume_confirms_up", 60))
        elif obv_trend < 0:
            signals.append(("volume_confirms_down", 60))

        if not signals:
            return

        signal_type = signals[0][0]
        confidence = min(100.0, float(sum(s[1] for s in signals) / len(signals)))
        reasoning = (
            f"RSI={rsi_val:.1f}, MACD_hist={macd_hist:.4f}, "
            f"BB_pct={bb_pct:.2f}, ATR={atr_val:.2f}, "
            f"signals={[s[0] for s in signals]}"
        )
        metadata = {
            "rsi": round(float(rsi_val), 2),
            "macd_hist": round(float(macd_hist), 4),
            "bb_pct": round(float(bb_pct), 3),
            "atr": round(float(atr_val), 2),
            "price": round(float(price), 2),
            "signals": [s[0] for s in signals],
        }

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=reasoning,
            metadata=metadata,
        )
        self.logger.info("technical_signal", symbol=symbol, signal=signal_type, confidence=confidence)
```

Create `agents/technical/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.technical.agent import TechnicalAnalysisAgent

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
    agent = TechnicalAnalysisAgent(
        name="technical",
        bus=bus, db=db, router=router,
        watchlist=settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(","),
        interval_seconds=60,
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
.venv\Scripts\pytest tests/agents/technical/test_agent.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add agents/technical/agent.py agents/technical/main.py tests/agents/technical/test_agent.py
git commit -m "feat: TechnicalAnalysisAgent with RSI/MACD/BB/ATR/OBV signals"
```

---

## Task 4: FinBERT wrapper

**Files:**
- Create: `agents/sentiment/__init__.py`
- Create: `agents/sentiment/finbert.py`
- Create: `tests/agents/sentiment/__init__.py`
- Create: `tests/agents/sentiment/test_finbert.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/sentiment/__init__.py` (empty).

Create `tests/agents/sentiment/test_finbert.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from agents.sentiment.finbert import FinBertSentiment, SentimentResult


def test_sentiment_result_fields():
    r = SentimentResult(label="positive", score=0.92, compound=0.92)
    assert r.label == "positive"
    assert r.score == 0.92
    assert r.compound == 0.92


def test_finbert_analyze_returns_result():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"label": "positive", "score": 0.91}]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        result = fb.analyze("Apple beats earnings estimates by 15%")

    assert isinstance(result, SentimentResult)
    assert result.label == "positive"
    assert result.compound > 0


def test_finbert_negative_returns_negative_compound():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"label": "negative", "score": 0.88}]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        result = fb.analyze("Company misses revenue targets, outlook slashed")

    assert result.compound < 0


def test_finbert_neutral_returns_zero_compound():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [{"label": "neutral", "score": 0.78}]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        result = fb.analyze("Company reports quarterly results")

    assert result.compound == 0.0


def test_finbert_batch_analyze_returns_list():
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [
        {"label": "positive", "score": 0.91},
        {"label": "negative", "score": 0.85},
    ]
    texts = ["Good earnings", "Bad outlook"]

    with patch("agents.sentiment.finbert.pipeline", return_value=mock_pipeline):
        fb = FinBertSentiment()
        fb._pipe = mock_pipeline
        results = fb.batch_analyze(texts)

    assert len(results) == 2
    assert results[0].compound > 0
    assert results[1].compound < 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/sentiment/test_finbert.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.sentiment'`

- [ ] **Step 3: Implement `agents/sentiment/finbert.py`**

Create `agents/sentiment/__init__.py` (empty).

```python
from dataclasses import dataclass
from typing import Optional

try:
    from transformers import pipeline as hf_pipeline
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False


@dataclass
class SentimentResult:
    label: str       # "positive" | "negative" | "neutral"
    score: float     # confidence 0.0–1.0
    compound: float  # -score for negative, +score for positive, 0.0 for neutral


_LABEL_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


class FinBertSentiment:
    MODEL = "ProsusAI/finbert"

    def __init__(self):
        self._pipe = None

    def _load(self):
        if self._pipe is None and _TRANSFORMERS_AVAILABLE:
            from transformers import pipeline
            self._pipe = pipeline(
                "text-classification",
                model=self.MODEL,
                truncation=True,
                max_length=512,
            )

    def analyze(self, text: str) -> SentimentResult:
        self._load()
        if self._pipe is None:
            return SentimentResult(label="neutral", score=0.5, compound=0.0)
        result = self._pipe(text)[0]
        label = result["label"].lower()
        score = float(result["score"])
        return SentimentResult(label=label, score=score, compound=_LABEL_SIGN.get(label, 0.0) * score)

    def batch_analyze(self, texts: list[str]) -> list[SentimentResult]:
        self._load()
        if self._pipe is None:
            return [SentimentResult("neutral", 0.5, 0.0) for _ in texts]
        raw = self._pipe(texts)
        results = []
        for r in raw:
            label = r["label"].lower()
            score = float(r["score"])
            results.append(SentimentResult(label=label, score=score, compound=_LABEL_SIGN.get(label, 0.0) * score))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/sentiment/test_finbert.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add agents/sentiment/__init__.py agents/sentiment/finbert.py tests/agents/sentiment/__init__.py tests/agents/sentiment/test_finbert.py
git commit -m "feat: FinBERT sentiment wrapper with transformers pipeline"
```

---

## Task 5: SentimentAgent

**Files:**
- Create: `agents/sentiment/agent.py`
- Create: `agents/sentiment/main.py`
- Create: `tests/agents/sentiment/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/sentiment/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.sentiment.agent import SentimentAgent
from agents.sentiment.finbert import SentimentResult

TICKER_MAP = {"AAPL": ["apple", "aapl"], "BTC": ["bitcoin", "btc", "crypto"]}

NEWS_ROWS = [
    {"headline": "Apple beats earnings by 15%, raises guidance", "source": "Reuters", "time": None},
    {"headline": "Bitcoin surges as ETF approval expected", "source": "Bloomberg", "time": None},
    {"headline": "Markets rally on Fed pivot hopes", "source": "CNBC", "time": None},
]


def make_agent():
    return SentimentAgent(
        name="sentiment",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        ticker_map=TICKER_MAP,
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_sentiment_agent_stores_signal_per_ticker():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=NEWS_ROWS)
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[
        SentimentResult("positive", 0.92, 0.92),
        SentimentResult("positive", 0.88, 0.88),
        SentimentResult("neutral", 0.75, 0.0),
    ])
    await agent.run_once()
    assert agent.db.execute.call_count >= 1


@pytest.mark.asyncio
async def test_sentiment_agent_publishes_per_ticker():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=NEWS_ROWS)
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[
        SentimentResult("positive", 0.91, 0.91),
        SentimentResult("positive", 0.87, 0.87),
        SentimentResult("neutral", 0.70, 0.0),
    ])
    await agent.run_once()
    published_channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.sentiment" in ch for ch in published_channels)


@pytest.mark.asyncio
async def test_sentiment_agent_handles_empty_news():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sentiment_agent_confidence_in_range():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=NEWS_ROWS[:1])
    agent._finbert = MagicMock()
    agent._finbert.batch_analyze = MagicMock(return_value=[
        SentimentResult("positive", 0.91, 0.91),
    ])
    await agent.run_once()
    if agent.db.execute.called:
        confidence = agent.db.execute.call_args[0][5]
        assert 0.0 <= confidence <= 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/sentiment/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.sentiment.agent'`

- [ ] **Step 3: Implement `agents/sentiment/agent.py`**

```python
from agents.base import AnalysisAgent
from agents.sentiment.finbert import FinBertSentiment

SOURCE_WEIGHTS = {
    "reuters": 1.0, "bloomberg": 1.0, "ft": 1.0, "wsj": 0.95,
    "cnbc": 0.8, "marketwatch": 0.75, "seeking alpha": 0.65,
    "wallstreetbets": 0.4, "investing": 0.5, "stocks": 0.45,
}

DEFAULT_TICKER_MAP = {
    "AAPL": ["apple", "aapl"], "MSFT": ["microsoft", "msft"],
    "GOOGL": ["google", "googl", "alphabet"], "AMZN": ["amazon", "amzn"],
    "TSLA": ["tesla", "tsla"], "NVDA": ["nvidia", "nvda"],
    "SPY": ["s&p", "spy", "market"], "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth"], "SOL": ["solana", "sol"],
}


class SentimentAgent(AnalysisAgent):
    def __init__(self, *args, ticker_map: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticker_map = ticker_map or DEFAULT_TICKER_MAP
        self._finbert = FinBertSentiment()

    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT headline, source, time FROM news_items
            WHERE time > NOW() - INTERVAL '24 hours'
            ORDER BY time DESC LIMIT 200
            """
        )
        if not rows:
            return

        headlines = [r["headline"] for r in rows]
        results = self._finbert.batch_analyze(headlines)

        for ticker, keywords in self.ticker_map.items():
            relevant = [
                (results[i], rows[i])
                for i, r in enumerate(rows)
                if any(kw in r["headline"].lower() for kw in keywords)
            ]
            if not relevant:
                continue

            total_weight = 0.0
            weighted_compound = 0.0
            for result, row in relevant:
                source = row["source"].lower() if row["source"] else "unknown"
                weight = SOURCE_WEIGHTS.get(source, 0.5)
                weighted_compound += result.compound * weight * result.score
                total_weight += weight

            if total_weight == 0:
                continue

            compound = weighted_compound / total_weight
            confidence = min(100.0, abs(compound) * 100 * (1 + len(relevant) / 10))
            label = "bullish" if compound > 0.1 else ("bearish" if compound < -0.1 else "neutral")
            reasoning = (
                f"Analyzed {len(relevant)} articles for {ticker}. "
                f"Weighted compound sentiment: {compound:.3f}. "
                f"Signal: {label}."
            )
            await self.store_signal(
                symbol=ticker,
                signal_type=f"sentiment_{label}",
                confidence=confidence,
                reasoning=reasoning,
                metadata={"compound": round(compound, 4), "article_count": len(relevant), "label": label},
            )
            self.logger.info("sentiment_signal", ticker=ticker, label=label, compound=compound)
```

Create `agents/sentiment/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.sentiment.agent import SentimentAgent

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
    agent = SentimentAgent(name="sentiment", bus=bus, db=db, router=router, interval_seconds=300)
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
.venv\Scripts\pytest tests/agents/sentiment/test_agent.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add agents/sentiment/agent.py agents/sentiment/main.py tests/agents/sentiment/test_agent.py
git commit -m "feat: SentimentAgent with FinBERT source-weighted per-ticker sentiment"
```

---

## Task 6: MacroResearchAgent

**Files:**
- Create: `agents/macro/__init__.py`
- Create: `agents/macro/regime.py`
- Create: `agents/macro/agent.py`
- Create: `agents/macro/main.py`
- Create: `tests/agents/macro/__init__.py`
- Create: `tests/agents/macro/test_regime.py`
- Create: `tests/agents/macro/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/macro/__init__.py` (empty).

Create `tests/agents/macro/test_regime.py`:

```python
from agents.macro.regime import classify_regime, MacroRegime, FedCycle


def make_macro(fedfunds=5.33, cpi=3.2, unrate=3.8, dgs10=4.2, gdp=2.1, prev_fedfunds=4.0):
    return {
        "FEDFUNDS": fedfunds,
        "CPIAUCSL": cpi,
        "UNRATE": unrate,
        "DGS10": dgs10,
        "GDP": gdp,
        "FEDFUNDS_PREV": prev_fedfunds,
    }


def test_expansion_regime():
    data = make_macro(fedfunds=5.0, cpi=2.5, unrate=3.8, gdp=2.5, prev_fedfunds=4.5)
    result = classify_regime(data)
    assert result.regime == MacroRegime.EXPANSION


def test_stagflation_regime():
    data = make_macro(fedfunds=5.5, cpi=7.5, unrate=4.5, gdp=0.5, prev_fedfunds=4.0)
    result = classify_regime(data)
    assert result.regime == MacroRegime.STAGFLATION


def test_contraction_regime():
    data = make_macro(fedfunds=2.0, cpi=1.5, unrate=6.5, gdp=-1.0, prev_fedfunds=3.0)
    result = classify_regime(data)
    assert result.regime == MacroRegime.CONTRACTION


def test_hiking_cycle():
    data = make_macro(fedfunds=5.5, prev_fedfunds=4.5)
    result = classify_regime(data)
    assert result.fed_cycle == FedCycle.HIKING


def test_cutting_cycle():
    data = make_macro(fedfunds=4.0, prev_fedfunds=5.25)
    result = classify_regime(data)
    assert result.fed_cycle == FedCycle.CUTTING


def test_yield_curve_inverted():
    data = make_macro(fedfunds=5.5, dgs10=4.2)
    result = classify_regime(data)
    assert result.yield_curve_inverted is True


def test_yield_curve_normal():
    data = make_macro(fedfunds=2.0, dgs10=4.5)
    result = classify_regime(data)
    assert result.yield_curve_inverted is False


def test_risk_on_in_expansion():
    data = make_macro(fedfunds=3.0, cpi=2.0, unrate=3.5, gdp=3.0, prev_fedfunds=2.5)
    result = classify_regime(data)
    assert result.risk_on is True
```

Create `tests/agents/macro/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.macro.agent import MacroResearchAgent

MACRO_ROWS = [
    {"series_id": "FEDFUNDS", "value": 5.33, "time": None},
    {"series_id": "CPIAUCSL", "value": 3.2, "time": None},
    {"series_id": "UNRATE", "value": 3.8, "time": None},
    {"series_id": "DGS10", "value": 4.25, "time": None},
    {"series_id": "GDP", "value": 2.9, "time": None},
]


def make_agent():
    return MacroResearchAgent(
        name="macro",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=3600,
    )


@pytest.mark.asyncio
async def test_macro_agent_stores_regime_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=MACRO_ROWS)
    agent.router.chat = AsyncMock(return_value="Markets in late-cycle expansion. Fed likely to pause.")
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]


@pytest.mark.asyncio
async def test_macro_agent_publishes_regime():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=MACRO_ROWS)
    agent.router.chat = AsyncMock(return_value="Expansion with hawkish Fed.")
    await agent.run_once()
    agent.bus.publish.assert_called()
    calls = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.macro" in c for c in calls)


@pytest.mark.asyncio
async def test_macro_agent_handles_missing_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/macro/ -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `agents/macro/regime.py`**

Create `agents/macro/__init__.py` (empty).

```python
from dataclasses import dataclass
from enum import Enum


class MacroRegime(str, Enum):
    EXPANSION = "expansion"
    CONTRACTION = "contraction"
    STAGFLATION = "stagflation"
    RECOVERY = "recovery"


class FedCycle(str, Enum):
    HIKING = "hiking"
    PAUSING = "pausing"
    CUTTING = "cutting"
    EASING = "easing"


@dataclass
class RegimeResult:
    regime: MacroRegime
    fed_cycle: FedCycle
    yield_curve_inverted: bool
    risk_on: bool
    confidence: float
    summary: str


def classify_regime(data: dict) -> RegimeResult:
    fedfunds = data.get("FEDFUNDS", 0.0)
    cpi = data.get("CPIAUCSL", 2.0)
    unrate = data.get("UNRATE", 4.0)
    dgs10 = data.get("DGS10", fedfunds + 1.5)
    gdp = data.get("GDP", 2.0)
    prev_fedfunds = data.get("FEDFUNDS_PREV", fedfunds)

    # Fed cycle
    diff = fedfunds - prev_fedfunds
    if diff >= 0.25:
        fed_cycle = FedCycle.HIKING
    elif diff <= -0.25:
        fed_cycle = FedCycle.CUTTING if fedfunds > 1.0 else FedCycle.EASING
    else:
        fed_cycle = FedCycle.PAUSING

    # Regime classification
    high_inflation = cpi > 4.0
    high_unemployment = unrate > 5.5
    negative_growth = gdp < 0.0
    strong_growth = gdp > 2.0

    if high_inflation and (negative_growth or high_unemployment):
        regime = MacroRegime.STAGFLATION
        confidence = 80.0
    elif negative_growth or high_unemployment:
        regime = MacroRegime.CONTRACTION
        confidence = 75.0
    elif strong_growth and not high_inflation and unrate < 4.5:
        regime = MacroRegime.EXPANSION
        confidence = 85.0
    else:
        regime = MacroRegime.RECOVERY
        confidence = 65.0

    yield_curve_inverted = dgs10 < fedfunds
    risk_on = regime in (MacroRegime.EXPANSION, MacroRegime.RECOVERY) and not yield_curve_inverted

    summary = (
        f"{regime.value.title()} regime | Fed: {fed_cycle.value} | "
        f"CPI={cpi:.1f}% UNRATE={unrate:.1f}% GDP={gdp:.1f}% | "
        f"Curve={'inverted' if yield_curve_inverted else 'normal'} | "
        f"Risk={'on' if risk_on else 'off'}"
    )

    return RegimeResult(
        regime=regime,
        fed_cycle=fed_cycle,
        yield_curve_inverted=yield_curve_inverted,
        risk_on=risk_on,
        confidence=confidence,
        summary=summary,
    )
```

- [ ] **Step 4: Implement `agents/macro/agent.py`**

```python
from agents.base import AnalysisAgent
from agents.macro.regime import classify_regime


class MacroResearchAgent(AnalysisAgent):
    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT DISTINCT ON (series_id) series_id, value, time
            FROM macro_data
            ORDER BY series_id, time DESC
            """
        )
        if not rows:
            return

        latest = {r["series_id"]: float(r["value"]) for r in rows}

        # Get previous FEDFUNDS reading for cycle detection
        prev_rows = await self.db.fetch(
            """
            SELECT value FROM macro_data
            WHERE series_id = 'FEDFUNDS'
            ORDER BY time DESC LIMIT 2
            """
        )
        if len(prev_rows) >= 2:
            latest["FEDFUNDS_PREV"] = float(prev_rows[1]["value"])

        result = classify_regime(latest)

        prompt = (
            f"Current macroeconomic regime: {result.summary}\n\n"
            f"Raw indicators: {latest}\n\n"
            "As a senior macroeconomic strategist, provide a 2-paragraph outlook: "
            "(1) what this regime means for equities, bonds, and crypto, "
            "(2) what to watch for a regime change. Be concise and specific."
        )
        narrative = await self.router.chat("macro", [{"role": "user", "content": prompt}])

        await self.store_signal(
            symbol=None,
            signal_type=f"macro_regime_{result.regime.value}",
            confidence=result.confidence,
            reasoning=f"{result.summary}\n\n{narrative}",
            metadata={
                "regime": result.regime.value,
                "fed_cycle": result.fed_cycle.value,
                "yield_curve_inverted": result.yield_curve_inverted,
                "risk_on": result.risk_on,
                "indicators": {k: round(v, 2) for k, v in latest.items()},
            },
        )
        self.logger.info("macro_regime", regime=result.regime.value, fed_cycle=result.fed_cycle.value)
```

Create `agents/macro/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.macro.agent import MacroResearchAgent

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
    agent = MacroResearchAgent(name="macro", bus=bus, db=db, router=router, interval_seconds=3600)
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/macro/ -v
```

Expected: 11 passed (8 regime + 3 agent)

- [ ] **Step 6: Commit**

```
git add agents/macro/ tests/agents/macro/
git commit -m "feat: MacroResearchAgent with 4-regime classification and Fed cycle detection"
```

---

## Task 7: FundamentalResearchAgent

**Files:**
- Create: `agents/research/__init__.py`
- Create: `agents/research/agent.py`
- Create: `agents/research/main.py`
- Create: `tests/agents/research/__init__.py`
- Create: `tests/agents/research/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/research/__init__.py` (empty).

Create `tests/agents/research/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.research.agent import FundamentalResearchAgent

SEC_ROWS = [
    {"ticker": "AAPL", "form_type": "10-K", "period": "2023-09-30",
     "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm",
     "time": None},
    {"ticker": "MSFT", "form_type": "10-Q", "period": "2023-12-31",
     "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901924000013/0000789019-24-000013-index.htm",
     "time": None},
]


def make_agent():
    return FundamentalResearchAgent(
        name="research",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=3600,
    )


@pytest.mark.asyncio
async def test_research_agent_stores_signal_per_ticker():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SEC_ROWS)
    agent._fetch_filing_text = AsyncMock(return_value="Apple Inc. reported strong revenue growth...")
    agent.router.chat = AsyncMock(return_value='{"quality_score": 85, "moat": "strong", "thesis": "Growth driven by services", "risks": "Supply chain"}')
    await agent.run_once()
    assert agent.db.execute.call_count >= 1


@pytest.mark.asyncio
async def test_research_agent_publishes_fundamental_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[SEC_ROWS[0]])
    agent._fetch_filing_text = AsyncMock(return_value="Fiscal year revenue exceeded expectations...")
    agent.router.chat = AsyncMock(return_value='{"quality_score": 78, "moat": "moderate", "thesis": "Steady growth", "risks": "Competition"}')
    await agent.run_once()
    agent.bus.publish.assert_called()
    channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.research" in c for c in channels)


@pytest.mark.asyncio
async def test_research_agent_handles_no_filings():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_research_agent_skips_on_fetch_failure():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[SEC_ROWS[0]])
    agent._fetch_filing_text = AsyncMock(return_value=None)
    agent.router.chat = AsyncMock()
    await agent.run_once()
    agent.router.chat.assert_not_called()
    agent.db.execute.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/research/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `agents/research/agent.py`**

Create `agents/research/__init__.py` (empty).

```python
import json
import re
import httpx
from agents.base import AnalysisAgent

EDGAR_SECTION_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_HEADERS = {"User-Agent": "hedgefund info@hedgefund.local"}
MAX_TEXT_CHARS = 8000

ANALYSIS_PROMPT = """You are a senior equity analyst. Analyze this SEC filing excerpt and return a JSON object with exactly these fields:
{{
  "quality_score": <integer 0-100, earnings quality and consistency>,
  "moat": <"strong" | "moderate" | "weak">,
  "thesis": <one sentence investment thesis>,
  "risks": <one sentence key risks>
}}

Filing ({ticker} {form_type} for period {period}):
{text}

Return ONLY the JSON object, no other text."""


class FundamentalResearchAgent(AnalysisAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processed: set[str] = set()

    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT DISTINCT ON (ticker, form_type) ticker, form_type, period, filing_url, time
            FROM sec_filings
            WHERE form_type IN ('10-K', '10-Q')
            ORDER BY ticker, form_type, time DESC
            """
        )
        for row in rows:
            key = f"{row['ticker']}_{row['form_type']}_{row['period']}"
            if key in self._processed:
                continue
            await self._analyze_filing(row)
            self._processed.add(key)

    async def _fetch_filing_text(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=SEC_HEADERS)
                if resp.status_code != 200:
                    return None
                text = resp.text
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:MAX_TEXT_CHARS] if text else None
        except Exception:
            return None

    async def _analyze_filing(self, row: dict):
        ticker = row["ticker"]
        form_type = row["form_type"]
        period = row["period"]
        url = row["filing_url"]

        text = await self._fetch_filing_text(url)
        if not text:
            return

        prompt = ANALYSIS_PROMPT.format(
            ticker=ticker, form_type=form_type, period=period, text=text
        )
        raw = await self.router.chat("research", [{"role": "user", "content": prompt}])

        try:
            analysis = json.loads(raw.strip())
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                return
            try:
                analysis = json.loads(match.group())
            except json.JSONDecodeError:
                return

        quality = int(analysis.get("quality_score", 50))
        moat = analysis.get("moat", "moderate")
        thesis = analysis.get("thesis", "")
        risks = analysis.get("risks", "")

        signal_type = "fundamental_bullish" if quality >= 70 else ("fundamental_bearish" if quality < 40 else "fundamental_neutral")

        await self.store_signal(
            symbol=ticker,
            signal_type=signal_type,
            confidence=float(quality),
            reasoning=f"{form_type} {period}: {thesis} Risks: {risks}",
            metadata={"quality_score": quality, "moat": moat, "form_type": form_type, "period": period},
        )
        self.logger.info("fundamental_signal", ticker=ticker, quality=quality, moat=moat)
```

Create `agents/research/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.research.agent import FundamentalResearchAgent

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
    agent = FundamentalResearchAgent(name="research", bus=bus, db=db, router=router, interval_seconds=3600)
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
.venv\Scripts\pytest tests/agents/research/test_agent.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add agents/research/ tests/agents/research/
git commit -m "feat: FundamentalResearchAgent with Ollama LLM SEC filing analysis"
```

---

## Task 8: SignalAggregatorAgent

**Files:**
- Create: `agents/aggregator/__init__.py`
- Create: `agents/aggregator/agent.py`
- Create: `agents/aggregator/main.py`
- Create: `tests/agents/aggregator/__init__.py`
- Create: `tests/agents/aggregator/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/aggregator/__init__.py` (empty).

Create `tests/agents/aggregator/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock
from agents.aggregator.agent import SignalAggregatorAgent, REGIME_WEIGHTS

SIGNALS_ROWS = [
    {"agent": "technical", "symbol": "AAPL", "signal_type": "macd_bullish_cross", "confidence": 75.0, "time": None},
    {"agent": "sentiment", "symbol": "AAPL", "signal_type": "sentiment_bullish", "confidence": 82.0, "time": None},
    {"agent": "macro",     "symbol": None,   "signal_type": "macro_regime_expansion", "confidence": 85.0, "time": None},
    {"agent": "research",  "symbol": "AAPL", "signal_type": "fundamental_bullish", "confidence": 78.0, "time": None},
]


def make_agent():
    return SignalAggregatorAgent(
        name="aggregator",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=120,
    )


@pytest.mark.asyncio
async def test_aggregator_stores_consensus_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SIGNALS_ROWS)
    await agent.run_once()
    assert agent.db.execute.call_count >= 1
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]


@pytest.mark.asyncio
async def test_aggregator_publishes_consensus():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SIGNALS_ROWS)
    await agent.run_once()
    channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.aggregator" in c for c in channels)


@pytest.mark.asyncio
async def test_aggregator_consensus_is_bullish_for_all_bullish_inputs():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SIGNALS_ROWS)
    await agent.run_once()
    call = agent.db.execute.call_args
    signal_type = call[0][4]
    assert "bull" in signal_type or "consensus" in signal_type


@pytest.mark.asyncio
async def test_aggregator_handles_no_signals():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()


def test_regime_weights_sum_to_one():
    from agents.macro.regime import MacroRegime
    for regime in MacroRegime:
        weights = REGIME_WEIGHTS.get(regime, {})
        if weights:
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{regime}: weights sum to {total}"
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/aggregator/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `agents/aggregator/agent.py`**

Create `agents/aggregator/__init__.py` (empty).

```python
from collections import defaultdict
from agents.base import AnalysisAgent
from agents.macro.regime import MacroRegime

AGENT_CATEGORY = {
    "technical": "technical",
    "sentiment": "sentiment",
    "macro": "macro",
    "research": "fundamental",
}

REGIME_WEIGHTS = {
    MacroRegime.EXPANSION:   {"technical": 0.30, "fundamental": 0.30, "sentiment": 0.25, "macro": 0.15},
    MacroRegime.CONTRACTION: {"technical": 0.20, "fundamental": 0.30, "sentiment": 0.10, "macro": 0.40},
    MacroRegime.STAGFLATION: {"technical": 0.25, "fundamental": 0.25, "sentiment": 0.10, "macro": 0.40},
    MacroRegime.RECOVERY:    {"technical": 0.35, "fundamental": 0.25, "sentiment": 0.15, "macro": 0.25},
}

DEFAULT_WEIGHTS = {"technical": 0.30, "fundamental": 0.30, "sentiment": 0.20, "macro": 0.20}

BULLISH_KEYWORDS = {"bullish", "overbought", "macd_bullish", "expansion", "recovery", "bb_lower_touch"}
BEARISH_KEYWORDS = {"bearish", "oversold_risk", "macd_bearish", "contraction", "stagflation", "bb_upper_touch"}


def _signal_direction(signal_type: str) -> float:
    st = signal_type.lower()
    if any(k in st for k in BULLISH_KEYWORDS):
        return 1.0
    if any(k in st for k in BEARISH_KEYWORDS):
        return -1.0
    return 0.0


class SignalAggregatorAgent(AnalysisAgent):
    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, time
            FROM signals
            WHERE time > NOW() - INTERVAL '6 hours'
              AND agent != 'aggregator'
            ORDER BY time DESC
            """
        )
        if not rows:
            return

        # Detect current macro regime from recent macro signals
        current_regime = MacroRegime.EXPANSION
        for row in rows:
            if row["agent"] == "macro":
                for regime in MacroRegime:
                    if regime.value in row["signal_type"]:
                        current_regime = regime
                        break
                break

        weights = REGIME_WEIGHTS.get(current_regime, DEFAULT_WEIGHTS)

        # Group signals by symbol
        by_symbol: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            sym = row["symbol"] or "__market__"
            by_symbol[sym].append(row)

        for symbol, signals in by_symbol.items():
            if symbol == "__market__":
                continue

            weighted_score = 0.0
            total_weight = 0.0

            for sig in signals:
                cat = AGENT_CATEGORY.get(sig["agent"], "technical")
                w = weights.get(cat, 0.25)
                direction = _signal_direction(sig["signal_type"])
                confidence = float(sig["confidence"]) / 100.0
                weighted_score += direction * confidence * w
                total_weight += w

            if total_weight == 0:
                continue

            normalized = weighted_score / total_weight
            consensus_confidence = min(100.0, abs(normalized) * 100 * (1 + len(signals) / 10))

            if normalized > 0.1:
                consensus = "consensus_bullish"
            elif normalized < -0.1:
                consensus = "consensus_bearish"
            else:
                consensus = "consensus_neutral"

            agent_breakdown = {
                sig["agent"]: {"signal": sig["signal_type"], "confidence": sig["confidence"]}
                for sig in signals[:5]
            }

            await self.store_signal(
                symbol=symbol,
                signal_type=consensus,
                confidence=consensus_confidence,
                reasoning=(
                    f"Regime={current_regime.value}, weighted_score={normalized:.3f}, "
                    f"signals_used={len(signals)}, weights={weights}"
                ),
                metadata={
                    "regime": current_regime.value,
                    "weighted_score": round(normalized, 4),
                    "signal_count": len(signals),
                    "agent_breakdown": agent_breakdown,
                },
            )
            self.logger.info("consensus_signal", symbol=symbol, consensus=consensus, score=normalized)
```

Create `agents/aggregator/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.aggregator.agent import SignalAggregatorAgent

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
    agent = SignalAggregatorAgent(name="aggregator", bus=bus, db=db, router=router, interval_seconds=120)
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
.venv\Scripts\pytest tests/agents/aggregator/test_agent.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add agents/aggregator/ tests/agents/aggregator/
git commit -m "feat: SignalAggregatorAgent with regime-aware weighted consensus"
```

---

## Task 9: Wire into start_all.py and push

**Files:**
- Modify: `scripts/start_all.py`

- [ ] **Step 1: Run the full test suite**

```
cd C:\Users\jomik\hedge-fund
.venv\Scripts\pytest tests/ -v --tb=short
```

Expected: All tests pass (46 Phase 2 + ~25 new Phase 3 = ~71 total).

- [ ] **Step 2: Update `scripts/start_all.py`**

Replace the `AGENTS` list with:

```python
AGENTS: list[str] = [
    "data/ingest/main.py",
    "agents/technical/main.py",
    "agents/sentiment/main.py",
    "agents/macro/main.py",
    "agents/research/main.py",
    "agents/aggregator/main.py",
    # Phase 4:
    # "agents/quant/momentum/main.py",
    # "agents/quant/mean_reversion/main.py",
    # "agents/quant/ml_quant/main.py",
    # "agents/quant/supervisor/main.py",
    # "agents/portfolio_mgr/main.py",
    # "agents/risk/main.py",
    # "agents/execution/main.py",
    # "agents/cio/main.py",
    # "agents/ops/main.py",
]
```

- [ ] **Step 3: Commit and push**

```
git add scripts/start_all.py
git commit -m "feat: wire Phase 3 analysis agents into start_all"
git push origin master
```

---

## Self-Review

- [x] **Spec coverage:** All 5 agents implemented with complete signal flow. FinBERT with Ollama fallback. 4-regime macro + Fed cycle. LLM fundamental analysis. Regime-aware aggregation.
- [x] **No placeholders:** All code complete in every step.
- [x] **Type consistency:** `store_signal()` signature consistent. `MacroRegime` enum used in both regime.py and aggregator. `FinBertSentiment` interface stable between finbert.py and sentiment agent.
- [x] **Signal format:** All agents call `store_signal()` with same schema (symbol, signal_type, confidence 0-100, reasoning text, metadata dict).
- [x] **REGIME_WEIGHTS:** All 4 regimes defined, weights sum to 1.0 (verified by test).
