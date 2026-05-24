# Phase 2 — Data Ingest Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 6 data ingest agents that continuously pull market data (stocks, crypto, macro, news, SEC filings, social) into TimescaleDB and publish update events to the Redis bus.

**Architecture:** Each agent inherits from `DataIngestAgent` (extends `BaseAgent`) and implements `run_once()`. External REST APIs are called with `httpx.AsyncClient`; blocking library calls (yfinance, PRAW) run in `asyncio.run_in_executor`. All agents publish to `data.<source>.updated` Redis channels so downstream agents can react.

**Tech Stack:** yfinance (stocks), httpx (Binance/FRED/NewsAPI/SEC EDGAR), praw (Reddit), asyncpg (DB), Redis pub/sub, TimescaleDB

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `data/__init__.py` | Create | Package marker |
| `data/ingest/__init__.py` | Create | Package marker |
| `data/ingest/base.py` | Create | `DataIngestAgent` with `store_prices()` helper |
| `data/ingest/stocks.py` | Create | yfinance OHLCV for US stock watchlist |
| `data/ingest/crypto.py` | Create | Binance REST 1-min bars for crypto watchlist |
| `data/ingest/macro.py` | Create | FRED API — FEDFUNDS, CPI, GDP, UNRATE, DGS10 |
| `data/ingest/news.py` | Create | NewsAPI financial headlines |
| `data/ingest/sec.py` | Create | SEC EDGAR 10-K/10-Q/8-K filings for watchlist |
| `data/ingest/social.py` | Create | Reddit PRAW hot posts from finance subreddits |
| `data/ingest/main.py` | Create | Entry point that starts all 6 ingest agents concurrently |
| `scripts/setup_db.py` | Modify | Add macro_data, news_items, sec_filings tables; unique constraint on prices |
| `shared/config.py` | Modify | Add reddit creds + watchlist config fields |
| `requirements.txt` | Modify | Add yfinance==0.2.38, praw==7.7.1 |
| `scripts/start_all.py` | Modify | Wire in data ingest main.py process |
| `tests/data/__init__.py` | Create | Package marker |
| `tests/data/ingest/__init__.py` | Create | Package marker |
| `tests/data/ingest/test_base.py` | Create | Tests for DataIngestAgent.store_prices() |
| `tests/data/ingest/test_stocks.py` | Create | Tests for StocksIngestAgent |
| `tests/data/ingest/test_crypto.py` | Create | Tests for CryptoIngestAgent |
| `tests/data/ingest/test_macro.py` | Create | Tests for MacroIngestAgent |
| `tests/data/ingest/test_news.py` | Create | Tests for NewsIngestAgent |
| `tests/data/ingest/test_sec.py` | Create | Tests for SecIngestAgent |
| `tests/data/ingest/test_social.py` | Create | Tests for SocialIngestAgent |

---

## Task 1: Schema additions and config updates

**Files:**
- Modify: `scripts/setup_db.py`
- Modify: `shared/config.py`
- Test: `tests/shared/test_config.py` (add assertions for new fields)

- [ ] **Step 1: Write failing config tests**

Add to `tests/shared/test_config.py`:

```python
def test_settings_stock_watchlist_default():
    settings = Settings()
    assert settings.stock_watchlist == "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,SPY,QQQ"

def test_settings_crypto_watchlist_default():
    settings = Settings()
    assert settings.crypto_watchlist == "BTCUSDT,ETHUSDT,SOLUSDT"

def test_settings_reddit_defaults():
    settings = Settings()
    assert settings.reddit_client_id == ""
    assert settings.reddit_client_secret == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\jomik\hedge-fund
.venv\Scripts\pytest tests/shared/test_config.py -v
```

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'stock_watchlist'`

- [ ] **Step 3: Add new fields to `shared/config.py`**

Replace the content of `shared/config.py` with:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    model_tier: int = Field(default=1, ge=1, le=3)

    ollama_host: str = "http://localhost:11434"
    ollama_primary_model: str = "llama3.1:8b"
    ollama_research_model: str = "mistral:7b"
    ollama_shadow_model: str = "phi3:mini"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "hedgefund"
    db_user: str = "hedgefund"
    db_password: str = "changeme"

    paper_trading: bool = True

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    binance_api_key: str = ""
    binance_secret_key: str = ""
    news_api_key: str = ""
    fred_api_key: str = ""
    gmail_sender: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "hedgefund/1.0"

    stock_watchlist: str = "AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,SPY,QQQ"
    crypto_watchlist: str = "BTCUSDT,ETHUSDT,SOLUSDT"

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def db_dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
```

