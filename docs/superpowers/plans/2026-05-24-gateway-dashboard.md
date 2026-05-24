# Gateway + Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI gateway (REST + WebSocket) and Next.js dashboard (7 tabs) so the hedge fund has a live Bloomberg-style UI.

**Architecture:** FastAPI gateway reads from TimescaleDB + Redis and exposes REST endpoints + a WebSocket that streams live Redis events to the browser. Next.js dashboard at port 3000 calls the gateway at port 8000 and renders 7 tabs: Overview, Consensus, Terminal, Activity, Quant Lab, Operations, CIO Chat.

**Tech Stack:** FastAPI, uvicorn, asyncpg, redis-py, Next.js 14 (App Router), Tailwind CSS, shadcn/ui, lightweight-charts v4, SWR

---

## File Structure

### Gateway (Python)
```
gateway/
├── __init__.py
├── main.py           # FastAPI app, lifespan, CORS, mounts routers
├── deps.py           # FastAPI dependencies: get_db(), get_bus()
├── ws_manager.py     # WebSocket connection manager + Redis fan-out bridge
└── routers/
    ├── __init__.py
    ├── portfolio.py  # GET /portfolio, GET /positions, GET /trades
    ├── signals.py    # GET /signals, GET /signals/{symbol}
    ├── trades.py     # GET /trades/pending, POST /trades/{id}/approve|deny
    ├── agents.py     # GET /agents/health
    ├── backtests.py  # GET /backtests/algos, GET /backtests/algos/{id}
    └── chat.py       # POST /chat (sends message to CIO via Redis, waits for response)
```

### Tests
```
tests/gateway/
├── conftest.py       # AsyncClient fixture
├── test_portfolio.py
├── test_signals.py
├── test_trades.py
├── test_agents.py
└── test_backtests.py
```

### Dashboard (Next.js)
```
dashboard/
├── package.json
├── next.config.mjs
├── tailwind.config.ts
├── tsconfig.json
├── components.json         # shadcn/ui config
├── app/
│   ├── layout.tsx          # Root layout with sidebar nav + kill switch
│   ├── page.tsx            # Redirect → /overview
│   ├── globals.css
│   ├── overview/page.tsx
│   ├── consensus/page.tsx
│   ├── terminal/page.tsx
│   ├── activity/page.tsx
│   ├── quant/page.tsx
│   ├── ops/page.tsx
│   └── chat/page.tsx
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   └── kill-switch.tsx
│   ├── overview/
│   │   ├── pnl-card.tsx
│   │   ├── positions-table.tsx
│   │   ├── risk-gauge.tsx
│   │   ├── regime-badge.tsx
│   │   └── trade-queue.tsx
│   ├── consensus/
│   │   └── voting-matrix.tsx
│   ├── terminal/
│   │   ├── price-chart.tsx
│   │   └── news-feed.tsx
│   ├── activity/
│   │   └── activity-feed.tsx
│   ├── quant/
│   │   └── algos-table.tsx
│   ├── ops/
│   │   └── agent-board.tsx
│   └── chat/
│       └── cio-chat.tsx
└── lib/
    ├── api.ts              # REST fetch helpers
    └── use-ws.ts           # WebSocket React hook
```

---

## Task 1: Add Gateway Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add fastapi, uvicorn, python-jose to requirements.txt**

Open `requirements.txt` and append:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-jose[cryptography]==3.3.0
websockets==12.0
```

- [ ] **Step 2: Install new deps**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\pip.exe install fastapi==0.111.0 "uvicorn[standard]==0.29.0" "python-jose[cryptography]==3.3.0" websockets==12.0
```

Expected: `Successfully installed fastapi-0.111.0 ...`

- [ ] **Step 3: Add JWT secret to .env**

Append to `C:\Users\jomik\hedge-fund\.env`:
```
# Gateway
GATEWAY_PORT=8000
JWT_SECRET=dev-secret-change-in-production
```

- [ ] **Step 4: Add gateway settings to shared/config.py**

In `shared/config.py`, add to the `Settings` class (before the `@computed_field`):
```python
    gateway_port: int = 8000
    jwt_secret: str = "dev-secret-change-in-production"
```

- [ ] **Step 5: Run existing tests to confirm nothing broke**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/shared/test_config.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add requirements.txt .env shared/config.py
git commit -m "feat(gateway): add fastapi/uvicorn deps and gateway config"
```

---

## Task 2: Gateway Foundation (deps.py + main.py)

**Files:**
- Create: `gateway/__init__.py`
- Create: `gateway/deps.py`
- Create: `gateway/main.py`

- [ ] **Step 1: Create gateway/__init__.py**

```python
# gateway/__init__.py
```

- [ ] **Step 2: Create gateway/deps.py**

```python
# gateway/deps.py
from shared.db import Database
from shared.bus import RedisBus
from shared.config import settings

_db: Database | None = None
_bus: RedisBus | None = None


def get_db() -> Database:
    assert _db is not None, "Database not initialised"
    return _db


def get_bus() -> RedisBus:
    assert _bus is not None, "RedisBus not initialised"
    return _bus


async def startup():
    global _db, _bus
    _db = Database(settings.db_dsn)
    await _db.connect()
    _bus = RedisBus(settings.redis_url)
    await _bus.connect()


async def shutdown():
    if _db:
        await _db.disconnect()
    if _bus:
        await _bus.disconnect()
```

- [ ] **Step 3: Create gateway/main.py**

```python
# gateway/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway import deps
from gateway.routers import portfolio, signals, trades, agents, backtests, chat
from gateway.ws_manager import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await deps.startup()
    yield
    await deps.shutdown()


