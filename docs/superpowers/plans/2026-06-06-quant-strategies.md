# New Quant Strategies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new quant strategy agents — News-Momentum (combines sentiment signal with price momentum) and VWAP Deviation (trades reversion to volume-weighted average price) — both running every 2 minutes and feeding into the existing aggregator pipeline.

**Architecture:** Both agents extend `AnalysisAgent`, call `store_signal()`, and publish to Redis. They read their tunable parameters from `agent_params.yaml` (keyed by current macro regime) — if the file doesn't exist yet, they fall back to hardcoded defaults. Both registered in `start_all.py` and `KNOWN_AGENT_INTERVALS` in the Engineer agent.

**Tech Stack:** Python asyncio, asyncpg, pandas, structlog — same stack as existing quant agents.

---

## File Structure

```
agents/quant/news_momentum/__init__.py     NEW
agents/quant/news_momentum/agent.py       NEW — NewsMomentumAgent
agents/quant/news_momentum/main.py        NEW
agents/quant/vwap/__init__.py              NEW
agents/quant/vwap/agent.py               NEW — VWAPDeviationAgent
agents/quant/vwap/main.py                NEW
tests/agents/quant/test_news_momentum.py  NEW
tests/agents/quant/test_vwap.py           NEW
scripts/start_all.py                      MODIFY — add both agents
agents/ops/agent.py                       MODIFY — add to KNOWN_AGENT_INTERVALS
```

---

## Task 1: Shared param loader utility

Both agents need to read from `agent_params.yaml` (written by the self-improving optimizer). Create a lightweight reader they both share.

**Files:**
- Modify: `shared/config.py` (add one helper)

- [ ] **Step 1: Add `load_agent_params` helper to shared**

Create `shared/agent_params.py`:

```python
# shared/agent_params.py
"""
Reads per-agent, per-regime parameters from agent_params.yaml.
Falls back to provided defaults if file doesn't exist or key is missing.
"""
import os
from typing import Any


def load_agent_params(agent_name: str, regime: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """Load parameters for agent_name in the given regime from agent_params.yaml."""
    try:
        import yaml
        path = os.path.join(os.getcwd(), "agent_params.yaml")
        if not os.path.exists(path):
            return defaults
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        agent_section = data.get(agent_name, {})
        # Try exact regime, fall back to _default, then to provided defaults
        params = agent_section.get(regime) or agent_section.get("_default") or {}
        return {**defaults, **params}
    except Exception:
        return defaults
```

- [ ] **Step 2: Write test for param loader**

Create `tests/shared/test_agent_params.py`:

```python
# tests/shared/test_agent_params.py
import pytest
import yaml


def test_load_returns_defaults_when_file_missing():
    from shared.agent_params import load_agent_params
    result = load_agent_params("nonexistent_agent", "expansion", {"threshold": 1.0})
    assert result == {"threshold": 1.0}


def test_load_returns_regime_params(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    params = {
        "news_momentum": {
            "_default": {"composite_threshold": 1.0},
            "expansion": {"composite_threshold": 0.8},
        }
    }
    (tmp_path / "agent_params.yaml").write_text(yaml.dump(params))
    from shared.agent_params import load_agent_params
    result = load_agent_params("news_momentum", "expansion", {"composite_threshold": 1.0})
    assert result["composite_threshold"] == 0.8


def test_load_falls_back_to_default_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    params = {"news_momentum": {"_default": {"composite_threshold": 1.5}}}
    (tmp_path / "agent_params.yaml").write_text(yaml.dump(params))
    from shared.agent_params import load_agent_params
    result = load_agent_params("news_momentum", "unknown_regime", {"composite_threshold": 1.0})
    assert result["composite_threshold"] == 1.5
```

- [ ] **Step 3: Run tests**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/shared/test_agent_params.py -v
```

Expected: `3 passed`

- [ ] **Step 4: Commit**

```powershell
git add shared/agent_params.py tests/shared/test_agent_params.py
git commit -m "feat(quant): shared agent_params loader for regime-aware parameters"
```

---

## Task 2: News-Momentum agent

**Files:**
- Create: `agents/quant/news_momentum/__init__.py`
- Create: `agents/quant/news_momentum/agent.py`
- Create: `agents/quant/news_momentum/main.py`
- Create: `tests/agents/quant/test_news_momentum.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/quant/test_news_momentum.py
import pytest
from unittest.mock import AsyncMock, MagicMock