- [ ] **Step 4: Add new tables to `scripts/setup_db.py`**

Append the following SQL to the `SCHEMA` string in `scripts/setup_db.py`, inside the triple-quoted string before the closing `"""`:

```sql
-- Unique constraint on prices for idempotent inserts
DO $$ BEGIN
    ALTER TABLE prices ADD CONSTRAINT prices_time_symbol_unique UNIQUE (time, symbol);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS macro_data (
    time        TIMESTAMPTZ NOT NULL,
    series_id   TEXT NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    source      TEXT NOT NULL DEFAULT 'FRED',
    UNIQUE (time, series_id)
);

CREATE TABLE IF NOT EXISTS news_items (
    id              SERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,
    headline        TEXT NOT NULL,
    url             TEXT NOT NULL DEFAULT '',
    sentiment_score DOUBLE PRECISION,
    UNIQUE (time, source, headline)
);

CREATE TABLE IF NOT EXISTS sec_filings (
    id          SERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    form_type   TEXT NOT NULL,
    period      TEXT NOT NULL,
    filing_url  TEXT NOT NULL,
    summary     TEXT,
    UNIQUE (ticker, form_type, period)
);
```

- [ ] **Step 5: Run config tests to verify they pass**

```
.venv\Scripts\pytest tests/shared/test_config.py -v
```

Expected: all pass (old + new tests)

- [ ] **Step 6: Commit**

```
git add shared/config.py scripts/setup_db.py tests/shared/test_config.py
git commit -m "feat: add ingest config fields and DB tables for macro, news, SEC"
```

---

## Task 2: DataIngestAgent base class

**Files:**
- Create: `data/__init__.py`
- Create: `data/ingest/__init__.py`
- Create: `data/ingest/base.py`
- Create: `tests/data/__init__.py`
- Create: `tests/data/ingest/__init__.py`
- Create: `tests/data/ingest/test_base.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/__init__.py` (empty) and `tests/data/ingest/__init__.py` (empty).

Create `tests/data/ingest/test_base.py`:

```python
import pytest
from unittest.mock import AsyncMock
from data.ingest.base import DataIngestAgent
from datetime import datetime, timezone


class ConcreteIngestAgent(DataIngestAgent):
    async def run_once(self):
        pass


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return ConcreteIngestAgent(
        name="test_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
    )


@pytest.mark.asyncio
async def test_store_prices_calls_executemany():
    agent = make_agent()
    rows = [
        {
            "time": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            "symbol": "AAPL",
            "asset_class": "stock",
            "open": 150.0,
            "high": 151.0,
            "low": 149.0,
            "close": 150.5,
            "volume": 1_000_000.0,
        }
    ]
    await agent.store_prices(rows)
    agent.db.executemany.assert_called_once()
    call_args = agent.db.executemany.call_args
    assert "INSERT INTO prices" in call_args[0][0]
    assert len(call_args[0][1]) == 1
    record = call_args[0][1][0]
    assert record[1] == "AAPL"
    assert record[2] == "stock"
    assert record[6] == 150.5


@pytest.mark.asyncio
async def test_store_prices_empty_list_skips_db():
    agent = make_agent()
    await agent.store_prices([])
    agent.db.executemany.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_base.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data'`

- [ ] **Step 3: Create package markers and base class**

Create `data/__init__.py` (empty file).

Create `data/ingest/__init__.py` (empty file).

Create `data/ingest/base.py`:

```python
from shared.agent_base import BaseAgent


class DataIngestAgent(BaseAgent):
    async def store_prices(self, rows: list[dict]):
        if not rows:
            return
        await self.db.executemany(
            """
            INSERT INTO prices (time, symbol, asset_class, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT ON CONSTRAINT prices_time_symbol_unique DO NOTHING
            """,
            [
                (
                    r["time"],
                    r["symbol"],
                    r["asset_class"],
                    r.get("open"),
                    r.get("high"),
                    r.get("low"),
                    r["close"],
                    r.get("volume"),
                )
                for r in rows
            ],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_base.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```
git add data/__init__.py data/ingest/__init__.py data/ingest/base.py tests/data/__init__.py tests/data/ingest/__init__.py tests/data/ingest/test_base.py
git commit -m "feat: DataIngestAgent base class with store_prices helper"
```

---

## Task 3: StocksIngestAgent

**Files:**
- Create: `data/ingest/stocks.py`
- Create: `tests/data/ingest/test_stocks.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/ingest/test_stocks.py`:

```python
import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from data.ingest.stocks import StocksIngestAgent


def make_agent(watchlist=None):
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return StocksIngestAgent(
        name="stocks_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        watchlist=watchlist or ["AAPL", "MSFT"],
        interval_seconds=60,
    )


def make_fake_df():
    return pd.DataFrame(
        [{"Open": 150.0, "High": 151.0, "Low": 149.0, "Close": 150.5, "Volume": 1_000_000.0}],
        index=pd.DatetimeIndex(["2024-01-01 10:00:00+00:00"]),
    )


@pytest.mark.asyncio
async def test_stocks_agent_stores_prices():
    agent = make_agent(["AAPL"])
    agent._fetch_ticker_history = MagicMock(return_value=make_fake_df())
    await agent.run_once()
    agent.db.executemany.assert_called_once()
    records = agent.db.executemany.call_args[0][1]
    assert len(records) == 1
    assert records[0][1] == "AAPL"
    assert records[0][2] == "stock"
    assert records[0][6] == 150.5


@pytest.mark.asyncio
async def test_stocks_agent_publishes_update():
    agent = make_agent(["AAPL", "MSFT"])
    agent._fetch_ticker_history = MagicMock(return_value=make_fake_df())
    await agent.run_once()
    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.stocks.updated"
    assert call[0][1]["symbols"] == ["AAPL", "MSFT"]


@pytest.mark.asyncio
async def test_stocks_agent_skips_empty_history():
    agent = make_agent(["AAPL"])
    agent._fetch_ticker_history = MagicMock(return_value=pd.DataFrame())
    await agent.run_once()
    agent.db.executemany.assert_not_called()
    agent.bus.publish.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_stocks.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ingest.stocks'`

- [ ] **Step 3: Implement `data/ingest/stocks.py`**

```python
import asyncio
import yfinance as yf
from datetime import timezone
from data.ingest.base import DataIngestAgent

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "SPY", "QQQ"]


class StocksIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str] = DEFAULT_WATCHLIST, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    def _fetch_ticker_history(self, symbol: str):
        return yf.Ticker(symbol).history(period="1d", interval="1m")

    async def run_once(self):
        rows = []
        loop = asyncio.get_event_loop()
        for symbol in self.watchlist:
            hist = await loop.run_in_executor(None, self._fetch_ticker_history, symbol)
            for ts, row in hist.iterrows():
                rows.append({
                    "time": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    "symbol": symbol,
                    "asset_class": "stock",
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
        await self.store_prices(rows)
        await self.bus.publish("data.stocks.updated", {
            "symbols": self.watchlist,
            "bar_count": len(rows),
        })
        self.logger.info("stocks_ingested", symbols=len(self.watchlist), bars=len(rows))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_stocks.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add data/ingest/stocks.py tests/data/ingest/test_stocks.py
git commit -m "feat: StocksIngestAgent with yfinance OHLCV ingest"
```

---

## Task 4: CryptoIngestAgent

