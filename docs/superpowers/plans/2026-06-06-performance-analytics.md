# Performance Analytics Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live `/analytics` dashboard tab with equity curve, daily returns, drawdown chart, P&L by symbol, key metrics, and a monthly returns heatmap — all updating in real-time when trades execute.

**Architecture:** New FastAPI router computes all metrics server-side from existing `portfolio_state` and `trades` tables. Dashboard uses Chart.js + react-chartjs-2 for rendering. The existing `useWebSocket()` hook triggers SWR cache invalidation on `trade.executed` events so charts refresh automatically within seconds of a fill.

**Tech Stack:** Python (FastAPI, asyncpg), Chart.js 4, react-chartjs-2, SWR, Next.js 14, Tailwind CSS

---

## File Structure

```
gateway/routers/analytics.py          NEW — 4 endpoints: summary, equity-curve, pnl-by-symbol, monthly-returns
tests/gateway/test_analytics.py       NEW — gateway tests
dashboard/app/analytics/page.tsx       NEW — page with range selector + 4 sections
dashboard/components/analytics/
  metrics-row.tsx                      NEW — 6 stat cards
  equity-chart.tsx                     NEW — line chart (portfolio value)
  returns-chart.tsx                    NEW — bar chart (daily returns)
  drawdown-chart.tsx                   NEW — area chart (drawdown from peak)
  pnl-by-symbol.tsx                    NEW — horizontal bar chart
  monthly-heatmap.tsx                  NEW — grid heatmap (year × month)
dashboard/components/layout/sidebar.tsx  MODIFY — add Analytics nav entry
gateway/main.py                        MODIFY — register analytics router
dashboard/package.json                 MODIFY — add chart.js, react-chartjs-2
```

---

## Task 1: Gateway analytics router + tests

**Files:**
- Create: `gateway/routers/analytics.py`
- Create: `tests/gateway/test_analytics.py`
- Modify: `gateway/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gateway/test_analytics.py
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_summary_returns_metrics(client, mock_db):
    mock_db.fetch.side_effect = [
        # portfolio_state rows (daily)
        [
            {"time": "2026-06-01T00:00:00+00:00", "total_value": 100000.0},
            {"time": "2026-06-02T00:00:00+00:00", "total_value": 101500.0},
            {"time": "2026-06-03T00:00:00+00:00", "total_value": 103000.0},
            {"time": "2026-06-04T00:00:00+00:00", "total_value": 102000.0},
            {"time": "2026-06-05T00:00:00+00:00", "total_value": 104000.0},
        ],
        # closed trades
        [
            {"symbol": "AAPL", "action": "long", "quantity": 10.0, "price": 180.0,
             "entry_price": 175.0, "time": "2026-06-03T00:00:00+00:00"},
            {"symbol": "MSFT", "action": "long", "quantity": 5.0, "price": 420.0,
             "entry_price": 430.0, "time": "2026-06-04T00:00:00+00:00"},
        ],
    ]
    resp = await client.get("/analytics/summary?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    assert "sharpe" in data
    assert "max_drawdown" in data
    assert "win_rate" in data
    assert "total_pnl" in data
    assert "trade_count" in data
    assert data["trade_count"] == 2
    assert data["win_rate"] == 0.5  # 1 win (AAPL), 1 loss (MSFT)


@pytest.mark.asyncio
async def test_summary_insufficient_data_returns_error(client, mock_db):
    mock_db.fetch.side_effect = [[], []]
    resp = await client.get("/analytics/summary?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("error") == "insufficient_data"


@pytest.mark.asyncio
async def test_equity_curve_returns_time_series(client, mock_db):
    mock_db.fetch.return_value = [
        {"time": "2026-06-01T00:00:00+00:00", "total_value": 100000.0},
        {"time": "2026-06-02T00:00:00+00:00", "total_value": 101000.0},
    ]
    resp = await client.get("/analytics/equity-curve?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    assert "equity" in data
    assert "daily_returns" in data
    assert "drawdown" in data
    assert len(data["equity"]) == 2


@pytest.mark.asyncio
async def test_pnl_by_symbol_aggregates(client, mock_db):
    mock_db.fetch.return_value = [
        {"symbol": "AAPL", "action": "long", "quantity": 10.0,
         "price": 185.0, "entry_price": 180.0},
        {"symbol": "AAPL", "action": "long", "quantity": 5.0,
         "price": 185.0, "entry_price": 183.0},
        {"symbol": "MSFT", "action": "long", "quantity": 3.0,
         "price": 400.0, "entry_price": 420.0},
    ]
    resp = await client.get("/analytics/pnl-by-symbol?range=7d")
    assert resp.status_code == 200
    data = resp.json()
    symbols = {d["symbol"] for d in data}
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    aapl = next(d for d in data if d["symbol"] == "AAPL")
    assert aapl["pnl"] > 0   # (185-180)*10 + (185-183)*5 = 60


@pytest.mark.asyncio
async def test_monthly_returns_grid(client, mock_db):
    mock_db.fetch.return_value = [
        {"time": "2026-06-01T00:00:00+00:00", "total_value": 100000.0},
        {"time": "2026-06-30T00:00:00+00:00", "total_value": 104000.0},
    ]
    resp = await client.get("/analytics/monthly-returns")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["year"] == 2026
    assert data[0]["month"] == 6
    assert abs(data[0]["return_pct"] - 4.0) < 0.01
```