def make_agent():
    from agents.quant.news_momentum.agent import NewsMomentumAgent
    agent = NewsMomentumAgent.__new__(NewsMomentumAgent)
    agent.name = "news_momentum"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent.store_signal = AsyncMock()
    agent._running = True
    agent.interval_seconds = 120
    agent.watchlist = ["AAPL", "MSFT"]
    return agent


@pytest.mark.asyncio
async def test_bullish_when_both_agree():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bullish_signal", "confidence": 80.0
    })
    # 20 prices trending up: start 100, end 102 (+2%)
    prices = [{"close": 100.0 + i * 0.1} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bullish_signal"


@pytest.mark.asyncio
async def test_neutral_when_directions_diverge():
    agent = make_agent()
    # Sentiment is bearish but price is going up
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bearish_signal", "confidence": 70.0
    })
    prices = [{"close": 100.0 + i * 0.2} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_recent_sentiment():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value=None)
    prices = [{"close": 100.0} for _ in range(20)]
    agent.db.fetch = AsyncMock(return_value=prices)

    await agent._analyze("AAPL", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_bearish_when_both_agree_negative():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bearish_signal", "confidence": 75.0
    })
    prices = [{"close": 110.0 - i * 0.3} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bearish_signal"


@pytest.mark.asyncio
async def test_confidence_bounded():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bullish_signal", "confidence": 100.0
    })
    prices = [{"close": 100.0 + i * 5} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    call = agent.store_signal.call_args
    assert call.kwargs["confidence"] <= 85.0
    assert call.kwargs["confidence"] >= 0.0
```

- [ ] **Step 2: Run to verify tests fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/quant/test_news_momentum.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `agents/quant/news_momentum/__init__.py`**

```python
# agents/quant/news_momentum/__init__.py
```

- [ ] **Step 4: Create `agents/quant/news_momentum/agent.py`**

```python
# agents/quant/news_momentum/agent.py
from agents.base import AnalysisAgent
from shared.agent_params import load_agent_params

DEFAULTS = {
    "sentiment_weight": 0.40,
    "momentum_weight": 0.60,
    "momentum_lookback": 20,
    "composite_threshold": 1.0,
    "sentiment_lookback_hours": 2,
}


class NewsMomentumAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        # Get current regime from Redis
        regime_data = await self.bus.get("macro:current_regime") or {}
        regime = regime_data.get("regime", "expansion")

        for symbol in self.watchlist:
            await self._analyze(symbol, regime)

    async def _analyze(self, symbol: str, regime: str):
        params = load_agent_params("news_momentum", regime, DEFAULTS)
        lookback = int(params["momentum_lookback"])
        sent_hours = int(params["sentiment_lookback_hours"])
        threshold = float(params["composite_threshold"])
        sent_w = float(params["sentiment_weight"])
        mom_w = float(params["momentum_weight"])

        # Latest sentiment signal for this symbol
        sentiment_row = await self.db.fetchrow(
            """
            SELECT signal_type, confidence FROM signals
            WHERE agent = 'sentiment' AND symbol = $1
              AND time > now_or_backtest() - INTERVAL '1 hour' * $2
            ORDER BY time DESC LIMIT 1
            """,
            symbol, sent_hours,
        )
        if sentiment_row is None:
            return  # No recent sentiment → skip

        # Price momentum (lookback candles)
        price_rows = await self.db.fetch(
            "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT $2",
            symbol, lookback,
        )
        if len(price_rows) < 2:
            return

        latest_close = float(price_rows[0]["close"])
        oldest_close = float(price_rows[-1]["close"])
        if oldest_close == 0:
            return
        price_momentum_pct = (latest_close - oldest_close) / oldest_close * 100

        # Direction-adjust sentiment to [-100, +100]
        sig = sentiment_row["signal_type"]
        conf = float(sentiment_row["confidence"])
        if "bullish" in sig:
            sentiment_score = +conf
        elif "bearish" in sig:
            sentiment_score = -conf
        else:
            sentiment_score = 0.0

        # Suppress if directions disagree
        sentiment_dir = 1 if sentiment_score > 0 else (-1 if sentiment_score < 0 else 0)
        momentum_dir = 1 if price_momentum_pct > 0 else (-1 if price_momentum_pct < 0 else 0)
        if sentiment_dir != 0 and momentum_dir != 0 and sentiment_dir != momentum_dir:
            return  # Contradicting signals — suppress

        composite = (sentiment_score * sent_w) + (price_momentum_pct * mom_w)

        if composite > threshold:
            signal_type = "bullish_signal"
        elif composite < -threshold:
            signal_type = "bearish_signal"
        else:
            return  # Within neutral band

        confidence = min(85.0, max(0.0, abs(composite) * 8))

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=round(confidence, 2),
            reasoning=(
                f"News-momentum composite={composite:.2f} (sent={sentiment_score:.1f}×{sent_w}, "
                f"mom={price_momentum_pct:.2f}%×{mom_w}) regime={regime}"
            ),
            metadata={
                "sentiment_score": sentiment_score,
                "price_momentum_pct": round(price_momentum_pct, 4),
                "composite": round(composite, 4),
                "regime": regime,
            },
        )
        self.logger.info("news_momentum_signal", symbol=symbol,
                         signal=signal_type, composite=round(composite, 2))