app = FastAPI(title="Hedge Fund Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Create gateway/routers/__init__.py**

```python
# gateway/routers/__init__.py
```

- [ ] **Step 5: Smoke-test the app starts**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -c "from gateway.main import app; print('ok')"
```

Expected: `ok` (will fail until routers exist — continue to next tasks first)

- [ ] **Step 6: Commit skeleton**

```powershell
git add gateway/
git commit -m "feat(gateway): FastAPI app skeleton with lifespan and CORS"
```

---

## Task 3: Portfolio Router

**Files:**
- Create: `gateway/routers/portfolio.py`
- Create: `tests/gateway/conftest.py`
- Create: `tests/gateway/test_portfolio.py`

- [ ] **Step 1: Create tests/gateway/conftest.py**

```python
# tests/gateway/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
import gateway.deps as deps_module


@pytest.fixture
async def mock_db():
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.execute = AsyncMock()
    return db


@pytest.fixture
async def mock_bus():
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
async def client(mock_db, mock_bus):
    deps_module._db = mock_db
    deps_module._bus = mock_bus
    from gateway.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: Write failing test for GET /portfolio**

```python
# tests/gateway/test_portfolio.py
import pytest
from decimal import Decimal


@pytest.mark.asyncio
async def test_get_portfolio_returns_summary(client, mock_db):
    mock_db.fetchrow.return_value = {
        "cash": 95000.0,
        "total_value": 102000.0,
        "peak_value": 105000.0,
        "open_positions": 2,
        "time": "2026-05-24T10:00:00+00:00",
    }
    resp = await client.get("/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_value"] == 102000.0
    assert data["cash"] == 95000.0
    assert data["open_positions"] == 2


@pytest.mark.asyncio
async def test_get_portfolio_no_state_returns_initial_capital(client, mock_db):
    mock_db.fetchrow.return_value = None
    resp = await client.get("/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_value"] == 100000.0


@pytest.mark.asyncio
async def test_get_positions_returns_list(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "symbol": "AAPL", "direction": "long", "quantity": 10.0,
         "entry_price": 180.0, "status": "open", "asset_class": "stock",
         "entry_time": "2026-05-24T09:00:00+00:00", "entry_thesis": "bullish",
         "exit_price": None, "exit_time": None},
    ]
    resp = await client.get("/portfolio/positions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_get_trades_returns_list(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "symbol": "AAPL", "action": "long", "quantity": 10.0,
         "price": 180.0, "paper": True, "status": "executed",
         "confidence": 80.0, "pm_reasoning": "bullish signal",
         "time": "2026-05-24T09:00:00+00:00", "position_id": None},
    ]
    resp = await client.get("/portfolio/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"
```

- [ ] **Step 3: Run test to verify it fails**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/gateway/test_portfolio.py -v
```

Expected: `ModuleNotFoundError` or router 404 — test collection error is fine at this point.

- [ ] **Step 4: Create gateway/routers/portfolio.py**

```python
# gateway/routers/portfolio.py
from fastapi import APIRouter, Depends
from shared.db import Database
from shared.config import settings
from gateway.deps import get_db

router = APIRouter()


@router.get("")
async def get_portfolio(db: Database = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT cash, total_value, peak_value, open_positions, time "
        "FROM portfolio_state ORDER BY time DESC LIMIT 1"
    )
    if not row:
        return {
            "cash": settings.initial_capital,
            "total_value": settings.initial_capital,
            "peak_value": settings.initial_capital,
            "open_positions": 0,
            "time": None,
        }
    return dict(row)


@router.get("/positions")
async def get_positions(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM positions WHERE status = 'open' ORDER BY entry_time DESC"
    )
    return rows


@router.get("/trades")
async def get_trades(limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM trades ORDER BY time DESC LIMIT $1", limit
    )
    return rows
```

- [ ] **Step 5: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_portfolio.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```powershell
git add gateway/routers/portfolio.py tests/gateway/
git commit -m "feat(gateway): portfolio router with state/positions/trades endpoints"
```

---

## Task 4: Signals + Agents + Backtests Routers

**Files:**
- Create: `gateway/routers/signals.py`
- Create: `gateway/routers/agents.py`
- Create: `gateway/routers/backtests.py`
- Create: `tests/gateway/test_signals.py`
- Create: `tests/gateway/test_agents.py`
- Create: `tests/gateway/test_backtests.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gateway/test_signals.py
import pytest


@pytest.mark.asyncio
async def test_get_signals_returns_recent(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "aggregator", "symbol": "AAPL", "signal_type": "bullish",
         "confidence": 72.0, "reasoning": "strong trend", "time": "2026-05-24T10:00:00+00:00",
         "metadata": None},
    ]
    resp = await client.get("/signals")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_signals_for_symbol(client, mock_db):
    mock_db.fetch.return_value = []
    resp = await client.get("/signals/AAPL")
    assert resp.status_code == 200
    assert resp.json() == []
```

```python
# tests/gateway/test_agents.py
import pytest


