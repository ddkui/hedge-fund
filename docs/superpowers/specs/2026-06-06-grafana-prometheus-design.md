# Grafana + Prometheus Monitoring — Design Spec

**Date:** 2026-06-06  
**Status:** Approved  
**Build order:** 2 of 5

---

## Overview

Add production-grade monitoring to the hedge fund system. Prometheus scrapes a `/metrics` endpoint on the existing gateway every 15 seconds. Grafana reads from Prometheus and serves three dashboards (Agent Health, Trading Activity, Portfolio). Both services run in Docker Compose, accessible via Caddy with password auth. Dashboard login is upgraded from stored password to email OTP (magic link) for improved security.

---

## Architecture

### Prometheus metrics endpoint — `gateway/routers/metrics.py`

Exposes `GET /metrics` returning Prometheus text format via `prometheus_client` Python library. Registered on the existing FastAPI app. Metrics are computed by querying TimescaleDB on each scrape, cached for 15 seconds to avoid hammering the DB.

**Metrics registry:**

#### Agent Health Dashboard
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `hf_agent_up` | Gauge | `agent` | 1=healthy, 0=down (from agent_health table) |
| `hf_agent_last_heartbeat_seconds` | Gauge | `agent` | Seconds since last heartbeat |
| `hf_agent_restart_count` | Counter | `agent` | Total restart attempts by Engineer agent |

#### Trading Activity Dashboard
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `hf_trades_total` | Counter | `status`, `broker` | Trades by status (executed/denied/pending) |
| `hf_signals_total` | Counter | `agent`, `signal_type` | Signals emitted per agent |
| `hf_execution_latency_seconds` | Histogram | `broker` | Time from pending → executed |
| `hf_pending_trades_count` | Gauge | — | Current queue depth |

#### Portfolio Dashboard
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `hf_portfolio_value_usd` | Gauge | — | Current total_value from portfolio_state |
| `hf_portfolio_drawdown_pct` | Gauge | — | Current drawdown from peak |
| `hf_open_positions_count` | Gauge | — | Count of open positions |
| `hf_cash_usd` | Gauge | — | Current cash balance |

### Docker Compose additions

```yaml
prometheus:
  image: prom/prometheus:v2.51.0
  restart: unless-stopped
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - prometheus_data:/prometheus
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.retention.time=90d'

grafana:
  image: grafana/grafana:10.4.0
  restart: unless-stopped
  ports:
    - "3001:3000"
  environment:
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    GF_SERVER_ROOT_URL: https://${DOMAIN}/grafana
    GF_SERVER_SERVE_FROM_SUB_PATH: "true"
  volumes:
    - grafana_data:/var/lib/grafana
    - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
  depends_on:
    - prometheus
```

`monitoring/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: hedge_fund_gateway
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: /metrics
```

Caddy routes `/grafana/*` to Grafana with Caddy basic auth (separate from dashboard login).

### Grafana dashboards (provisioned as JSON, checked into repo)

Three dashboard JSON files in `monitoring/grafana/dashboards/`:
- `agent-health.json` — status table + timeline for each agent, restart counter
- `trading-activity.json` — trades/hour rate, signal volume, execution latency heatmap, pending queue
- `portfolio.json` — portfolio value gauge, drawdown gauge, position count, cash gauge

### Email OTP login (dashboard auth upgrade)

Replaces the current single-password auth with a two-step magic-link flow.

**Flow:**
```
1. User visits /login → enters email address
2. Gateway POST /auth/request-otp
   → generates 6-digit OTP
   → stores in Redis: otp:{email} = {otp, expires_at} TTL=600s
   → sends Gmail via existing NotificationService
3. User enters OTP on /login step 2
4. Gateway POST /auth/verify-otp
   → validates OTP from Redis
   → deletes OTP key (single-use)
   → issues JWT (same as current)
5. JWT stored in httpOnly cookie, middleware unchanged
```

**Security properties:**
- OTP is 6 digits, single-use, 10-minute TTL
- Rate-limited: max 3 OTP requests per email per 15 minutes (slowapi)
- Invalid OTP attempts: max 5 before lockout for 15 minutes (Redis counter)
- JWT expiry unchanged at 24 hours

**New gateway endpoints:**
- `POST /auth/request-otp` — body: `{email: string}` → sends OTP email
- `POST /auth/verify-otp` — body: `{email: string, otp: string}` → returns JWT

**Config addition:**
```
ALLOWED_LOGIN_EMAILS=user@example.com,other@example.com  # comma-separated allowlist
```

**Dashboard login page update:**
- Step 1: email input + "Send Code" button
- Step 2: 6-digit OTP input (auto-focus, auto-submit on 6 chars) + "Verify" button + "Resend" (after 60s)

---

## Files

### New
- `gateway/routers/metrics.py`
- `monitoring/prometheus.yml`
- `monitoring/grafana/dashboards/agent-health.json`
- `monitoring/grafana/dashboards/trading-activity.json`
- `monitoring/grafana/dashboards/portfolio.json`
- `monitoring/grafana/datasources/prometheus.yml`
- `tests/gateway/test_metrics.py`

### Modified
- `gateway/main.py` — register metrics router
- `gateway/routers/auth.py` — add OTP endpoints, remove password endpoint
- `dashboard/app/login/page.tsx` — two-step OTP flow
- `docker-compose.yml` — add prometheus, grafana services + volumes
- `shared/config.py` — add `allowed_login_emails`, `grafana_password`
- `.env.example` — document new vars

---

## Tests

- `test_metrics_endpoint_returns_prometheus_format` — assert Content-Type and metric names present
- `test_metrics_agent_health_reflects_db` — mock agent_health rows, assert gauge values
- `test_otp_request_sends_email_and_stores_redis` — mock Gmail + Redis, assert OTP stored
- `test_otp_verify_issues_jwt_on_correct_code` — assert JWT returned
- `test_otp_verify_rejects_wrong_code` — assert 401
- `test_otp_rate_limit_blocks_after_3_requests` — assert 429 on 4th request