- [ ] **Step 2: Run to verify tests fail**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/gateway/test_analytics.py -v
```

Expected: `ImportError` or 404 (router not registered)

- [ ] **Step 3: Create `gateway/routers/analytics.py`**

```python
# gateway/routers/analytics.py
import math
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()

RANGE_MAP = {
    "1d":  "1 day",
    "7d":  "7 days",
    "1m":  "30 days",
    "3m":  "90 days",
    "all": "36500 days",
}


def _range_interval(range_str: str) -> str:
    return RANGE_MAP.get(range_str, "7 days")


def _compute_sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    return round((mean / std) * math.sqrt(252), 4) if std > 0 else 0.0


def _compute_sortino(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    neg = [r for r in daily_returns if r < 0]
    if not neg:
        return 0.0
    downside_var = sum(r ** 2 for r in neg) / len(neg)
    downside_std = math.sqrt(downside_var)
    return round((mean / downside_std) * math.sqrt(252), 4) if downside_std > 0 else 0.0


def _compute_max_drawdown(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 6)


def _compute_drawdown_series(values: list[float]) -> list[float]:
    peak = values[0] if values else 1.0
    result = []
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        result.append(round(-dd * 100, 4))
    return result


def _compute_daily_returns(values: list[float]) -> list[float]:
    if len(values) < 2:
        return []
    return [
        round((values[i] - values[i - 1]) / values[i - 1] * 100, 4)
        for i in range(1, len(values))
    ]


@router.get("/summary")
async def get_summary(range: str = Query("7d"), db: Database = Depends(get_db)):
    interval = _range_interval(range)
    rows = await db.fetch(
        f"SELECT time, total_value FROM portfolio_state "
        f"WHERE time > now() - INTERVAL '{interval}' ORDER BY time ASC"
    )
    trades = await db.fetch(
        f"SELECT symbol, action, quantity, price, entry_price FROM trades "
        f"WHERE status = 'executed' AND time > now() - INTERVAL '{interval}'"
    )
    values = [float(r["total_value"]) for r in rows]
    if len(values) < 2:
        return {"error": "insufficient_data"}

    daily_returns = _compute_daily_returns(values)
    pnls = [
        (float(t["price"]) - float(t["entry_price"])) * float(t["quantity"])
        * (1 if t["action"] == "long" else -1)
        for t in trades
    ]
    wins = sum(1 for p in pnls if p > 0)
    start_val = values[0]
    end_val = values[-1]
    days = max((datetime.fromisoformat(str(rows[-1]["time"])) -
                datetime.fromisoformat(str(rows[0]["time"]))).days, 1)
    cagr = round(((end_val / start_val) ** (365 / days) - 1) * 100, 4) if start_val > 0 else 0.0

    return {
        "sharpe": _compute_sharpe(daily_returns),
        "sortino": _compute_sortino(daily_returns),
        "max_drawdown": round(_compute_max_drawdown(values) * 100, 4),
        "win_rate": round(wins / len(pnls), 4) if pnls else 0.0,
        "total_pnl": round(sum(pnls), 2),
        "trade_count": len(trades),
        "cagr": cagr,
        "start_value": start_val,
        "end_value": end_val,
    }


@router.get("/equity-curve")
async def get_equity_curve(range: str = Query("7d"), db: Database = Depends(get_db)):
    interval = _range_interval(range)
    rows = await db.fetch(
        f"SELECT time, total_value FROM portfolio_state "
        f"WHERE time > now() - INTERVAL '{interval}' ORDER BY time ASC"
    )
    times = [str(r["time"]) for r in rows]
    values = [float(r["total_value"]) for r in rows]
    daily_returns = _compute_daily_returns(values)
    drawdown = _compute_drawdown_series(values)
    return {
        "labels": times,
        "equity": values,
        "daily_returns": [0.0] + daily_returns,
        "drawdown": drawdown,
    }


@router.get("/pnl-by-symbol")
async def get_pnl_by_symbol(range: str = Query("7d"), db: Database = Depends(get_db)):
    interval = _range_interval(range)
    trades = await db.fetch(
        f"SELECT symbol, action, quantity, price, entry_price FROM trades "
        f"WHERE status = 'executed' AND time > now() - INTERVAL '{interval}'"
    )
    by_symbol: dict[str, float] = {}
    for t in trades:
        pnl = (float(t["price"]) - float(t["entry_price"])) * float(t["quantity"])
        if t["action"] == "short":
            pnl = -pnl
        by_symbol[t["symbol"]] = by_symbol.get(t["symbol"], 0.0) + pnl
    result = [{"symbol": s, "pnl": round(p, 2)} for s, p in by_symbol.items()]
    return sorted(result, key=lambda x: x["pnl"], reverse=True)


@router.get("/monthly-returns")
async def get_monthly_returns(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT time, total_value FROM portfolio_state ORDER BY time ASC"
    )
    if not rows:
        return []
    # Group by year-month, take first and last value
    monthly: dict[tuple, list[float]] = {}
    for r in rows:
        t = datetime.fromisoformat(str(r["time"]).replace("+00:00", "+00:00"))
        key = (t.year, t.month)
        monthly.setdefault(key, []).append(float(r["total_value"]))
    result = []
    for (year, month), vals in sorted(monthly.items()):
        ret = round((vals[-1] - vals[0]) / vals[0] * 100, 4) if vals[0] > 0 else 0.0
        result.append({"year": year, "month": month, "return_pct": ret})
    return result
```

- [ ] **Step 4: Register router in `gateway/main.py`**

Add to imports:
```python
from gateway.routers import analytics as analytics_router
```

Add after the other `app.include_router` lines:
```python
app.include_router(analytics_router.router, prefix="/analytics", tags=["analytics"])
```

- [ ] **Step 5: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_analytics.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```powershell
git add gateway/routers/analytics.py gateway/main.py tests/gateway/test_analytics.py
git commit -m "feat(analytics): gateway router with summary, equity-curve, pnl-by-symbol, monthly-returns"
```

---

## Task 2: Install Chart.js dependencies

**Files:**
- Modify: `dashboard/package.json`

- [ ] **Step 1: Install deps**

```powershell
Set-Location C:\Users\jomik\hedge-fund\dashboard
npm install chart.js@^4.4.0 react-chartjs-2@^5.2.0
```

Expected: `added N packages`

- [ ] **Step 2: Commit**

```powershell
Set-Location C:\Users\jomik\hedge-fund
git add dashboard/package.json dashboard/package-lock.json
git commit -m "feat(analytics): add chart.js and react-chartjs-2"
```

---

## Task 3: Metrics Row component

**Files:**
- Create: `dashboard/components/analytics/metrics-row.tsx`

- [ ] **Step 1: Create `dashboard/components/analytics/metrics-row.tsx`**

```tsx
// dashboard/components/analytics/metrics-row.tsx
"use client";

interface Metrics {
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  win_rate: number;
  cagr: number;
  total_pnl: number;
  trade_count: number;
  error?: string;
}

interface MetricsRowProps {
  data: Metrics | null;
  isLoading: boolean;
}

function StatCard({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 text-center">
      <p className="text-xs text-muted uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-2xl font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}

export function MetricsRow({ data, isLoading }: MetricsRowProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-surface border border-border rounded-xl p-4 h-20 animate-pulse" />
        ))}
      </div>
    );
  }
  if (!data || data.error) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 text-center text-muted text-sm">
        Not enough trading history yet — make some trades first.
      </div>
    );
  }
  const pnlColor = data.total_pnl >= 0 ? "text-accent" : "text-danger";
  const ddColor = "text-danger";
  return (
    <div className="grid grid-cols-6 gap-3">
      <StatCard label="Sharpe" value={data.sharpe.toFixed(2)} color={data.sharpe >= 1 ? "text-accent" : "text-warning"} />
      <StatCard label="Sortino" value={data.sortino.toFixed(2)} color={data.sortino >= 1 ? "text-accent" : "text-warning"} />
      <StatCard label="Max Drawdown" value={`-${data.max_drawdown.toFixed(2)}%`} color={ddColor} />
      <StatCard label="Win Rate" value={`${(data.win_rate * 100).toFixed(1)}%`} color={data.win_rate >= 0.5 ? "text-accent" : "text-danger"} />
      <StatCard label="CAGR" value={`${data.cagr.toFixed(2)}%`} color={data.cagr >= 0 ? "text-accent" : "text-danger"} />
      <StatCard label="Total P&L" value={`$${data.total_pnl.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} color={pnlColor} />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```powershell
git add dashboard/components/analytics/metrics-row.tsx
git commit -m "feat(analytics): MetricsRow component with 6 stat cards"
```

---

## Task 4: Equity + Daily Returns charts

**Files:**
- Create: `dashboard/components/analytics/equity-chart.tsx`
- Create: `dashboard/components/analytics/returns-chart.tsx`

- [ ] **Step 1: Create `dashboard/components/analytics/equity-chart.tsx`**

```tsx
// dashboard/components/analytics/equity-chart.tsx
"use client";
import { useEffect, useRef } from "react";
import {
  Chart, LineElement, PointElement, LinearScale, TimeScale,
  CategoryScale, Tooltip, Legend, Filler, type ChartData,
} from "chart.js";
import { Line } from "react-chartjs-2";

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler);

interface EquityChartProps {
  labels: string[];
  values: number[];
}

export function EquityChart({ labels, values }: EquityChartProps) {
  const data: ChartData<"line"> = {
    labels: labels.map((l) => new Date(l).toLocaleDateString()),
    datasets: [
      {
        label: "Portfolio Value",
        data: values,
        borderColor: "#00d4aa",
        backgroundColor: "rgba(0,212,170,0.08)",
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        borderWidth: 2,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: "index" as const } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#6b7280", callback: (v: number) => `$${v.toLocaleString()}` }, grid: { color: "#1e1e2e" } },
    },
  };
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Equity Curve</h2>
      <div style={{ height: 240 }}>
        <Line data={data} options={options} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/components/analytics/returns-chart.tsx`**

```tsx
// dashboard/components/analytics/returns-chart.tsx
"use client";
import { Chart, BarElement, LinearScale, CategoryScale, Tooltip } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(BarElement, LinearScale, CategoryScale, Tooltip);

interface ReturnsChartProps {
  labels: string[];
  returns: number[];
}

export function ReturnsChart({ labels, returns }: ReturnsChartProps) {
  const data = {
    labels: labels.map((l) => new Date(l).toLocaleDateString()),
    datasets: [
      {
        label: "Daily Return %",
        data: returns,
        backgroundColor: returns.map((r) => (r >= 0 ? "rgba(0,212,170,0.7)" : "rgba(255,71,87,0.7)")),
        borderRadius: 2,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#6b7280", callback: (v: number) => `${v}%` }, grid: { color: "#1e1e2e" } },
    },
  };
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Daily Returns</h2>
      <div style={{ height: 240 }}>
        <Bar data={data} options={options} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
git add dashboard/components/analytics/equity-chart.tsx dashboard/components/analytics/returns-chart.tsx
git commit -m "feat(analytics): EquityChart and ReturnsChart components"
```

---

## Task 5: Drawdown + P&L by Symbol charts

**Files:**
- Create: `dashboard/components/analytics/drawdown-chart.tsx`
- Create: `dashboard/components/analytics/pnl-by-symbol.tsx`

- [ ] **Step 1: Create `dashboard/components/analytics/drawdown-chart.tsx`**

```tsx
// dashboard/components/analytics/drawdown-chart.tsx
"use client";
import { Chart, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler } from "chart.js";
import { Line } from "react-chartjs-2";

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler);

interface DrawdownChartProps {
  labels: string[];
  drawdown: number[];
}

export function DrawdownChart({ labels, drawdown }: DrawdownChartProps) {
  const data = {
    labels: labels.map((l) => new Date(l).toLocaleDateString()),
    datasets: [
      {
        label: "Drawdown %",
        data: drawdown,
        borderColor: "#ff4757",
        backgroundColor: "rgba(255,71,87,0.15)",
        fill: true,
        tension: 0.3,
        pointRadius: 1,
        borderWidth: 1.5,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#6b7280", callback: (v: number) => `${v}%` }, grid: { color: "#1e1e2e" }, max: 0 },
    },
  };
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Drawdown</h2>
      <div style={{ height: 240 }}>
        <Line data={data} options={options} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/components/analytics/pnl-by-symbol.tsx`**

```tsx
// dashboard/components/analytics/pnl-by-symbol.tsx
"use client";
import { Chart, BarElement, LinearScale, CategoryScale, Tooltip } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(BarElement, LinearScale, CategoryScale, Tooltip);

interface PnlEntry { symbol: string; pnl: number; }

export function PnlBySymbol({ data }: { data: PnlEntry[] }) {
  const chartData = {
    labels: data.map((d) => d.symbol),
    datasets: [
      {
        label: "P&L ($)",
        data: data.map((d) => d.pnl),
        backgroundColor: data.map((d) => (d.pnl >= 0 ? "rgba(0,212,170,0.7)" : "rgba(255,71,87,0.7)")),
        borderRadius: 3,
      },
    ],
  };
  const options = {
    indexAxis: "y" as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", callback: (v: number) => `$${v}` }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#e2e8f0" }, grid: { color: "#1e1e2e" } },
    },
  };
  const height = Math.max(200, data.length * 36);
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">P&L by Symbol</h2>
      <div style={{ height }}>
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```powershell
git add dashboard/components/analytics/drawdown-chart.tsx dashboard/components/analytics/pnl-by-symbol.tsx
git commit -m "feat(analytics): DrawdownChart and PnlBySymbol components"
```

---

## Task 6: Monthly Heatmap component

**Files:**
- Create: `dashboard/components/analytics/monthly-heatmap.tsx`

- [ ] **Step 1: Create `dashboard/components/analytics/monthly-heatmap.tsx`**

```tsx
// dashboard/components/analytics/monthly-heatmap.tsx
"use client";

interface MonthlyReturn { year: number; month: number; return_pct: number; }

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function cellColor(ret: number): string {
  if (ret > 5) return "bg-accent text-black";
  if (ret > 2) return "bg-accent/60 text-black";
  if (ret > 0) return "bg-accent/30 text-accent";
  if (ret === 0) return "bg-border text-muted";
  if (ret > -2) return "bg-danger/30 text-danger";
  if (ret > -5) return "bg-danger/60 text-white";
  return "bg-danger text-white";
}

export function MonthlyHeatmap({ data }: { data: MonthlyReturn[] }) {
  const years = [...new Set(data.map((d) => d.year))].sort();
  const lookup = new Map(data.map((d) => [`${d.year}-${d.month}`, d.return_pct]));

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Monthly Returns</h2>
      <div className="overflow-x-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th className="text-muted text-left pr-3 py-1 w-12">Year</th>
              {MONTHS.map((m) => (
                <th key={m} className="text-muted text-center px-1 py-1 w-14">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td className="text-muted pr-3 py-1 font-mono">{year}</td>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => {
                  const ret = lookup.get(`${year}-${month}`);
                  return (
                    <td key={month} className="px-0.5 py-0.5">
                      {ret !== undefined ? (
                        <div
                          title={`${ret >= 0 ? "+" : ""}${ret.toFixed(2)}%`}
                          className={`text-center rounded px-1 py-1 font-mono cursor-help ${cellColor(ret)}`}
                        >
                          {ret >= 0 ? "+" : ""}{ret.toFixed(1)}
                        </div>
                      ) : (
                        <div className="text-center text-border px-1 py-1">—</div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```powershell
git add dashboard/components/analytics/monthly-heatmap.tsx
git commit -m "feat(analytics): MonthlyHeatmap calendar grid component"
```

---

## Task 7: Analytics page + sidebar entry

**Files:**
- Create: `dashboard/app/analytics/page.tsx`
- Modify: `dashboard/components/layout/sidebar.tsx`

- [ ] **Step 1: Create `dashboard/app/analytics/page.tsx`**

```tsx
// dashboard/app/analytics/page.tsx
"use client";
import useSWR from "swr";
import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { MetricsRow } from "@/components/analytics/metrics-row";
import { EquityChart } from "@/components/analytics/equity-chart";
import { ReturnsChart } from "@/components/analytics/returns-chart";
import { DrawdownChart } from "@/components/analytics/drawdown-chart";
import { PnlBySymbol } from "@/components/analytics/pnl-by-symbol";
import { MonthlyHeatmap } from "@/components/analytics/monthly-heatmap";
import { useWebSocket } from "@/lib/use-ws";

const RANGES = ["1d", "7d", "1m", "3m", "all"] as const;
type Range = typeof RANGES[number];

export default function AnalyticsPage() {
  const [range, setRange] = useState<Range>("7d");
  const { messages } = useWebSocket();

  const { data: summary, isLoading: sumLoading, mutate: mutateSummary } =
    useSWR(`analytics-summary-${range}`, () => apiFetch(`/analytics/summary?range=${range}`), { refreshInterval: 60000 });

  const { data: curve, isLoading: curveLoading, mutate: mutateCurve } =
    useSWR(`analytics-curve-${range}`, () => apiFetch(`/analytics/equity-curve?range=${range}`), { refreshInterval: 60000 });

  const { data: pnlData = [], isLoading: pnlLoading, mutate: mutatePnl } =
    useSWR(`analytics-pnl-${range}`, () => apiFetch(`/analytics/pnl-by-symbol?range=${range}`), { refreshInterval: 60000 });

  const { data: monthly = [], isLoading: monthlyLoading, mutate: mutateMonthly } =
    useSWR("analytics-monthly", () => apiFetch("/analytics/monthly-returns"), { refreshInterval: 300000 });

  // Refresh all on trade execute
  useEffect(() => {
    const latest = messages[0];
    if (latest?.channel === "trade.executed") {
      mutateSummary();
      mutateCurve();
      mutatePnl();
      mutateMonthly();
    }
  }, [messages]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Performance Analytics</h1>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                range === r ? "bg-accent text-black" : "bg-border text-muted hover:text-white"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Key Metrics */}
      <MetricsRow data={summary} isLoading={sumLoading} />

      {/* Equity + Daily Returns */}
      {curve && !curve.error && (
        <div className="grid grid-cols-2 gap-4">
          <EquityChart labels={curve.labels} values={curve.equity} />
          <ReturnsChart labels={curve.labels} returns={curve.daily_returns} />
        </div>
      )}

      {/* Drawdown + P&L by Symbol */}
      <div className="grid grid-cols-2 gap-4">
        {curve && !curve.error && (
          <DrawdownChart labels={curve.labels} drawdown={curve.drawdown} />
        )}
        {!pnlLoading && pnlData.length > 0 && (
          <PnlBySymbol data={pnlData} />
        )}
      </div>

      {/* Monthly Heatmap */}
      {!monthlyLoading && monthly.length > 0 && (
        <MonthlyHeatmap data={monthly} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add Analytics to sidebar**

In `dashboard/components/layout/sidebar.tsx`, add `TrendingUp` to the import:
```tsx
import {
  LayoutDashboard, Cpu, BarChart2, Activity,
  FlaskConical, Server, MessageSquare, ArrowLeftRight, BrainCircuit, TrendingUp
} from "lucide-react";
```

Add to NAV array after `{ href: "/trades", ... }`:
```tsx
{ href: "/analytics",  label: "Analytics",  icon: TrendingUp },
```

- [ ] **Step 3: Run full test suite**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all existing tests + 5 new analytics tests pass

- [ ] **Step 4: Commit**

```powershell
git add dashboard/app/analytics/ dashboard/components/analytics/ dashboard/components/layout/sidebar.tsx
git commit -m "feat(analytics): complete analytics tab with 5 chart components and real-time WS updates"
```