@pytest.mark.asyncio
async def test_get_agent_health(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "technical", "status": "healthy",
         "time": "2026-05-24T10:00:00+00:00", "message": None, "metadata": None},
    ]
    resp = await client.get("/agents/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["agent"] == "technical"
```

```python
# tests/gateway/test_backtests.py
import pytest


@pytest.mark.asyncio
async def test_get_algos_returns_list(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "name": "MomentumV1", "quant_agent": "momentum",
         "strategy_type": "momentum", "status": "live",
         "sharpe_ratio": 1.4, "max_drawdown": -0.08, "win_rate": 0.58,
         "trade_count": 42, "created_at": "2026-05-20T00:00:00+00:00",
         "retired_at": None, "retirement_reason": None, "config": None},
    ]
    resp = await client.get("/backtests/algos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "MomentumV1"
```

- [ ] **Step 2: Run to verify they fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_signals.py tests/gateway/test_agents.py tests/gateway/test_backtests.py -v
```

Expected: errors (routers missing)

- [ ] **Step 3: Create gateway/routers/signals.py**

```python
# gateway/routers/signals.py
from fastapi import APIRouter, Depends
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("")
async def get_signals(limit: int = 100, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM signals ORDER BY time DESC LIMIT $1", limit
    )
    return rows


@router.get("/{symbol}")
async def get_signals_for_symbol(symbol: str, limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM signals WHERE symbol = $1 ORDER BY time DESC LIMIT $2",
        symbol.upper(), limit,
    )
    return rows
```

- [ ] **Step 4: Create gateway/routers/agents.py**

```python
# gateway/routers/agents.py
from fastapi import APIRouter, Depends
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/health")
async def get_agent_health(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (agent) agent, status, time, message, metadata
        FROM agent_health
        ORDER BY agent, time DESC
        """
    )
    return rows
```

- [ ] **Step 5: Create gateway/routers/backtests.py**

```python
# gateway/routers/backtests.py
from fastapi import APIRouter, Depends, HTTPException
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/algos")
async def get_algos(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM quant_algos ORDER BY created_at DESC"
    )
    return rows


@router.get("/algos/{algo_id}")
async def get_algo(algo_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT * FROM quant_algos WHERE id = $1", algo_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Algo not found")
    return row
```

- [ ] **Step 6: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_signals.py tests/gateway/test_agents.py tests/gateway/test_backtests.py -v
```

Expected: `5 passed`

- [ ] **Step 7: Commit**

```powershell
git add gateway/routers/signals.py gateway/routers/agents.py gateway/routers/backtests.py tests/gateway/
git commit -m "feat(gateway): signals, agents health, and backtests routers"
```

---

## Task 5: Trade Approval Router

**Files:**
- Create: `gateway/routers/trades.py`
- Create: `tests/gateway/test_trades.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gateway/test_trades.py
import pytest


@pytest.mark.asyncio
async def test_get_pending_trades(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 5, "symbol": "TSLA", "action": "long", "quantity": 5.0,
         "price": 200.0, "paper": True, "status": "pending",
         "confidence": 55.0, "pm_reasoning": "moderate signal",
         "time": "2026-05-24T10:00:00+00:00", "position_id": None},
    ]
    resp = await client.get("/trades/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_trade_updates_status(client, mock_db):
    mock_db.fetchrow.return_value = {"id": 5, "status": "pending"}
    resp = await client.post("/trades/5/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_deny_trade_updates_status(client, mock_db):
    mock_db.fetchrow.return_value = {"id": 5, "status": "pending"}
    resp = await client.post("/trades/5/deny")
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


@pytest.mark.asyncio
async def test_approve_nonexistent_trade_returns_404(client, mock_db):
    mock_db.fetchrow.return_value = None
    resp = await client.post("/trades/999/approve")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_trades.py -v
```

Expected: 404 errors (router missing)

- [ ] **Step 3: Create gateway/routers/trades.py**

```python
# gateway/routers/trades.py
from fastapi import APIRouter, Depends, HTTPException
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/pending")
async def get_pending_trades(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM trades WHERE status = 'pending' ORDER BY time DESC"
    )
    return rows


@router.post("/{trade_id}/approve")
async def approve_trade(trade_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT id, status FROM trades WHERE id = $1", trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.execute(
        "UPDATE trades SET status = 'approved' WHERE id = $1", trade_id
    )
    return {"id": trade_id, "status": "approved"}


@router.post("/{trade_id}/deny")
async def deny_trade(trade_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT id, status FROM trades WHERE id = $1", trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.execute(
        "UPDATE trades SET status = 'denied' WHERE id = $1", trade_id
    )
    return {"id": trade_id, "status": "denied"}
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_trades.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```powershell
git add gateway/routers/trades.py tests/gateway/test_trades.py
git commit -m "feat(gateway): trade approval router (pending/approve/deny)"
```

---

## Task 6: CIO Chat Router

**Files:**
- Create: `gateway/routers/chat.py`

- [ ] **Step 1: Create gateway/routers/chat.py**

```python
# gateway/routers/chat.py
import asyncio
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from shared.bus import RedisBus
from gateway.deps import get_bus

router = APIRouter()


class ChatMessage(BaseModel):
    message: str


@router.post("")
async def chat(body: ChatMessage, bus: RedisBus = Depends(get_bus)):
    """Send message to CIO agent and wait up to 30s for response."""
    request_id = str(uuid.uuid4())
    await bus.publish("cio.chat.request", {
        "request_id": request_id,
        "message": body.message,
    })
    # Poll Redis for response (CIO agent writes to cio.chat.response:<request_id>)
    for _ in range(60):
        await asyncio.sleep(0.5)
        response = await bus.get(f"cio.chat.response:{request_id}")
        if response:
            return {"reply": response.get("reply", ""), "request_id": request_id}
    return {"reply": "CIO is not responding. Check agent health.", "request_id": request_id}
```

- [ ] **Step 2: Commit**

```powershell
git add gateway/routers/chat.py
git commit -m "feat(gateway): CIO chat router (pub/sub via Redis)"
```

---

## Task 7: WebSocket Manager

**Files:**
- Create: `gateway/ws_manager.py`

- [ ] **Step 1: Create gateway/ws_manager.py**

```python
# gateway/ws_manager.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from gateway.deps import get_bus

router = APIRouter()

# Redis channels to forward to all connected WebSocket clients
SUBSCRIBED_CHANNELS = [
    "ops.heartbeat",
    "signals.technical",
    "signals.sentiment",
    "signals.macro",
    "signals.research",
    "signals.aggregator",
    "signals.quant_supervisor",
    "signals.portfolio_mgr",
    "data.prices",
    "data.news",
]

_clients: list[WebSocket] = []


async def _broadcast(message: dict):
    disconnected = []
    for ws in _clients:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _clients.remove(ws)


async def _redis_bridge():
    """Subscribe to all channels and broadcast to WebSocket clients."""
    bus = get_bus()
    import redis.asyncio as aioredis
    from shared.config import settings
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(*SUBSCRIBED_CHANNELS)
    async for raw in pubsub.listen():
        if raw["type"] == "message":
            data = raw["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            try:
                payload = json.loads(data)
            except Exception:
                payload = {"raw": data}
            await _broadcast({"channel": raw["channel"], "data": payload})


_bridge_task: asyncio.Task | None = None


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _bridge_task
    await ws.accept()
    _clients.append(ws)

    # Start bridge task once
    if _bridge_task is None or _bridge_task.done():
        _bridge_task = asyncio.create_task(_redis_bridge())

    try:
        while True:
            # Keep connection alive, handle ping/pong
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, Exception):
        if ws in _clients:
            _clients.remove(ws)
```

- [ ] **Step 2: Verify gateway fully assembles**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -c "from gateway.main import app; print('Gateway OK, routes:', [r.path for r in app.routes])"
```

Expected: prints list including `/portfolio`, `/signals`, `/trades`, `/ws`, etc.

- [ ] **Step 3: Run full gateway test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/ -v
```

Expected: all PASS

- [ ] **Step 4: Start gateway and verify health endpoint**

```powershell
Start-Process -NoNewWindow .venv\Scripts\uvicorn.exe -ArgumentList "gateway.main:app","--port","8000","--reload" -RedirectStandardOutput gateway.log
Start-Sleep -Seconds 3
Invoke-RestMethod http://localhost:8000/health
```

Expected: `{"status":"ok"}`

Stop it after verifying:
```powershell
Stop-Process -Name uvicorn -Force -ErrorAction SilentlyContinue
```

- [ ] **Step 5: Commit**

```powershell
git add gateway/ws_manager.py
git commit -m "feat(gateway): WebSocket endpoint with Redis fan-out bridge"
```

---

## Task 8: Next.js Project Scaffold

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/next.config.mjs`
- Create: `dashboard/tailwind.config.ts`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/app/globals.css`
- Create: `dashboard/components.json`

- [ ] **Step 1: Verify node is available**

```powershell
node --version; npm --version
```

Expected: node v18+ and npm v9+. If not installed: download from https://nodejs.org/

- [ ] **Step 2: Create dashboard/package.json**

```json
{
  "name": "hedge-fund-dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --port 3000",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18",
    "react-dom": "^18",
    "swr": "^2.2.5",
    "lightweight-charts": "^4.1.3",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.3.0",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-badge": "^1.0.4",
    "lucide-react": "^0.378.0"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "tailwindcss": "^3.4.1"
  }
}
```

- [ ] **Step 3: Create dashboard/next.config.mjs**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ]
  },
}

export default nextConfig
```

- [ ] **Step 4: Create dashboard/tsconfig.json**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 5: Create dashboard/tailwind.config.ts**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        surface: "#13131a",
        border: "#1e1e2e",
        accent: "#00d4aa",
        danger: "#ff4757",
        warning: "#ffa502",
        muted: "#6b7280",
      },
    },
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 6: Create dashboard/postcss.config.mjs**

```js
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
export default config;
```

- [ ] **Step 7: Create dashboard/app/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #0a0a0f;
  --surface: #13131a;
}

body {
  background: var(--background);
  color: #e2e8f0;
  font-family: 'Inter', system-ui, sans-serif;
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: #13131a;
}
::-webkit-scrollbar-thumb {
  background: #2d2d3f;
  border-radius: 3px;
}
```