**Files:**
- Create: `data/ingest/crypto.py`
- Create: `tests/data/ingest/test_crypto.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/ingest/test_crypto.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from data.ingest.crypto import CryptoIngestAgent

BINANCE_KLINE = [
    1704067200000,  # open time ms
    "42000.00",     # open
    "42500.00",     # high
    "41800.00",     # low
    "42200.00",     # close
    "100.5",        # volume
    1704067259999,  # close time ms
    "4221000.00",   # quote asset volume
    150,            # number of trades
    "60.0",         # taker buy base
    "2532000.00",   # taker buy quote
    "0",            # ignore
]


def make_agent(watchlist=None):
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return CryptoIngestAgent(
        name="crypto_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        watchlist=watchlist or ["BTCUSDT"],
        interval_seconds=30,
    )


@pytest.mark.asyncio
async def test_crypto_agent_fetches_binance_and_stores():
    agent = make_agent(["BTCUSDT"])

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [BINANCE_KLINE]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.crypto.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_called_once()
    records = agent.db.executemany.call_args[0][1]
    assert len(records) == 1
    assert records[0][1] == "BTCUSDT"
    assert records[0][2] == "crypto"
    assert records[0][6] == 42200.0


@pytest.mark.asyncio
async def test_crypto_agent_publishes_update():
    agent = make_agent(["BTCUSDT", "ETHUSDT"])

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [BINANCE_KLINE]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.crypto.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.crypto.updated"
    assert set(call[0][1]["symbols"]) == {"BTCUSDT", "ETHUSDT"}


@pytest.mark.asyncio
async def test_crypto_agent_calls_correct_url():
    agent = make_agent(["SOLUSDT"])

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = []

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.crypto.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    call = mock_client.get.call_args
    assert "binance.com" in call[0][0]
    assert call[1]["params"]["symbol"] == "SOLUSDT"
    assert call[1]["params"]["interval"] == "1m"
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_crypto.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ingest.crypto'`

- [ ] **Step 3: Implement `data/ingest/crypto.py`**

```python
import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
DEFAULT_WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


class CryptoIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str] = DEFAULT_WATCHLIST, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        rows = []
        async with httpx.AsyncClient() as client:
            for symbol in self.watchlist:
                resp = await client.get(
                    BINANCE_KLINES_URL,
                    params={"symbol": symbol, "interval": "1m", "limit": 10},
                )
                resp.raise_for_status()
                for kline in resp.json():
                    rows.append({
                        "time": datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
                        "symbol": symbol,
                        "asset_class": "crypto",
                        "open": float(kline[1]),
                        "high": float(kline[2]),
                        "low": float(kline[3]),
                        "close": float(kline[4]),
                        "volume": float(kline[5]),
                    })
        await self.store_prices(rows)
        await self.bus.publish("data.crypto.updated", {
            "symbols": self.watchlist,
            "bar_count": len(rows),
        })
        self.logger.info("crypto_ingested", symbols=len(self.watchlist), bars=len(rows))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_crypto.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add data/ingest/crypto.py tests/data/ingest/test_crypto.py
git commit -m "feat: CryptoIngestAgent with Binance REST 1-min bars"
```

---

## Task 5: MacroIngestAgent

**Files:**
- Create: `data/ingest/macro.py`
- Create: `tests/data/ingest/test_macro.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/ingest/test_macro.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.macro import MacroIngestAgent

FRED_RESPONSE = {
    "observations": [
        {"date": "2024-01-01", "value": "5.33"},
        {"date": "2023-12-01", "value": "5.33"},
    ]
}


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return MacroIngestAgent(
        name="macro_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        api_key="testkey",
        interval_seconds=3600,
    )


@pytest.mark.asyncio
async def test_macro_agent_stores_observations():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = FRED_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.macro.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    assert agent.db.executemany.call_count >= 1
    first_call = agent.db.executemany.call_args_list[0]
    assert "INSERT INTO macro_data" in first_call[0][0]
    records = first_call[0][1]
    assert len(records) == 2
    assert records[0][1] == "FEDFUNDS"
    assert records[0][2] == 5.33


@pytest.mark.asyncio
async def test_macro_agent_skips_missing_values():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {"date": "2024-01-01", "value": "."},
            {"date": "2023-12-01", "value": "5.33"},
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.macro.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    first_call = agent.db.executemany.call_args_list[0]
    records = first_call[0][1]
    assert len(records) == 1
    assert records[0][2] == 5.33


@pytest.mark.asyncio
async def test_macro_agent_publishes_update():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = FRED_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.macro.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.macro.updated"
    assert "FEDFUNDS" in call[0][1]["series"]
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_macro.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ingest.macro'`

