# Performance Analytics Dashboard — Design Spec

**Date:** 2026-06-06  
**Status:** Approved  
**Build order:** 1 of 5

---

## Overview

A dedicated `/analytics` tab in the Next.js dashboard that shows live trading performance metrics sourced from the existing `portfolio_state` and `trades` TimescaleDB tables. All charts update in real-time when a trade executes via the existing WebSocket broadcast. No new DB tables required.

---

## Architecture

### Gateway — new router `gateway/routers/analytics.py`

Two endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /analytics/summary?range=7d` | Returns all scalar metrics: Sharpe, Sortino, max drawdown, win rate, CAGR, total P&L, trade count |
| `GET /analytics/equity-curve?range=7d` | Returns time-bucketed portfolio values + daily returns + drawdown series |
| `GET /analytics/pnl-by-symbol?range=7d` | Returns aggregated P&L per symbol from closed trades |
| `GET /analytics/monthly-returns` | Returns monthly return % grid (year × month) for heatmap |

Range parameter accepted values: `1d`, `7d`, `1m`, `3m`, `all`.

All metric computation happens server-side in SQL. The dashboard renders only.

**Metric formulas (server-side):**
- **Sharpe** = (mean daily return − 0%) / std daily return × √252
- **Sortino** = mean daily return / std of negative daily returns × √252
- **Max Drawdown** = max((peak − trough) / peak) over the period
- **Win Rate** = count(pnl > 0) / count(all closed trades)
- **CAGR** = (end_value / start_value) ^ (365 / days) − 1
- **Total P&L** = sum of all closed trade P&L

### Dashboard — `dashboard/app/analytics/page.tsx`

**Dependencies added:**
```json
"chart.js": "^4.4.0",
"react-chartjs-2": "^5.2.0"
```

**Page layout — four sections, stacked vertically:**

```
┌─────────────────────────────────────────────────────────┐
│  [1D]  [7D]  [1M]  [3M]  [All]     ← shared range bar  │
├─────────────────────────────────────────────────────────┤
│  SECTION 1: Equity Curve (line) + Daily Returns (bar)   │
│  Left: portfolio_state.total_value over time            │
│  Right: green/red bars for daily return %               │
├─────────────────────────────────────────────────────────┤
│  SECTION 2: Key Metrics (6 stat cards)                  │
│  Sharpe │ Sortino │ Max DD │ Win Rate │ CAGR │ Total P&L │
├─────────────────────────────────────────────────────────┤
│  SECTION 3: Drawdown (area, red fill) + P&L by Symbol   │
│  Left: rolling drawdown from peak                       │
│  Right: horizontal bar chart, sorted by P&L             │
├─────────────────────────────────────────────────────────┤
│  SECTION 4: Monthly Returns Heatmap                     │
│  Grid: rows=years, cols=Jan…Dec                         │
│  Cell colour: green=profit, red=loss, grey=no data      │
└─────────────────────────────────────────────────────────┘
```

**Real-time updates:**  
The page subscribes to the existing `useWebSocket()` hook. When a message arrives on the `trade.executed` channel, SWR's `mutate()` is called for all analytics cache keys. Charts reflect the new trade within seconds.

**Chart.js registration:**  
One `Chart.register(...)` call at the top of the page imports only the required controllers (Line, Bar) to keep bundle size small.

### Sidebar

Add `{ href: "/analytics", label: "Analytics", icon: TrendingUp }` to `sidebar.tsx` between "Trades" and "Consensus".

---

## Data Sources

| Chart | Table | Key columns |
|-------|-------|-------------|
| Equity curve | `portfolio_state` | `time`, `total_value` |
| Daily returns | `portfolio_state` | daily diff of `total_value` |
| Drawdown | `portfolio_state` | rolling max vs current |
| Key metrics | `portfolio_state` + `trades` | computed in SQL |
| P&L by symbol | `trades` | `symbol`, `price`, `quantity`, `action` |
| Monthly heatmap | `portfolio_state` | monthly first/last value |

---

## Files

### New
- `gateway/routers/analytics.py`
- `dashboard/app/analytics/page.tsx`
- `dashboard/components/analytics/equity-chart.tsx`
- `dashboard/components/analytics/returns-chart.tsx`
- `dashboard/components/analytics/drawdown-chart.tsx`
- `dashboard/components/analytics/pnl-by-symbol.tsx`
- `dashboard/components/analytics/monthly-heatmap.tsx`
- `dashboard/components/analytics/metrics-row.tsx`
- `tests/gateway/test_analytics.py`

### Modified
- `gateway/main.py` — register analytics router
- `dashboard/components/layout/sidebar.tsx` — add Analytics nav entry
- `dashboard/package.json` — add chart.js + react-chartjs-2

---

## Error Handling

- Insufficient data (< 2 data points): endpoint returns `{"error": "insufficient_data"}`, dashboard shows "Not enough trading history yet" placeholder
- DB unavailable: FastAPI dependency injection raises 503
- WebSocket disconnected: SWR falls back to polling every 30s

---

## Tests

- `test_analytics_summary_returns_correct_sharpe` — mock portfolio_state rows, assert Sharpe formula
- `test_analytics_equity_curve_range_filtering` — assert 1d range returns only last 24h rows
- `test_analytics_pnl_by_symbol_aggregates_correctly` — multiple trades per symbol, assert sum
- `test_analytics_monthly_returns_grid_shape` — assert correct year/month structure