- [ ] **Step 8: Install dependencies**

```powershell
Set-Location C:\Users\jomik\hedge-fund\dashboard
npm install
```

Expected: `added N packages` with no errors.

- [ ] **Step 9: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/
git commit -m "feat(dashboard): Next.js 14 project scaffold with Tailwind"
```

---

## Task 9: API Client Library + WebSocket Hook

**Files:**
- Create: `dashboard/lib/api.ts`
- Create: `dashboard/lib/use-ws.ts`

- [ ] **Step 1: Create dashboard/lib/api.ts**

```ts
// dashboard/lib/api.ts
const BASE = "/api";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  portfolio: () => apiFetch<Portfolio>("/portfolio"),
  positions: () => apiFetch<Position[]>("/portfolio/positions"),
  trades: (limit = 50) => apiFetch<Trade[]>(`/portfolio/trades?limit=${limit}`),
  pendingTrades: () => apiFetch<Trade[]>("/trades/pending"),
  approveTrade: (id: number) => apiFetch<{ id: number; status: string }>(`/trades/${id}/approve`, { method: "POST" }),
  denyTrade: (id: number) => apiFetch<{ id: number; status: string }>(`/trades/${id}/deny`, { method: "POST" }),
  signals: (limit = 100) => apiFetch<Signal[]>(`/signals?limit=${limit}`),
  signalsForSymbol: (symbol: string) => apiFetch<Signal[]>(`/signals/${symbol}`),
  agentHealth: () => apiFetch<AgentHealth[]>("/agents/health"),
  algos: () => apiFetch<Algo[]>("/backtests/algos"),
  chat: (message: string) => apiFetch<{ reply: string }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  }),
};

// Types
export interface Portfolio {
  cash: number;
  total_value: number;
  peak_value: number;
  open_positions: number;
  time: string | null;
}

export interface Position {
  id: number;
  symbol: string;
  asset_class: string;
  direction: string;
  quantity: number;
  entry_price: number;
  entry_time: string;
  entry_thesis: string | null;
  status: string;
  exit_price: number | null;
  exit_time: string | null;
}

export interface Trade {
  id: number;
  symbol: string;
  action: string;
  quantity: number;
  price: number;
  paper: boolean;
  status: string;
  confidence: number;
  pm_reasoning: string | null;
  time: string;
  position_id: number | null;
}

export interface Signal {
  agent: string;
  symbol: string | null;
  signal_type: string;
  confidence: number;
  reasoning: string | null;
  time: string;
}

export interface AgentHealth {
  agent: string;
  status: string;
  time: string;
}

export interface Algo {
  id: number;
  name: string;
  quant_agent: string;
  strategy_type: string;
  status: string;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  trade_count: number | null;
  created_at: string;
}
```

- [ ] **Step 2: Create dashboard/lib/use-ws.ts**

```ts
// dashboard/lib/use-ws.ts
"use client";
import { useEffect, useRef, useState } from "react";

export interface WsMessage {
  channel: string;
  data: Record<string, unknown>;
}

export function useWebSocket() {
  const [messages, setMessages] = useState<WsMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage;
        if (msg.channel) {
          setMessages((prev) => [msg, ...prev].slice(0, 200));
        }
      } catch {
        // ignore ping frames
      }
    };

    return () => ws.close();
  }, []);

  return { messages, connected };
}

export function useChannelMessages(channel: string) {
  const { messages, connected } = useWebSocket();
  return {
    messages: messages.filter((m) => m.channel === channel),
    connected,
  };
}
```

- [ ] **Step 3: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/lib/
git commit -m "feat(dashboard): API client and WebSocket hook"
```

---

## Task 10: Root Layout + Sidebar + Kill Switch

**Files:**
- Create: `dashboard/app/layout.tsx`
- Create: `dashboard/app/page.tsx`
- Create: `dashboard/components/layout/sidebar.tsx`
- Create: `dashboard/components/layout/kill-switch.tsx`

- [ ] **Step 1: Create dashboard/components/layout/sidebar.tsx**

```tsx
// dashboard/components/layout/sidebar.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Cpu, BarChart2, Activity,
  FlaskConical, Server, MessageSquare
} from "lucide-react";

const NAV = [
  { href: "/overview",   label: "Overview",   icon: LayoutDashboard },
  { href: "/consensus",  label: "Consensus",  icon: Cpu },
  { href: "/terminal",   label: "Terminal",   icon: BarChart2 },
  { href: "/activity",   label: "AI Activity",icon: Activity },
  { href: "/quant",      label: "Quant Lab",  icon: FlaskConical },
  { href: "/ops",        label: "Operations", icon: Server },
  { href: "/chat",       label: "CIO Chat",   icon: MessageSquare },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 min-h-screen bg-surface border-r border-border flex flex-col">
      <div className="px-4 py-5 border-b border-border">
        <span className="text-accent font-bold text-lg tracking-tight">⬡ HedgeFund</span>
        <p className="text-muted text-xs mt-0.5">AI Trading System</p>
      </div>
      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === href
                ? "bg-accent/10 text-accent font-medium"
                : "text-muted hover:text-white hover:bg-white/5"
            }`}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Create dashboard/components/layout/kill-switch.tsx**