```

- [ ] **Step 5: Create `agents/quant/news_momentum/main.py`**

```python
# agents/quant/news_momentum/main.py
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.news_momentum.agent import NewsMomentumAgent


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
    watchlist = [s.strip() for s in
                 (settings.stock_watchlist + "," + settings.crypto_watchlist).split(",")
                 if s.strip()]
    agent = NewsMomentumAgent(
        name="news_momentum", bus=bus, db=db, router=router,
        watchlist=watchlist, interval_seconds=120,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/quant/test_news_momentum.py -v
```

Expected: `5 passed`

- [ ] **Step 7: Commit**

```powershell
git add agents/quant/news_momentum/ tests/agents/quant/test_news_momentum.py
git commit -m "feat(quant): News-Momentum agent — sentiment × price composite signal"
```

---

## Task 3: VWAP Deviation agent

**Files:**
- Create: `agents/quant/vwap/__init__.py`
- Create: `agents/quant/vwap/agent.py`
- Create: `agents/quant/vwap/main.py`
- Create: `tests/agents/quant/test_vwap.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/quant/test_vwap.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta


def make_agent():
    from agents.quant.vwap.agent import VWAPDeviationAgent
    agent = VWAPDeviationAgent.__new__(VWAPDeviationAgent)
    agent.name = "vwap"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent.store_signal = AsyncMock()
    agent._running = True
    agent.interval_seconds = 120
    agent.watchlist = ["AAPL", "BTCUSDT"]
    return agent


def _make_candles(n, base_price, base_volume=1000.0):
    now = datetime.now(timezone.utc)
    return [
        {"close": base_price, "volume": base_volume,
         "time": now - timedelta(minutes=n - i)}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_bullish_when_price_below_vwap():
    agent = make_agent()
    candles = _make_candles(20, 100.0)  # uniform → VWAP = 100
    candles[0] = {**candles[0], "close": 97.0}  # current price 3% below VWAP → bullish
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bullish_signal"


@pytest.mark.asyncio
async def test_bearish_when_price_above_vwap():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[0] = {**candles[0], "close": 103.0}  # 3% above VWAP → bearish
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bearish_signal"


@pytest.mark.asyncio
async def test_neutral_within_threshold():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[0] = {**candles[0], "close": 100.3}  # 0.3% — within 1.5% threshold
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_skips_insufficient_candles():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=_make_candles(3, 100.0))

    await agent._analyze("AAPL", "stock", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_vwap_calculation_correct():
    from agents.quant.vwap.agent import _compute_vwap
    # VWAP = sum(close*vol) / sum(vol)
    candles = [
        {"close": 100.0, "volume": 200.0},
        {"close": 110.0, "volume": 100.0},
    ]
    # (100*200 + 110*100) / 300 = (20000+11000)/300 = 103.333...
    vwap = _compute_vwap(candles)
    assert abs(vwap - 103.333) < 0.01


@pytest.mark.asyncio
async def test_confidence_scales_with_deviation():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[0] = {**candles[0], "close": 90.0}  # 10% below → high confidence
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")

    call = agent.store_signal.call_args
    assert call.kwargs["confidence"] > 60.0
    assert call.kwargs["confidence"] <= 80.0
```

- [ ] **Step 2: Run to verify tests fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/quant/test_vwap.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `agents/quant/vwap/__init__.py`**

```python
# agents/quant/vwap/__init__.py
```

- [ ] **Step 4: Create `agents/quant/vwap/agent.py`**

```python
# agents/quant/vwap/agent.py
from datetime import datetime, timezone, timedelta
from agents.base import AnalysisAgent
from shared.agent_params import load_agent_params

DEFAULTS = {
    "deviation_threshold_pct": 1.5,
    "min_candles": 5,
    "crypto_window_hours": 24,
}

CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"}


def _compute_vwap(candles: list[dict]) -> float:
    total_vol = sum(float(c["volume"]) for c in candles)
    if total_vol == 0:
        return float(candles[0]["close"])
    return sum(float(c["close"]) * float(c["volume"]) for c in candles) / total_vol


class VWAPDeviationAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        regime_data = await self.bus.get("macro:current_regime") or {}
        regime = regime_data.get("regime", "expansion")

        for symbol in self.watchlist:
            asset_class = "crypto" if symbol in CRYPTO_SYMBOLS else "stock"
            await self._analyze(symbol, asset_class, regime)

    async def _analyze(self, symbol: str, asset_class: str, regime: str):
        params = load_agent_params("vwap", regime, DEFAULTS)
        threshold = float(params["deviation_threshold_pct"])
        min_candles = int(params["min_candles"])
        crypto_hours = int(params["crypto_window_hours"])

        now = datetime.now(timezone.utc)
        if asset_class == "crypto":
            window_start = now - timedelta(hours=crypto_hours)
        else:
            # NYSE market open: 14:30 UTC
            today = now.date()
            market_open = datetime(today.year, today.month, today.day, 14, 30, tzinfo=timezone.utc)
            window_start = market_open if now >= market_open else (market_open - timedelta(days=1))

        candles = await self.db.fetch(
            "SELECT close, volume, time FROM prices WHERE symbol = $1 AND time >= $2 ORDER BY time ASC",
            symbol, window_start,
        )

        if len(candles) < min_candles:
            return

        vwap = _compute_vwap(candles)
        current_close = float(candles[-1]["close"])  # most recent (last in ASC order)
        if vwap == 0:
            return

        deviation_pct = (current_close - vwap) / vwap * 100

        if deviation_pct < -threshold:
            signal_type = "bullish_signal"
        elif deviation_pct > threshold:
            signal_type = "bearish_signal"
        else:
            return

        confidence = min(80.0, abs(deviation_pct) * 15)

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=round(confidence, 2),
            reasoning=(
                f"VWAP={vwap:.4f}, current={current_close:.4f}, "
                f"deviation={deviation_pct:+.2f}% "
                f"({'below' if deviation_pct < 0 else 'above'} {threshold}% threshold), "
                f"regime={regime}"
            ),
            metadata={
                "vwap": round(vwap, 6),
                "current_close": current_close,
                "deviation_pct": round(deviation_pct, 4),
                "candle_count": len(candles),
                "regime": regime,
            },
        )
        self.logger.info("vwap_signal", symbol=symbol, signal=signal_type,
                         deviation=round(deviation_pct, 2))
```

- [ ] **Step 5: Create `agents/quant/vwap/main.py`**

```python
# agents/quant/vwap/main.py
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.vwap.agent import VWAPDeviationAgent


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
    watchlist = [s.strip() for s in
                 (settings.stock_watchlist + "," + settings.crypto_watchlist).split(",")
                 if s.strip()]
    agent = VWAPDeviationAgent(
        name="vwap", bus=bus, db=db, router=router,
        watchlist=watchlist, interval_seconds=120,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/quant/test_vwap.py -v
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```powershell
git add agents/quant/vwap/ tests/agents/quant/test_vwap.py
git commit -m "feat(quant): VWAP Deviation agent — reversion-to-VWAP signals"
```

---

## Task 4: Register agents in start_all.py and Engineer

**Files:**
- Modify: `scripts/start_all.py`
- Modify: `agents/ops/agent.py`

- [ ] **Step 1: Add to start_all.py**

In `scripts/start_all.py`, add to the AGENTS list under "Phase 4a: Quant signal layer":

```python
    "agents/quant/news_momentum/main.py",
    "agents/quant/vwap/main.py",
```

Add them after `"agents/quant/kronos/main.py"`.

- [ ] **Step 2: Add to KNOWN_AGENT_INTERVALS in Engineer**

In `agents/ops/agent.py`, add to the `KNOWN_AGENT_INTERVALS` dict:

```python
    "news_momentum":       120,
    "vwap":                120,
```

Add them after the `"ml_quant": 120` line.

- [ ] **Step 3: Run full test suite**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all pass (including 11 new quant strategy tests)

- [ ] **Step 4: Commit**

```powershell
git add scripts/start_all.py agents/ops/agent.py
git commit -m "feat(quant): register news_momentum + vwap agents in start_all and Engineer health monitor"
```