- [ ] **Step 3: Implement `data/ingest/macro.py`**

```python
import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

FRED_SERIES = ["FEDFUNDS", "CPIAUCSL", "GDP", "UNRATE", "DGS10"]
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


class MacroIngestAgent(DataIngestAgent):
    def __init__(self, *args, api_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key

    async def run_once(self):
        async with httpx.AsyncClient() as client:
            for series_id in FRED_SERIES:
                resp = await client.get(
                    FRED_URL,
                    params={
                        "series_id": series_id,
                        "api_key": self.api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 5,
                    },
                )
                resp.raise_for_status()
                observations = resp.json().get("observations", [])
                rows = [
                    (
                        datetime.strptime(obs["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                        series_id,
                        float(obs["value"]),
                        "FRED",
                    )
                    for obs in observations
                    if obs["value"] != "."
                ]
                if rows:
                    await self.db.executemany(
                        "INSERT INTO macro_data (time, series_id, value, source) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                        rows,
                    )
        await self.bus.publish("data.macro.updated", {"series": FRED_SERIES})
        self.logger.info("macro_ingested", series=len(FRED_SERIES))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_macro.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add data/ingest/macro.py tests/data/ingest/test_macro.py
git commit -m "feat: MacroIngestAgent pulling FRED economic series"
```

---

## Task 6: NewsIngestAgent

**Files:**
- Create: `data/ingest/news.py`
- Create: `tests/data/ingest/test_news.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/ingest/test_news.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.news import NewsIngestAgent

NEWSAPI_RESPONSE = {
    "articles": [
        {
            "source": {"name": "Reuters"},
            "title": "Markets rally on rate cut hopes",
            "url": "https://reuters.com/article/1",
            "publishedAt": "2024-01-15T10:30:00Z",
        },
        {
            "source": {"name": "Bloomberg"},
            "title": "Bitcoin surges past 50k",
            "url": "https://bloomberg.com/article/2",
            "publishedAt": "2024-01-15T09:00:00Z",
        },
    ]
}


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return NewsIngestAgent(
        name="news_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        api_key="testkey",
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_news_agent_stores_articles():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = NEWSAPI_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.news.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_called_once()
    call = agent.db.executemany.call_args
    assert "INSERT INTO news_items" in call[0][0]
    records = call[0][1]
    assert len(records) == 2
    assert records[0][2] == "Markets rally on rate cut hopes"
    assert records[1][1] == "Bloomberg"


@pytest.mark.asyncio
async def test_news_agent_publishes_update():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = NEWSAPI_RESPONSE

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.news.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.news.updated"
    assert call[0][1]["article_count"] == 2


@pytest.mark.asyncio
async def test_news_agent_handles_empty_response():
    agent = make_agent()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"articles": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("data.ingest.news.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_not_called()
    agent.bus.publish.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_news.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ingest.news'`

- [ ] **Step 3: Implement `data/ingest/news.py`**

```python
import httpx
from datetime import datetime
from data.ingest.base import DataIngestAgent

NEWSAPI_URL = "https://newsapi.org/v2/everything"
QUERY = "stock market OR cryptocurrency OR finance OR earnings"


class NewsIngestAgent(DataIngestAgent):
    def __init__(self, *args, api_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key

    async def run_once(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                NEWSAPI_URL,
                params={
                    "q": QUERY,
                    "apiKey": self.api_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                },
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])

        rows = [
            (
                datetime.fromisoformat(art["publishedAt"].replace("Z", "+00:00")),
                art.get("source", {}).get("name", "unknown"),
                art["title"],
                art.get("url", ""),
                None,
            )
            for art in articles
        ]
        if rows:
            await self.db.executemany(
                "INSERT INTO news_items (time, source, headline, url, sentiment_score) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                rows,
            )
        await self.bus.publish("data.news.updated", {"article_count": len(articles)})
        self.logger.info("news_ingested", articles=len(articles))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_news.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add data/ingest/news.py tests/data/ingest/test_news.py
git commit -m "feat: NewsIngestAgent pulling financial headlines from NewsAPI"
```