```tsx
// dashboard/components/layout/kill-switch.tsx
"use client";
import { useState } from "react";

export function KillSwitch() {
  const [active, setActive] = useState(false);

  async function toggle() {
    const action = active ? "resume" : "halt";
    try {
      await fetch(`/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: `KILL_SWITCH_${action.toUpperCase()}` }),
      });
      setActive(!active);
    } catch {
      alert("Failed to reach gateway");
    }
  }

  return (
    <button
      onClick={toggle}
      className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wide border transition-all ${
        active
          ? "bg-danger border-danger text-white animate-pulse"
          : "bg-transparent border-danger text-danger hover:bg-danger hover:text-white"
      }`}
    >
      {active ? "● TRADING HALTED" : "KILL SWITCH"}
    </button>
  );
}
```

- [ ] **Step 3: Create dashboard/app/layout.tsx**

```tsx
// dashboard/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { KillSwitch } from "@/components/layout/kill-switch";

export const metadata: Metadata = {
  title: "AI Hedge Fund",
  description: "Bloomberg-style AI trading dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen bg-background text-slate-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <header className="h-12 border-b border-border bg-surface flex items-center justify-between px-6">
            <span className="text-sm text-muted">Paper Trading Mode</span>
            <KillSwitch />
          </header>
          <main className="flex-1 p-6 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Create dashboard/app/page.tsx**

```tsx
// dashboard/app/page.tsx
import { redirect } from "next/navigation";
export default function Home() {
  redirect("/overview");
}
```

- [ ] **Step 5: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/ dashboard/components/layout/
git commit -m "feat(dashboard): root layout, sidebar nav, kill switch"
```

---

## Task 11: Overview Tab

**Files:**
- Create: `dashboard/components/overview/pnl-card.tsx`
- Create: `dashboard/components/overview/positions-table.tsx`
- Create: `dashboard/components/overview/risk-gauge.tsx`
- Create: `dashboard/components/overview/regime-badge.tsx`
- Create: `dashboard/components/overview/trade-queue.tsx`
- Create: `dashboard/app/overview/page.tsx`

- [ ] **Step 1: Create dashboard/components/overview/pnl-card.tsx**

```tsx
// dashboard/components/overview/pnl-card.tsx
"use client";
import useSWR from "swr";
import { api, type Portfolio } from "@/lib/api";

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

export function PnlCard() {
  const { data, isLoading } = useSWR<Portfolio>("portfolio", api.portfolio, { refreshInterval: 10000 });

  if (isLoading || !data) return <div className="h-32 bg-surface animate-pulse rounded-xl" />;

  const pnl = data.total_value - 100000;
  const pnlPct = (pnl / 100000) * 100;
  const isPos = pnl >= 0;

  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
      <p className="text-muted text-xs uppercase tracking-widest">Portfolio Value</p>
      <p className="text-3xl font-bold">{fmt(data.total_value)}</p>
      <p className={`text-sm font-medium ${isPos ? "text-accent" : "text-danger"}`}>
        {isPos ? "▲" : "▼"} {fmt(Math.abs(pnl))} ({pnlPct.toFixed(2)}%) all time
      </p>
      <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border text-center">
        <div>
          <p className="text-xs text-muted">Cash</p>
          <p className="font-medium text-sm">{fmt(data.cash)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Peak</p>
          <p className="font-medium text-sm">{fmt(data.peak_value)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Positions</p>
          <p className="font-medium text-sm">{data.open_positions}</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/components/overview/positions-table.tsx**

```tsx
// dashboard/components/overview/positions-table.tsx
"use client";
import useSWR from "swr";
import { api, type Position } from "@/lib/api";

export function PositionsTable() {
  const { data = [], isLoading } = useSWR<Position[]>("positions", api.positions, { refreshInterval: 15000 });

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest">Open Positions</h2>
      {isLoading ? (
        <div className="h-20 animate-pulse bg-border rounded" />
      ) : data.length === 0 ? (
        <p className="text-muted text-sm">No open positions</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2">Symbol</th>
              <th className="text-left py-2">Direction</th>
              <th className="text-right py-2">Qty</th>
              <th className="text-right py-2">Entry</th>
              <th className="text-left py-2 pl-4">Thesis</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 font-mono font-medium">{p.symbol}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${p.direction === "long" ? "bg-accent/10 text-accent" : "bg-danger/10 text-danger"}`}>
                    {p.direction.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 text-right font-mono">{p.quantity.toFixed(4)}</td>
                <td className="py-2 text-right font-mono">${p.entry_price.toFixed(2)}</td>
                <td className="py-2 pl-4 text-muted text-xs truncate max-w-xs">{p.entry_thesis ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create dashboard/components/overview/regime-badge.tsx**

```tsx
// dashboard/components/overview/regime-badge.tsx
"use client";
import useSWR from "swr";
import { api, type Signal } from "@/lib/api";

const REGIME_COLORS: Record<string, string> = {
  "expansion": "text-accent bg-accent/10",
  "contraction": "text-danger bg-danger/10",
  "stagflation": "text-warning bg-warning/10",
  "hiking_cycle": "text-orange-400 bg-orange-400/10",
  "cutting_cycle": "text-blue-400 bg-blue-400/10",
};

export function RegimeBadge() {
  const { data = [] } = useSWR<Signal[]>(
    "signals-macro",
    () => api.signalsForSymbol("MACRO"),
    { refreshInterval: 60000 }
  );

  const latest = data.find((s) => s.agent === "macro");
  const regime = latest?.signal_type ?? "unknown";
  const colorClass = REGIME_COLORS[regime] ?? "text-muted bg-muted/10";

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <p className="text-muted text-xs uppercase tracking-widest mb-2">Market Regime</p>
      <span className={`px-3 py-1.5 rounded-lg text-sm font-semibold uppercase tracking-wide ${colorClass}`}>
        {regime.replace(/_/g, " ")}
      </span>
      {latest && (
        <p className="text-xs text-muted mt-2">{latest.reasoning?.slice(0, 120)}…</p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create dashboard/components/overview/trade-queue.tsx**

```tsx
// dashboard/components/overview/trade-queue.tsx
"use client";
import useSWR from "swr";
import { api, type Trade } from "@/lib/api";

export function TradeQueue() {
  const { data = [], mutate, isLoading } = useSWR<Trade[]>("pending-trades", api.pendingTrades, { refreshInterval: 5000 });

  async function approve(id: number) {
    await api.approveTrade(id);
    mutate();
  }
  async function deny(id: number) {
    await api.denyTrade(id);
    mutate();
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest">
        Trade Approval Queue
        {data.length > 0 && (
          <span className="ml-2 bg-warning/20 text-warning text-xs px-2 py-0.5 rounded-full">{data.length}</span>
        )}
      </h2>
      {isLoading ? (
        <div className="h-16 animate-pulse bg-border rounded" />
      ) : data.length === 0 ? (
        <p className="text-muted text-sm">No pending trades</p>
      ) : (
        <div className="space-y-3">
          {data.map((t) => (
            <div key={t.id} className="border border-border rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold">{t.symbol}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${t.action === "long" ? "text-accent bg-accent/10" : "text-danger bg-danger/10"}`}>
                    {t.action.toUpperCase()}
                  </span>
                  <span className="text-muted text-xs">{t.quantity.toFixed(4)} @ ${t.price.toFixed(2)}</span>
                </div>
                <span className="text-xs text-warning">{t.confidence.toFixed(0)}% confidence</span>
              </div>
              <p className="text-xs text-muted">{t.pm_reasoning}</p>
              <div className="flex gap-2">
                <button onClick={() => approve(t.id)}
                  className="flex-1 py-1.5 rounded bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors">
                  ✓ Approve
                </button>
                <button onClick={() => deny(t.id)}
                  className="flex-1 py-1.5 rounded bg-danger/10 text-danger text-xs font-medium hover:bg-danger/20 transition-colors">
                  ✗ Deny
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create dashboard/app/overview/page.tsx**

```tsx
// dashboard/app/overview/page.tsx
import { PnlCard } from "@/components/overview/pnl-card";
import { PositionsTable } from "@/components/overview/positions-table";
import { RegimeBadge } from "@/components/overview/regime-badge";
import { TradeQueue } from "@/components/overview/trade-queue";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Overview</h1>
      <div className="grid grid-cols-3 gap-4">
        <PnlCard />
        <RegimeBadge />
        <TradeQueue />
      </div>
      <PositionsTable />
    </div>
  );
}
```

- [ ] **Step 6: Start dashboard and verify overview renders**

```powershell
Set-Location C:\Users\jomik\hedge-fund\dashboard
Start-Process -NoNewWindow npm -ArgumentList "run","dev"
Start-Sleep -Seconds 5
Start-Process "http://localhost:3000/overview"
```

Expected: Browser opens showing dark dashboard with Overview tab.

- [ ] **Step 7: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/overview/ dashboard/components/overview/
git commit -m "feat(dashboard): Overview tab with P&L, positions, regime, trade queue"
```

---

## Task 12: Consensus Tab

**Files:**
- Create: `dashboard/components/consensus/voting-matrix.tsx`
- Create: `dashboard/app/consensus/page.tsx`

- [ ] **Step 1: Create dashboard/components/consensus/voting-matrix.tsx**

```tsx
// dashboard/components/consensus/voting-matrix.tsx
"use client";
import useSWR from "swr";
import { api, type Signal } from "@/lib/api";

const AGENTS = ["technical", "sentiment", "macro", "research", "aggregator"];

function directionColor(s: string) {
  if (s.includes("bullish")) return "bg-accent/20 text-accent";
  if (s.includes("bearish")) return "bg-danger/20 text-danger";
  return "bg-muted/20 text-muted";
}

export function VotingMatrix() {
  const { data: signals = [], isLoading } = useSWR<Signal[]>(
    "signals-all",
    () => api.signals(200),
    { refreshInterval: 20000 }
  );

  // Latest signal per (agent, symbol)
  const matrix: Record<string, Record<string, Signal>> = {};
  for (const sig of signals) {
    if (!sig.symbol) continue;
    if (!matrix[sig.symbol]) matrix[sig.symbol] = {};
    if (!matrix[sig.symbol][sig.agent]) matrix[sig.symbol][sig.agent] = sig;
  }

  const symbols = Object.keys(matrix);

  return (
    <div className="bg-surface border border-border rounded-xl p-5 overflow-auto">
      <h2 className="text-sm font-semibold mb-4 text-muted uppercase tracking-widest">AI Consensus Matrix</h2>
      {isLoading ? (
        <div className="h-40 animate-pulse bg-border rounded" />
      ) : symbols.length === 0 ? (
        <p className="text-muted text-sm">No signals yet — waiting for agents</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2 pr-4">Symbol</th>
              {AGENTS.map((a) => (
                <th key={a} className="text-center py-2 px-3 capitalize">{a}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((sym) => (
              <tr key={sym} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 pr-4 font-mono font-bold">{sym}</td>
                {AGENTS.map((agent) => {
                  const sig = matrix[sym]?.[agent];
                  return (
                    <td key={agent} className="py-2 px-3 text-center">
                      {sig ? (
                        <span
                          title={sig.reasoning ?? ""}
                          className={`px-2 py-0.5 rounded text-xs cursor-help ${directionColor(sig.signal_type)}`}
                        >
                          {sig.signal_type.replace("_signal", "").toUpperCase()}
                          <br />
                          <span className="opacity-60">{sig.confidence.toFixed(0)}%</span>
                        </span>
                      ) : (
                        <span className="text-muted text-xs">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/app/consensus/page.tsx**

```tsx
// dashboard/app/consensus/page.tsx
import { VotingMatrix } from "@/components/consensus/voting-matrix";

export default function ConsensusPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">AI Consensus View</h1>
      <VotingMatrix />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/consensus/ dashboard/components/consensus/
git commit -m "feat(dashboard): Consensus tab with agent voting matrix"
```

---

## Task 13: Market Terminal Tab

**Files:**
- Create: `dashboard/components/terminal/price-chart.tsx`
- Create: `dashboard/components/terminal/news-feed.tsx`
- Create: `dashboard/app/terminal/page.tsx`

- [ ] **Step 1: Create dashboard/components/terminal/price-chart.tsx**

```tsx
// dashboard/components/terminal/price-chart.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type ISeriesApi, CandlestickSeries } from "lightweight-charts";

const WATCHLIST = ["AAPL", "MSFT", "NVDA", "BTCUSDT", "ETHUSDT", "SPY"];

export function PriceChart() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [selected, setSelected] = useState("AAPL");

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = createChart(chartRef.current, {
      layout: { background: { color: "#13131a" }, textColor: "#6b7280" },
      grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
      width: chartRef.current.clientWidth,
      height: 400,
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#00d4aa",
      downColor: "#ff4757",
      borderVisible: false,
      wickUpColor: "#00d4aa",
      wickDownColor: "#ff4757",
    });
    chartInstance.current = chart;
    seriesRef.current = series;

    const resize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    // Fetch OHLCV from gateway
    fetch(`/api/signals/${selected}`)
      .then((r) => r.json())
      .then(() => {
        // Seed with placeholder data until prices flow from ingest layer
        const now = Math.floor(Date.now() / 1000);
        const candles = Array.from({ length: 60 }, (_, i) => {
          const open = 150 + Math.random() * 20;
          return {
            time: (now - (59 - i) * 3600) as number,
            open,
            high: open + Math.random() * 5,
            low: open - Math.random() * 5,
            close: open + (Math.random() - 0.5) * 8,
          };
        });
        seriesRef.current?.setData(candles);
      })
      .catch(console.error);
  }, [selected]);

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Market Chart</h2>
        <div className="flex gap-1 ml-auto">
          {WATCHLIST.map((sym) => (
            <button
              key={sym}
              onClick={() => setSelected(sym)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                selected === sym ? "bg-accent text-black font-bold" : "bg-border text-muted hover:text-white"
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>
      <div ref={chartRef} />
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/components/terminal/news-feed.tsx**

```tsx
// dashboard/components/terminal/news-feed.tsx
"use client";
import { useEffect, useState } from "react";
import { useWebSocket } from "@/lib/use-ws";

interface NewsItem {
  headline: string;
  source: string;
  time: string;
  sentiment_score: number | null;
}

export function NewsFeed() {
  const { messages } = useWebSocket();
  const [news, setNews] = useState<NewsItem[]>([]);

  // Seed from DB on mount
  useEffect(() => {
    fetch("/api/signals?limit=20")
      .then((r) => r.json())
      .then((sigs) => {
        const newsSignals = sigs.filter((s: { agent: string }) => s.agent === "news_ingest");
        setNews(newsSignals.map((s: { reasoning: string; agent: string; time: string; confidence: number }) => ({
          headline: s.reasoning ?? "No headline",
          source: s.agent,
          time: s.time,
          sentiment_score: s.confidence,
        })));
      })
      .catch(console.error);
  }, []);

  // Live updates from WebSocket
  useEffect(() => {
    const newsMsg = messages.find((m) => m.channel === "data.news");
    if (newsMsg?.data) {
      setNews((prev) => [newsMsg.data as unknown as NewsItem, ...prev].slice(0, 50));
    }
  }, [messages]);

  return (
    <div className="bg-surface border border-border rounded-xl p-5 h-[400px] overflow-y-auto">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest sticky top-0 bg-surface pb-2">Live News</h2>
      {news.length === 0 ? (
        <p className="text-muted text-sm">Waiting for news feed…</p>
      ) : (
        <div className="space-y-3">
          {news.map((item, i) => (
            <div key={i} className="border-b border-border/50 pb-3">
              <p className="text-sm leading-snug">{item.headline}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-muted">{item.source}</span>
                {item.sentiment_score !== null && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${item.sentiment_score > 0.5 ? "text-accent bg-accent/10" : item.sentiment_score < -0.5 ? "text-danger bg-danger/10" : "text-muted bg-muted/10"}`}>
                    {item.sentiment_score > 0 ? "+" : ""}{(item.sentiment_score * 100).toFixed(0)}
                  </span>
                )}
                <span className="text-xs text-muted ml-auto">{new Date(item.time).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create dashboard/app/terminal/page.tsx**

```tsx
// dashboard/app/terminal/page.tsx
import { PriceChart } from "@/components/terminal/price-chart";
import { NewsFeed } from "@/components/terminal/news-feed";

export default function TerminalPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Market Terminal</h1>
      <PriceChart />
      <NewsFeed />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/terminal/ dashboard/components/terminal/
git commit -m "feat(dashboard): Terminal tab with TradingView chart and news feed"
```

---

## Task 14: AI Activity Tab

**Files:**
- Create: `dashboard/components/activity/activity-feed.tsx`
- Create: `dashboard/app/activity/page.tsx`

- [ ] **Step 1: Create dashboard/components/activity/activity-feed.tsx**

```tsx
// dashboard/components/activity/activity-feed.tsx
"use client";
import { useWebSocket, type WsMessage } from "@/lib/use-ws";

function channelLabel(channel: string) {
  return channel.replace("signals.", "").replace("ops.", "").replace("data.", "");
}

function channelColor(channel: string) {
  if (channel.startsWith("signals.aggregator")) return "text-accent";
  if (channel.startsWith("signals.portfolio")) return "text-purple-400";
  if (channel.startsWith("signals.risk") || channel.includes("risk")) return "text-danger";
  if (channel.startsWith("ops")) return "text-yellow-400";
  return "text-slate-400";
}

export function ActivityFeed() {
  const { messages, connected } = useWebSocket();

  return (
    <div className="bg-surface border border-border rounded-xl p-5 h-[600px] overflow-y-auto">
      <div className="flex items-center justify-between mb-3 sticky top-0 bg-surface pb-2">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Live Agent Activity</h2>
        <span className={`text-xs px-2 py-0.5 rounded-full ${connected ? "text-accent bg-accent/10" : "text-danger bg-danger/10"}`}>
          {connected ? "● LIVE" : "● DISCONNECTED"}
        </span>
      </div>
      {messages.length === 0 ? (
        <p className="text-muted text-sm">Waiting for agent messages… start agents first.</p>
      ) : (
        <div className="space-y-2 font-mono text-xs">
          {messages.map((msg, i) => (
            <div key={i} className="flex gap-3 items-start border-b border-border/30 pb-1">
              <span className="text-muted shrink-0">
                {new Date().toLocaleTimeString()}
              </span>
              <span className={`shrink-0 w-28 ${channelColor(msg.channel)}`}>
                [{channelLabel(msg.channel)}]
              </span>
              <span className="text-slate-300 break-all">
                {msg.data.symbol ? `${msg.data.symbol}: ` : ""}
                {(msg.data.signal_type as string) ?? (msg.data.status as string) ?? JSON.stringify(msg.data).slice(0, 120)}
                {msg.data.confidence ? ` (${Number(msg.data.confidence).toFixed(0)}%)` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/app/activity/page.tsx**

```tsx
// dashboard/app/activity/page.tsx
import { ActivityFeed } from "@/components/activity/activity-feed";

export default function ActivityPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">AI Activity</h1>
      <ActivityFeed />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/activity/ dashboard/components/activity/
git commit -m "feat(dashboard): AI Activity tab with live WebSocket agent feed"
```

---

## Task 15: Quant Lab Tab

**Files:**
- Create: `dashboard/components/quant/algos-table.tsx`
- Create: `dashboard/app/quant/page.tsx`

- [ ] **Step 1: Create dashboard/components/quant/algos-table.tsx**

```tsx
// dashboard/components/quant/algos-table.tsx
"use client";
import useSWR from "swr";
import { api, type Algo } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  live:    "text-accent bg-accent/10",
  testing: "text-warning bg-warning/10",
  approved:"text-blue-400 bg-blue-400/10",
  retired: "text-muted bg-muted/10",
};

export function AlgosTable() {
  const { data: algos = [], isLoading } = useSWR<Algo[]>("algos", api.algos, { refreshInterval: 30000 });

  return (
    <div className="bg-surface border border-border rounded-xl p-5 overflow-auto">
      <h2 className="text-sm font-semibold mb-4 text-muted uppercase tracking-widest">Quant Algorithms</h2>
      {isLoading ? (
        <div className="h-40 animate-pulse bg-border rounded" />
      ) : algos.length === 0 ? (
        <p className="text-muted text-sm">No algos yet — agents will submit after first run</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2">Name</th>
              <th className="text-left py-2">Agent</th>
              <th className="text-left py-2">Type</th>
              <th className="text-center py-2">Status</th>
              <th className="text-right py-2">Sharpe</th>
              <th className="text-right py-2">Max DD</th>
              <th className="text-right py-2">Win %</th>
              <th className="text-right py-2">Trades</th>
            </tr>
          </thead>
          <tbody>
            {algos.map((a) => (
              <tr key={a.id} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 font-medium">{a.name}</td>
                <td className="py-2 text-muted text-xs">{a.quant_agent}</td>
                <td className="py-2 text-muted text-xs">{a.strategy_type}</td>
                <td className="py-2 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[a.status] ?? "text-muted"}`}>
                    {a.status.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 text-right font-mono">{a.sharpe_ratio?.toFixed(2) ?? "—"}</td>
                <td className="py-2 text-right font-mono text-danger">{a.max_drawdown ? `${(a.max_drawdown * 100).toFixed(1)}%` : "—"}</td>
                <td className="py-2 text-right font-mono">{a.win_rate ? `${(a.win_rate * 100).toFixed(1)}%` : "—"}</td>
                <td className="py-2 text-right font-mono">{a.trade_count ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/app/quant/page.tsx**

```tsx
// dashboard/app/quant/page.tsx
import { AlgosTable } from "@/components/quant/algos-table";

export default function QuantPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Quant Lab</h1>
      <AlgosTable />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/quant/ dashboard/components/quant/
git commit -m "feat(dashboard): Quant Lab tab with algo performance table"
```

---

## Task 16: Operations Tab

**Files:**
- Create: `dashboard/components/ops/agent-board.tsx`
- Create: `dashboard/app/ops/page.tsx`

- [ ] **Step 1: Create dashboard/components/ops/agent-board.tsx**

```tsx
// dashboard/components/ops/agent-board.tsx
"use client";
import useSWR from "swr";
import { api, type AgentHealth } from "@/lib/api";

const STATUS_CONFIG = {
  healthy:  { color: "text-accent",   dot: "bg-accent",   label: "HEALTHY" },
  degraded: { color: "text-warning",  dot: "bg-warning",  label: "DEGRADED" },
  down:     { color: "text-danger",   dot: "bg-danger",   label: "DOWN" },
};

const ALL_AGENTS = [
  "ingest", "technical", "sentiment", "macro", "research", "aggregator",
  "momentum", "mean_reversion", "ml_quant", "quant_supervisor",
  "portfolio_mgr", "risk", "execution", "cio", "ops",
];

export function AgentBoard() {
  const { data = [], isLoading } = useSWR<AgentHealth[]>(
    "agent-health",
    api.agentHealth,
    { refreshInterval: 10000 }
  );

  const byAgent = Object.fromEntries(data.map((h) => [h.agent, h]));

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-4 text-muted uppercase tracking-widest">Agent Status Board</h2>
      {isLoading ? (
        <div className="h-40 animate-pulse bg-border rounded" />
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {ALL_AGENTS.map((agent) => {
            const health = byAgent[agent];
            const status = (health?.status ?? "down") as keyof typeof STATUS_CONFIG;
            const { color, dot, label } = STATUS_CONFIG[status] ?? STATUS_CONFIG.down;
            return (
              <div key={agent} className="border border-border rounded-lg p-3 flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                <div>
                  <p className="text-sm font-medium capitalize">{agent.replace(/_/g, " ")}</p>
                  <p className={`text-xs ${color}`}>{label}</p>
                  {health && (
                    <p className="text-xs text-muted">{new Date(health.time).toLocaleTimeString()}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/app/ops/page.tsx**

```tsx
// dashboard/app/ops/page.tsx
import { AgentBoard } from "@/components/ops/agent-board";

export default function OpsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Operations</h1>
      <AgentBoard />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/ops/ dashboard/components/ops/
git commit -m "feat(dashboard): Operations tab with agent health status board"
```

---

## Task 17: CIO Chat Tab

**Files:**
- Create: `dashboard/components/chat/cio-chat.tsx`
- Create: `dashboard/app/chat/page.tsx`

- [ ] **Step 1: Create dashboard/components/chat/cio-chat.tsx**

```tsx
// dashboard/components/chat/cio-chat.tsx
"use client";
import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "cio";
  content: string;
  time: Date;
}

const QUICK_ACTIONS = [
  "Give me the daily briefing",
  "What is the current portfolio status?",
  "Run backtest on momentum strategy",
  "Pause all trading",
];

export function CioChat() {
  const [messages, setMessages] = useState<Message[]>([{
    role: "cio",
    content: "Hello. I am your Chief Investment Officer. Ask me anything about the portfolio, market conditions, or give me instructions.",
    time: new Date(),
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim()) return;
    const userMsg: Message = { role: "user", content: text, time: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "cio", content: data.reply, time: new Date() }]);
    } catch {
      setMessages((prev) => [...prev, { role: "cio", content: "Connection error — check gateway.", time: new Date() }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] bg-surface border border-border rounded-xl overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${msg.role === "cio" ? "bg-accent/20 text-accent" : "bg-purple-500/20 text-purple-400"}`}>
              {msg.role === "cio" ? "CIO" : "ME"}
            </div>
            <div className={`max-w-2xl px-4 py-3 rounded-xl text-sm leading-relaxed ${msg.role === "cio" ? "bg-border text-slate-200" : "bg-purple-500/10 text-slate-200 text-right"}`}>
              {msg.content}
              <p className="text-xs text-muted mt-1">{msg.time.toLocaleTimeString()}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center text-xs font-bold">CIO</div>
            <div className="bg-border px-4 py-3 rounded-xl">
              <span className="text-muted text-sm animate-pulse">Thinking…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick actions */}
      <div className="px-4 py-2 border-t border-border flex gap-2 overflow-x-auto">
        {QUICK_ACTIONS.map((action) => (
          <button key={action} onClick={() => send(action)}
            className="shrink-0 px-3 py-1.5 rounded-full bg-border text-muted text-xs hover:text-white hover:bg-white/10 transition-colors">
            {action}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
          placeholder="Ask the CIO anything…"
          className="flex-1 bg-border border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-muted focus:outline-none focus:border-accent transition-colors"
        />
        <button onClick={() => send(input)} disabled={loading || !input.trim()}
          className="px-5 py-3 bg-accent text-black text-sm font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors">
          Send
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard/app/chat/page.tsx**

```tsx
// dashboard/app/chat/page.tsx
import { CioChat } from "@/components/chat/cio-chat";

export default function ChatPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">CIO Chat</h1>
      <CioChat />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add dashboard/app/chat/ dashboard/components/chat/
git commit -m "feat(dashboard): CIO Chat tab with conversational interface"
```

---

## Task 18: Wire Everything Up + Smoke Test

- [ ] **Step 1: Start gateway**

```powershell
Set-Location C:\Users\jomik\hedge-fund
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\jomik\hedge-fund; .venv\Scripts\uvicorn.exe gateway.main:app --port 8000 --reload"
```

- [ ] **Step 2: Start dashboard**

```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\jomik\hedge-fund\dashboard; npm run dev"
```

- [ ] **Step 3: Verify gateway is healthy**

```powershell
Start-Sleep -Seconds 5
Invoke-RestMethod http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Open dashboard in browser**

```powershell
Start-Process "http://localhost:3000/overview"
```

Expected: Dark Bloomberg-style dashboard with sidebar, P&L card showing $100,000 (no data yet), Overview tab active.

Navigate to each tab and verify they render without errors.

- [ ] **Step 5: Run full test suite to ensure nothing broke**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
```

Expected: 187+ tests passing (all original + new gateway tests)

- [ ] **Step 6: Final commit**

```powershell
cd C:\Users\jomik\hedge-fund
git add -A
git commit -m "feat: complete gateway + dashboard — all 7 tabs live"
```

---

*Next plans:*
- `2026-05-24-remaining-agents.md` — Portfolio Researcher, The Engineer, ChromaDB/Obsidian memory, ML retraining
- `2026-05-24-notifications-auth.md` — Gmail notifications, JWT auth, kill switch, security hardening
