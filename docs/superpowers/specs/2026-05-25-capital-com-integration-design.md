# Capital.com Integration Design

**Date:** 2026-05-25  
**Scope:** Add Capital.com as a live broker (execution + streaming price feed) for all CFD asset classes — forex, indices, commodities, and shares.

---

## Overview

Capital.com becomes the third broker adapter alongside Alpaca (equities) and Binance (crypto). It handles CFD trading across all asset classes and also replaces Yahoo Finance as the live price source for Capital.com instruments via a dedicated WebSocket price feed subprocess.

Agents specify Capital.com epics directly in their trade signals (e.g. `GOLD`, `EURUSD`, `US30`, `AAPL`). Fixed leverage is configured per asset class in `.env`.

---

## Architecture

```
Capital.com REST API  ←→  CapitalComSession (CST + X-SECURITY-TOKEN, auto-refresh)
        │
        ├── Order execution  →  ExecutionAgent._capital_com_fill()
        │                       agents/execution/agent.py
        │
        └── Streaming prices →  CapitalPriceFeed (WebSocket / LIGHTSTREAMER)
                                 shared/capital_com.py
                                 agents/capital_feed/agent.py (subprocess)
                                 → upserts to: prices table
```

### Auth Flow

Capital.com uses session-based auth:

1. POST `/api/v1/session` with `X-CAP-API-KEY` header + `{identifier, password}` body
2. Response returns `CST` and `X-SECURITY-TOKEN` headers — required on all subsequent requests
3. Tokens expire at 10 minutes — `CapitalComSession` refreshes every 9 minutes via background task
4. On 401 → re-authenticate once and retry; if still failing → fail the trade

### Routing

A pending trade is routed to Capital.com when:
- `settings.capital_com_api_key != ""`
- `settings.paper_trading == False`
- `trade["broker"] == "capital_com"` (agents set this field)

The existing `paper → Yahoo Finance` path is untouched.

---

## Components

### New Files

```
shared/
└── capital_com.py              # CapitalComSession + CapitalPriceFeed

agents/
└── capital_feed/
    ├── __init__.py
    └── agent.py                # subprocess entry point: runs CapitalPriceFeed

tests/
├── shared/
│   └── test_capital_com.py     # unit tests (all mocked)
└── agents/
    └── capital_feed/
        └── test_agent.py
```

### Modified Files

```
agents/execution/agent.py       # add _capital_com_fill()
shared/config.py                # add capital_com_* settings
scripts/start_all.py            # add capital_feed to subprocess list
.env.example                    # document new env vars
```

---

## Data Flow

### Price Feed

```
Capital.com WS → CapitalPriceFeed.on_tick(epic, bid, ask)
  → mid = (bid + ask) / 2
  → upsert prices (symbol=epic, close=mid, time=now)
```

Subscribes to all epics in `settings.capital_com_watchlist` on connect. On WebSocket disconnect: exponential backoff reconnect (1s → 2s → 4s … cap 60s).

### Execution

```
trades (status='pending', broker='capital_com')
  → ExecutionAgent._get_fill_price()
    → _capital_com_fill(trade)
      → CapitalComSession.place_order(epic, direction, size, leverage)
      → returns fill_price (level from order response)
  → _apply_fill() [unchanged]
```

Direction mapping: `long` → `BUY`, `close`/`short` → `SELL`.  
Size = `trade["quantity"]` (units, not notional).  
Leverage applied as `dealReference` size multiplier per asset class.

---

## Configuration

New `.env` keys:

```env
CAPITAL_COM_API_KEY=your-api-key
CAPITAL_COM_PASSWORD=your-account-password
CAPITAL_COM_DEMO=true                     # true=demo, false=live

CAPITAL_COM_LEVERAGE_FOREX=10
CAPITAL_COM_LEVERAGE_INDICES=5
CAPITAL_COM_LEVERAGE_COMMODITIES=5
CAPITAL_COM_LEVERAGE_SHARES=5

CAPITAL_COM_WATCHLIST=GOLD,EURUSD,US30,AAPL
```

Leverage is selected by asset class — agents tag trades with `asset_class` (`forex`, `indices`, `commodities`, `shares`). Defaults to 1 (no leverage) if unrecognised.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| 401 on any request | Re-auth once, retry; if still 401 → `_fail_trade()` |
| Order placement fails | Retry after 2s (same as Alpaca/Binance); second failure → `_fail_trade()` |
| WS disconnects | Exponential backoff reconnect, gap in prices table is acceptable |
| Missing price for symbol | ExecutionAgent skips trade (existing behaviour) |
| Token expiry | Background task refreshes at 9 min mark proactively |

No partial fills expected — Capital.com CFD market orders fill fully at quoted price.

---

## Tests (all mocked — no real API calls)

| Test | File |
|---|---|
| `test_session_auth_creates_tokens` | test_capital_com.py |
| `test_session_refresh_called_before_expiry` | test_capital_com.py |
| `test_session_reauth_on_401` | test_capital_com.py |
| `test_capital_fill_long_returns_fill_price` | test_capital_com.py |
| `test_capital_fill_short_returns_fill_price` | test_capital_com.py |
| `test_capital_fill_retries_on_failure` | test_capital_com.py |
| `test_capital_fill_fails_trade_on_double_failure` | test_capital_com.py |
| `test_price_feed_upserts_tick_to_db` | test_capital_com.py |
| `test_price_feed_reconnects_on_disconnect` | test_capital_com.py |
| `test_leverage_applied_correctly_per_asset_class` | test_capital_com.py |
| `test_capital_feed_agent_starts_feed` | test_agent.py |

All existing 230 tests must continue to pass after the integration.