---

## Task 7: SecIngestAgent

**Files:**
- Create: `data/ingest/sec.py`
- Create: `tests/data/ingest/test_sec.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/ingest/test_sec.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from data.ingest.sec import SecIngestAgent

TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}

SUBMISSIONS_JSON = {
    "filings": {
        "recent": {
            "form": ["10-K", "8-K", "10-Q"],
            "filingDate": ["2024-01-01", "2024-01-15", "2023-10-01"],
            "accessionNumber": ["0000320193-24-000001", "0000320193-24-000002", "0000320193-23-000003"],
            "reportDate": ["2023-09-30", "", "2023-06-30"],
        }
    }
}


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return SecIngestAgent(
        name="sec_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        watchlist=["AAPL"],
        interval_seconds=3600,
    )


def make_mock_client(tickers_json, submissions_json):
    mock_client = AsyncMock()

    async def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = 200
        if "company_tickers" in url:
            resp.json.return_value = tickers_json
        else:
            resp.json.return_value = submissions_json
        return resp

    mock_client.get = mock_get
    return mock_client


@pytest.mark.asyncio
async def test_sec_agent_loads_cik_on_first_run():
    agent = make_agent()
    mock_client = make_mock_client(TICKERS_JSON, SUBMISSIONS_JSON)

    with patch("data.ingest.sec.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    assert agent._ticker_cik.get("AAPL") == "0000320193"


@pytest.mark.asyncio
async def test_sec_agent_stores_filings():
    agent = make_agent()
    mock_client = make_mock_client(TICKERS_JSON, SUBMISSIONS_JSON)

    with patch("data.ingest.sec.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.db.executemany.assert_called_once()
    call_args = agent.db.executemany.call_args
    assert "INSERT INTO sec_filings" in call_args[0][0]
    records = call_args[0][1]
    form_types = {r[2] for r in records}
    assert "10-K" in form_types
    assert "10-Q" in form_types
    assert "8-K" in form_types


@pytest.mark.asyncio
async def test_sec_agent_publishes_update():
    agent = make_agent()
    mock_client = make_mock_client(TICKERS_JSON, SUBMISSIONS_JSON)

    with patch("data.ingest.sec.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.sec.updated"
    assert "AAPL" in call[0][1]["tickers"]
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_sec.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ingest.sec'`

- [ ] **Step 3: Implement `data/ingest/sec.py`**

```python
import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_HEADERS = {"User-Agent": "hedgefund info@hedgefund.local"}
FILING_TYPES = {"10-K", "10-Q", "8-K"}


class SecIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist
        self._ticker_cik: dict[str, str] = {}

    async def _load_ticker_cik(self, client: httpx.AsyncClient):
        resp = await client.get(SEC_TICKERS_URL, headers=SEC_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        self._ticker_cik = {
            v["ticker"]: str(v["cik_str"]).zfill(10)
            for v in data.values()
        }

    async def run_once(self):
        async with httpx.AsyncClient() as client:
            if not self._ticker_cik:
                await self._load_ticker_cik(client)

            rows = []
            for ticker in self.watchlist:
                cik = self._ticker_cik.get(ticker.upper())
                if not cik:
                    continue
                resp = await client.get(
                    SEC_SUBMISSIONS_URL.format(cik=cik),
                    headers=SEC_HEADERS,
                )
                if resp.status_code != 200:
                    continue
                recent = resp.json().get("filings", {}).get("recent", {})
                forms = recent.get("form", [])
                dates = recent.get("filingDate", [])
                accessions = recent.get("accessionNumber", [])
                periods = recent.get("reportDate", [])

                for form, date, accession, period in zip(forms, dates, accessions, periods):
                    if form not in FILING_TYPES:
                        continue
                    url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(cik)}/{accession.replace('-', '')}/{accession}-index.htm"
                    )
                    rows.append((
                        datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                        ticker,
                        form,
                        period,
                        url,
                        None,
                    ))

            if rows:
                await self.db.executemany(
                    "INSERT INTO sec_filings (time, ticker, form_type, period, filing_url, summary) "
                    "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
                    rows,
                )

        await self.bus.publish("data.sec.updated", {"tickers": self.watchlist})
        self.logger.info("sec_ingested", tickers=len(self.watchlist), filings=len(rows))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_sec.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add data/ingest/sec.py tests/data/ingest/test_sec.py
git commit -m "feat: SecIngestAgent pulling 10-K/10-Q/8-K filings from SEC EDGAR"
```

---

## Task 8: SocialIngestAgent

**Files:**
- Create: `data/ingest/social.py`
- Create: `tests/data/ingest/test_social.py`

- [ ] **Step 1: Write failing tests**

Create `tests/data/ingest/test_social.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from data.ingest.social import SocialIngestAgent

FAKE_POSTS = [
    {"id": "abc123", "title": "GME to the moon", "score": 5000, "subreddit": "wallstreetbets", "url": "https://reddit.com/abc", "created_utc": 1704067200.0},
    {"id": "def456", "title": "Bitcoin analysis", "score": 1200, "subreddit": "CryptoCurrency", "url": "https://reddit.com/def", "created_utc": 1704070800.0},
]


def make_agent():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()
    return SocialIngestAgent(
        name="social_ingest",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        client_id="test_id",
        client_secret="test_secret",
        interval_seconds=300,
    )


@pytest.mark.asyncio
async def test_social_agent_publishes_posts():
    agent = make_agent()
    agent._fetch_posts = MagicMock(return_value=FAKE_POSTS)

    await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "data.social.updated"
    assert call[0][1]["post_count"] == 2
    assert call[0][1]["source"] == "reddit"


@pytest.mark.asyncio
async def test_social_agent_publishes_posts_content():
    agent = make_agent()
    agent._fetch_posts = MagicMock(return_value=FAKE_POSTS)

    await agent.run_once()

    call = agent.bus.publish.call_args
    posts = call[0][1]["posts"]
    assert posts[0]["title"] == "GME to the moon"
    assert posts[1]["subreddit"] == "CryptoCurrency"


@pytest.mark.asyncio
async def test_social_agent_handles_empty_feed():
    agent = make_agent()
    agent._fetch_posts = MagicMock(return_value=[])

    await agent.run_once()

    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][1]["post_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/data/ingest/test_social.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ingest.social'`

- [ ] **Step 3: Implement `data/ingest/social.py`**

```python
import asyncio
import praw
from data.ingest.base import DataIngestAgent

SUBREDDITS = "wallstreetbets+investing+stocks+CryptoCurrency+SecurityAnalysis"


class SocialIngestAgent(DataIngestAgent):
    def __init__(self, *args, client_id: str, client_secret: str, user_agent: str = "hedgefund/1.0", **kwargs):
        super().__init__(*args, **kwargs)
        self._reddit_creds = {
            "client_id": client_id,
            "client_secret": client_secret,
            "user_agent": user_agent,
        }

    def _fetch_posts(self) -> list[dict]:
        reddit = praw.Reddit(**self._reddit_creds)
        posts = []
        for post in reddit.subreddit(SUBREDDITS).hot(limit=25):
            posts.append({
                "id": post.id,
                "title": post.title,
                "score": post.score,
                "subreddit": str(post.subreddit),
                "url": post.url,
                "created_utc": post.created_utc,
            })
        return posts

    async def run_once(self):
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(None, self._fetch_posts)
        await self.bus.publish("data.social.updated", {
            "post_count": len(posts),
            "source": "reddit",
            "posts": posts,
        })
        self.logger.info("social_ingested", posts=len(posts))
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/data/ingest/test_social.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add data/ingest/social.py tests/data/ingest/test_social.py
git commit -m "feat: SocialIngestAgent pulling Reddit hot posts from finance subreddits"
```

---

## Task 9: Entry point, requirements, and wiring

**Files:**
- Create: `data/ingest/main.py`
- Modify: `requirements.txt`
- Modify: `scripts/start_all.py`

- [ ] **Step 1: Add new packages to `requirements.txt`**

Replace the contents of `requirements.txt` with:

```
asyncpg==0.29.0
redis==5.0.3
python-dotenv==1.0.1
httpx==0.27.0
pydantic==2.7.1
pydantic-settings==2.2.1
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-mock==3.14.0
pytest-cov==7.1.0
structlog==24.1.0
ollama==0.2.1
yfinance==0.2.38
praw==7.7.1
```

- [ ] **Step 2: Install new packages**

```
.venv\Scripts\pip install yfinance==0.2.38 praw==7.7.1
```

Expected: Successfully installed yfinance and praw

- [ ] **Step 3: Create `data/ingest/main.py`**

```python
#!/usr/bin/env python3
"""
Starts all data ingest agents concurrently in a single process.
Each agent runs its own async loop on its own interval.
"""
import asyncio
import sys
sys.path.insert(0, ".")

from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from data.ingest.stocks import StocksIngestAgent
from data.ingest.crypto import CryptoIngestAgent
from data.ingest.macro import MacroIngestAgent
from data.ingest.news import NewsIngestAgent
from data.ingest.sec import SecIngestAgent
from data.ingest.social import SocialIngestAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(settings)

    await bus.connect()
    await db.connect()

    watchlist = settings.stock_watchlist.split(",")
    crypto_watchlist = settings.crypto_watchlist.split(",")

    agents = [
        StocksIngestAgent(name="stocks_ingest", bus=bus, db=db, router=router, watchlist=watchlist, interval_seconds=60),
        CryptoIngestAgent(name="crypto_ingest", bus=bus, db=db, router=router, watchlist=crypto_watchlist, interval_seconds=30),
        MacroIngestAgent(name="macro_ingest", bus=bus, db=db, router=router, api_key=settings.fred_api_key, interval_seconds=3600),
        NewsIngestAgent(name="news_ingest", bus=bus, db=db, router=router, api_key=settings.news_api_key, interval_seconds=300),
        SecIngestAgent(name="sec_ingest", bus=bus, db=db, router=router, watchlist=watchlist, interval_seconds=3600),
        SocialIngestAgent(
            name="social_ingest", bus=bus, db=db, router=router,
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            interval_seconds=300,
        ),
    ]

    try:
        await asyncio.gather(*[agent.run() for agent in agents])
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Wire into `scripts/start_all.py`**

Replace the `AGENTS` list in `scripts/start_all.py` with:

```python
AGENTS: list[str] = [
    "data/ingest/main.py",
    # Uncomment as agents are built in Phase 4+:
    # "agents/research/main.py",
    # "agents/macro/main.py",
    # "agents/sentiment/main.py",
    # "agents/options/main.py",
    # "agents/portfolio_researcher/main.py",
    # "agents/quant/momentum/main.py",
    # "agents/quant/mean_reversion/main.py",
    # "agents/quant/ml_quant/main.py",
    # "agents/quant/macro_quant/main.py",
    # "agents/quant/supervisor/main.py",
    # "agents/portfolio_mgr/main.py",
    # "agents/risk/main.py",
    # "agents/execution/main.py",
    # "agents/cio/main.py",
    # "agents/ops/main.py",
]
```

- [ ] **Step 5: Run the full test suite**

```
.venv\Scripts\pytest tests/ -v
```

Expected: All tests pass (22 old + 17 new = 39 total)

- [ ] **Step 6: Commit**

```
git add requirements.txt data/ingest/main.py scripts/start_all.py
git commit -m "feat: wire all ingest agents into main entry point and start_all"
```

- [ ] **Step 7: Push to GitHub**

```
git push origin master
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Stocks, crypto, macro, news, SEC, social — all 6 ingest workers covered. On-chain metrics deferred (Glassnode/CryptoQuant free tier limits require account signup — can be Phase 2b).
- [x] **No placeholders:** All steps have complete code.
- [x] **Type consistency:** `store_prices()` signature matches across base.py and all agents. `DataIngestAgent` → `BaseAgent` inheritance chain consistent throughout.
- [x] **DB tables:** macro_data, news_items, sec_filings added in Task 1. Unique constraints defined so ON CONFLICT works.
- [x] **Redis channels:** data.stocks.updated, data.crypto.updated, data.macro.updated, data.news.updated, data.sec.updated, data.social.updated — consistent naming.
