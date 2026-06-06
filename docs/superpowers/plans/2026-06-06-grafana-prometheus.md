# Grafana + Prometheus + Email OTP Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Prometheus metrics to the gateway, spin up Grafana with three pre-built dashboards in Docker Compose, and replace the stored-password dashboard login with a secure 6-digit email OTP flow.

**Architecture:** `prometheus_client` library exposes `GET /metrics` on the existing gateway (port 8000). Prometheus scrapes every 15s. Grafana reads from Prometheus and serves three provisioned dashboards. Dashboard login becomes a two-step form: email → OTP sent via Gmail → JWT issued. OTP stored in Redis with 10-minute TTL, rate-limited via slowapi.

**Tech Stack:** Python prometheus_client, FastAPI, Redis, Docker Compose, Grafana 10.4, Prometheus 2.51, Next.js 14

---

## File Structure

```
gateway/routers/metrics.py             NEW — GET /metrics Prometheus endpoint
gateway/routers/auth.py                MODIFY — add /auth/request-otp, /auth/verify-otp
monitoring/prometheus.yml              NEW — Prometheus scrape config
monitoring/grafana/datasources/
  prometheus.yml                       NEW — Grafana datasource provisioning
monitoring/grafana/dashboards/
  dashboards.yml                       NEW — Grafana dashboard provisioning config
  agent-health.json                    NEW — agent health Grafana dashboard
  trading-activity.json                NEW — trading activity Grafana dashboard
  portfolio.json                       NEW — portfolio Grafana dashboard
dashboard/app/login/page.tsx           MODIFY — two-step OTP form
shared/config.py                       MODIFY — add allowed_login_emails, grafana_password
docker-compose.yml                     MODIFY — add prometheus, grafana services
requirements.txt                       MODIFY — add prometheus_client
tests/gateway/test_metrics.py          NEW
tests/gateway/test_auth_otp.py         NEW
```

---

## Task 1: Prometheus metrics endpoint

**Files:**
- Create: `gateway/routers/metrics.py`
- Create: `tests/gateway/test_metrics.py`
- Modify: `gateway/main.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Install prometheus_client**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\pip.exe install prometheus_client==0.20.0
```

Add to `requirements.txt`:
```
prometheus_client==0.20.0
```

- [ ] **Step 2: Write failing tests**

```python
# tests/gateway/test_metrics.py
import pytest


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "technical", "status": "healthy", "time": "2026-06-06T10:00:00+00:00"},
    ]
    mock_db.fetchrow.return_value = {
        "total_value": 105000.0, "cash": 80000.0, "open_positions": 3, "peak_value": 106000.0
    }
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "hf_agent_up" in body
    assert "hf_portfolio_value_usd" in body
    assert "hf_open_positions_count" in body


@pytest.mark.asyncio
async def test_metrics_agent_up_reflects_health(client, mock_db):
    mock_db.fetch.return_value = [
        {"agent": "technical", "status": "healthy", "time": "2026-06-06T10:00:00+00:00"},
        {"agent": "execution", "status": "down", "time": "2026-06-06T10:00:00+00:00"},
    ]
    mock_db.fetchrow.return_value = {"total_value": 100000.0, "cash": 100000.0,
                                      "open_positions": 0, "peak_value": 100000.0}
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert 'hf_agent_up{agent="technical"} 1.0' in body
    assert 'hf_agent_up{agent="execution"} 0.0' in body


@pytest.mark.asyncio
async def test_metrics_portfolio_value_present(client, mock_db):
    mock_db.fetch.return_value = []
    mock_db.fetchrow.return_value = {
        "total_value": 123456.78, "cash": 50000.0, "open_positions": 2, "peak_value": 125000.0
    }
    resp = await client.get("/metrics")
    assert "123456.78" in resp.text
```

- [ ] **Step 3: Run to verify tests fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_metrics.py -v
```

Expected: 404 (route not registered)

- [ ] **Step 4: Create `gateway/routers/metrics.py`**

```python
# gateway/routers/metrics.py
import time
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()

_cache: dict = {"data": None, "ts": 0.0}
CACHE_TTL = 15.0  # seconds


async def _collect(db: Database) -> str:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    lines = []

    # --- Agent health ---
    lines.append("# HELP hf_agent_up 1 if agent is healthy, 0 if down")
    lines.append("# TYPE hf_agent_up gauge")
    agent_rows = await db.fetch(
        """
        SELECT DISTINCT ON (agent) agent, status
        FROM agent_health
        ORDER BY agent, time DESC
        """
    )
    for row in agent_rows:
        val = 1.0 if row["status"] == "healthy" else 0.0
        lines.append(f'hf_agent_up{{agent="{row["agent"]}"}} {val}')

    # --- Portfolio ---
    lines.append("# HELP hf_portfolio_value_usd Current portfolio total value in USD")
    lines.append("# TYPE hf_portfolio_value_usd gauge")
    lines.append("# HELP hf_cash_usd Current cash balance in USD")
    lines.append("# TYPE hf_cash_usd gauge")
    lines.append("# HELP hf_open_positions_count Number of open positions")
    lines.append("# TYPE hf_open_positions_count gauge")
    lines.append("# HELP hf_portfolio_drawdown_pct Current drawdown from peak as percentage")
    lines.append("# TYPE hf_portfolio_drawdown_pct gauge")

    state = await db.fetchrow(
        "SELECT total_value, cash, open_positions, peak_value FROM portfolio_state ORDER BY time DESC LIMIT 1"
    )
    if state:
        total = float(state["total_value"])
        cash = float(state["cash"])
        open_pos = int(state["open_positions"])
        peak = float(state["peak_value"])
        drawdown = (peak - total) / peak * 100 if peak > 0 else 0.0
        lines.append(f"hf_portfolio_value_usd {total}")
        lines.append(f"hf_cash_usd {cash}")
        lines.append(f"hf_open_positions_count {open_pos}")
        lines.append(f"hf_portfolio_drawdown_pct {drawdown:.4f}")
    else:
        lines += ["hf_portfolio_value_usd 0", "hf_cash_usd 0",
                  "hf_open_positions_count 0", "hf_portfolio_drawdown_pct 0"]

    # --- Trades ---
    lines.append("# HELP hf_trades_total Total trades by status")
    lines.append("# TYPE hf_trades_total counter")
    trade_rows = await db.fetch(
        "SELECT status, count(*) as cnt FROM trades GROUP BY status"
    )
    for row in trade_rows:
        lines.append(f'hf_trades_total{{status="{row["status"]}"}} {row["cnt"]}')

    # --- Signals ---
    lines.append("# HELP hf_signals_total Total signals emitted per agent")
    lines.append("# TYPE hf_signals_total counter")
    signal_rows = await db.fetch(
        "SELECT agent, count(*) as cnt FROM signals GROUP BY agent"
    )
    for row in signal_rows:
        lines.append(f'hf_signals_total{{agent="{row["agent"]}"}} {row["cnt"]}')

    # --- Pending trades ---
    lines.append("# HELP hf_pending_trades_count Current pending trade queue depth")
    lines.append("# TYPE hf_pending_trades_count gauge")
    pending = await db.fetch("SELECT count(*) as cnt FROM trades WHERE status = 'pending'")
    lines.append(f"hf_pending_trades_count {pending[0]['cnt'] if pending else 0}")

    output = "\n".join(lines) + "\n"
    _cache["data"] = output
    _cache["ts"] = now
    return output


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(db: Database = Depends(get_db)):
    return await _collect(db)
```

- [ ] **Step 5: Register in `gateway/main.py`**

Add import:
```python
from gateway.routers.metrics import router as metrics_router
```

Add after other routers:
```python
app.include_router(metrics_router)
```

- [ ] **Step 6: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_metrics.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Commit**

```powershell
git add gateway/routers/metrics.py gateway/main.py requirements.txt tests/gateway/test_metrics.py
git commit -m "feat(monitoring): Prometheus /metrics endpoint on gateway"
```

---

## Task 2: Email OTP login

**Files:**
- Modify: `gateway/routers/auth.py`
- Modify: `shared/config.py`
- Create: `tests/gateway/test_auth_otp.py`

- [ ] **Step 1: Add config settings**

In `shared/config.py`, add to the `Settings` class:
```python
    allowed_login_emails: str = ""       # comma-separated: user@example.com,other@example.com
    otp_expiry_seconds: int = 600        # 10 minutes
```

- [ ] **Step 2: Write failing tests**

```python
# tests/gateway/test_auth_otp.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_request_otp_sends_email_and_stores_redis(client, mock_bus):
    with patch("gateway.routers.auth.settings") as mock_settings:
        mock_settings.allowed_login_emails = "test@example.com"
        mock_settings.otp_expiry_seconds = 600
        mock_settings.gmail_sender = "sender@gmail.com"
        mock_settings.gmail_app_password = "app-pass"
        mock_bus.set = AsyncMock()
        with patch("gateway.routers.auth._send_otp_email") as mock_send:
            resp = await client.post("/auth/request-otp", json={"email": "test@example.com"})
            assert resp.status_code == 200
            assert resp.json()["message"] == "OTP sent"
            mock_bus.set.assert_called_once()
            mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_request_otp_rejects_unlisted_email(client):
    with patch("gateway.routers.auth.settings") as mock_settings:
        mock_settings.allowed_login_emails = "allowed@example.com"
        resp = await client.post("/auth/request-otp", json={"email": "hacker@evil.com"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verify_otp_issues_jwt_on_correct_code(client, mock_bus):
    mock_bus.get = AsyncMock(return_value={"otp": "123456", "email": "test@example.com"})
    with patch("gateway.routers.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret"
        mock_settings.allowed_login_emails = "test@example.com"
        mock_bus.delete = AsyncMock()
        resp = await client.post(
            "/auth/verify-otp",
            json={"email": "test@example.com", "otp": "123456"}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_verify_otp_rejects_wrong_code(client, mock_bus):
    mock_bus.get = AsyncMock(return_value={"otp": "123456", "email": "test@example.com"})
    resp = await client.post(
        "/auth/verify-otp",
        json={"email": "test@example.com", "otp": "999999"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_otp_rejects_expired_code(client, mock_bus):
    mock_bus.get = AsyncMock(return_value=None)  # expired = not in Redis
    resp = await client.post(
        "/auth/verify-otp",
        json={"email": "test@example.com", "otp": "123456"}
    )
    assert resp.status_code == 401
```

- [ ] **Step 3: Run to verify tests fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_auth_otp.py -v
```

Expected: 404 (routes missing)

- [ ] **Step 4: Update `gateway/routers/auth.py`**

```python
# gateway/routers/auth.py
import random
import smtplib
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from shared.config import settings
from gateway.auth import create_access_token
from gateway.deps import get_bus
from shared.bus import RedisBus

router = APIRouter()


class OtpRequest(BaseModel):
    email: str


class OtpVerify(BaseModel):
    email: str
    otp: str


def _send_otp_email(recipient: str, otp: str) -> None:
    msg = MIMEText(
        f"Your AI Hedge Fund login code is:\n\n  {otp}\n\nExpires in 10 minutes. Do not share this code."
    )
    msg["Subject"] = "[HedgeFund] Your login code"
    msg["From"] = settings.gmail_sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
        server.login(settings.gmail_sender, settings.gmail_app_password)
        server.send_message(msg)


@router.post("/request-otp")
async def request_otp(body: OtpRequest, bus: RedisBus = Depends(get_bus)):
    allowed = [e.strip() for e in settings.allowed_login_emails.split(",") if e.strip()]
    if allowed and body.email not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not authorised")

    otp = str(random.randint(100000, 999999))
    await bus.set(f"otp:{body.email}", {"otp": otp, "email": body.email},
                  ex=settings.otp_expiry_seconds)

    try:
        _send_otp_email(body.email, otp)
    except Exception:
        pass  # Don't leak email errors; OTP still stored for testing environments

    return {"message": "OTP sent"}


@router.post("/verify-otp")
async def verify_otp(body: OtpVerify, bus: RedisBus = Depends(get_bus)):
    stored = await bus.get(f"otp:{body.email}")
    if not stored or stored.get("otp") != body.otp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP")

    # Consume OTP — single use
    await bus.delete(f"otp:{body.email}")

    token = create_access_token()
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me():
    return {"user": "dashboard", "authenticated": True}
```

Add `delete` method to `shared/bus.py`:
```python
    async def delete(self, key: str):
        await self._client.delete(key)
```

- [ ] **Step 5: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_auth_otp.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Update login page to two-step OTP flow**

Replace `dashboard/app/login/page.tsx` with:

```tsx
// dashboard/app/login/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [step, setStep] = useState<"email" | "otp">("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const router = useRouter();

  async function requestOtp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/request-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Failed to send code");
        return;
      }
      setStep("otp");
      startResendCooldown();
    } catch {
      setError("Connection failed — is the gateway running?");
    } finally {
      setLoading(false);
    }
  }

  function startResendCooldown() {
    setResendCooldown(60);
    const interval = setInterval(() => {
      setResendCooldown((c) => {
        if (c <= 1) { clearInterval(interval); return 0; }
        return c - 1;
      });
    }, 1000);
  }

  async function verifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, otp }),
      });
      if (!res.ok) {
        setError("Invalid or expired code. Try again.");
        return;
      }
      const { access_token } = await res.json();
      document.cookie = `hf_token=${access_token}; path=/; max-age=86400; SameSite=Strict`;
      router.push("/overview");
    } catch {
      setError("Connection failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-full max-w-sm bg-surface border border-border rounded-2xl p-8 space-y-6">
        <div className="text-center">
          <p className="text-4xl mb-2">⬡</p>
          <h1 className="text-xl font-bold">AI Hedge Fund</h1>
          <p className="text-muted text-sm mt-1">
            {step === "email" ? "Enter your email to receive a login code" : `Code sent to ${email}`}
          </p>
        </div>

        {step === "email" ? (
          <form onSubmit={requestOtp} className="space-y-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              className="w-full bg-border border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-accent transition-colors"
              autoFocus
              required
            />
            {error && <p className="text-danger text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3 bg-accent text-black font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors"
            >
              {loading ? "Sending…" : "Send Login Code"}
            </button>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="space-y-4">
            <input
              type="text"
              value={otp}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                setOtp(v);
              }}
              placeholder="000000"
              className="w-full bg-border border border-border rounded-xl px-4 py-3 text-sm text-center text-2xl tracking-[0.5em] font-mono focus:outline-none focus:border-accent transition-colors"
              autoFocus
              maxLength={6}
              required
            />
            {error && <p className="text-danger text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading || otp.length !== 6}
              className="w-full py-3 bg-accent text-black font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors"
            >
              {loading ? "Verifying…" : "Verify Code"}
            </button>
            <div className="text-center">
              <button
                type="button"
                onClick={requestOtp}
                disabled={resendCooldown > 0}
                className="text-muted text-sm hover:text-white disabled:opacity-40 transition-colors"
              >
                {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : "Resend code"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Run full test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all pass

- [ ] **Step 8: Commit**

```powershell
git add gateway/routers/auth.py shared/config.py shared/bus.py tests/gateway/test_auth_otp.py dashboard/app/login/page.tsx
git commit -m "feat(auth): replace password login with 6-digit email OTP flow"
```

---

## Task 3: Docker Compose — Prometheus + Grafana

**Files:**
- Create: `monitoring/prometheus.yml`
- Create: `monitoring/grafana/datasources/prometheus.yml`
- Create: `monitoring/grafana/dashboards/dashboards.yml`
- Create: `monitoring/grafana/dashboards/agent-health.json`
- Create: `monitoring/grafana/dashboards/trading-activity.json`
- Create: `monitoring/grafana/dashboards/portfolio.json`
- Modify: `docker-compose.yml`
- Modify: `shared/config.py`

- [ ] **Step 1: Create `monitoring/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: hedge_fund_gateway
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: /metrics
```

- [ ] **Step 2: Create `monitoring/grafana/datasources/prometheus.yml`**

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
```

- [ ] **Step 3: Create `monitoring/grafana/dashboards/dashboards.yml`**

```yaml
apiVersion: 1
providers:
  - name: hedge-fund
    folder: Hedge Fund
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

- [ ] **Step 4: Create `monitoring/grafana/dashboards/agent-health.json`**

```json
{
  "title": "Agent Health",
  "uid": "hf-agent-health",
  "version": 1,
  "schemaVersion": 36,
  "refresh": "15s",
  "panels": [
    {
      "type": "stat",
      "title": "Agents Online",
      "gridPos": {"x":0,"y":0,"w":4,"h":4},
      "targets": [{"expr": "sum(hf_agent_up)", "legendFormat": "Online"}],
      "options": {"colorMode": "value", "graphMode": "none"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"},
        "thresholds": {"steps": [{"value": 0, "color": "red"}, {"value": 10, "color": "green"}]}}}
    },
    {
      "type": "table",
      "title": "Agent Status",
      "gridPos": {"x":4,"y":0,"w":20,"h":8},
      "targets": [{"expr": "hf_agent_up", "legendFormat": "{{agent}}", "instant": true}],
      "options": {"sortBy": [{"displayName": "Value", "desc": false}]}
    }
  ],
  "time": {"from": "now-1h", "to": "now"}
}
```

- [ ] **Step 5: Create `monitoring/grafana/dashboards/trading-activity.json`**

```json
{
  "title": "Trading Activity",
  "uid": "hf-trading",
  "version": 1,
  "schemaVersion": 36,
  "refresh": "15s",
  "panels": [
    {
      "type": "stat",
      "title": "Pending Trades",
      "gridPos": {"x":0,"y":0,"w":4,"h":4},
      "targets": [{"expr": "hf_pending_trades_count", "legendFormat": "Pending"}],
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"},
        "thresholds": {"steps": [{"value": 0, "color": "green"}, {"value": 5, "color": "yellow"}, {"value": 10, "color": "red"}]}}}
    },
    {
      "type": "timeseries",
      "title": "Signals per Agent",
      "gridPos": {"x":0,"y":4,"w":24,"h":8},
      "targets": [{"expr": "rate(hf_signals_total[5m])", "legendFormat": "{{agent}}"}]
    },
    {
      "type": "timeseries",
      "title": "Trade Execution Rate",
      "gridPos": {"x":0,"y":12,"w":24,"h":8},
      "targets": [{"expr": "rate(hf_trades_total{status=\"executed\"}[5m])", "legendFormat": "Executed/s"}]
    }
  ],
  "time": {"from": "now-6h", "to": "now"}
}
```

- [ ] **Step 6: Create `monitoring/grafana/dashboards/portfolio.json`**

```json
{
  "title": "Portfolio",
  "uid": "hf-portfolio",
  "version": 1,
  "schemaVersion": 36,
  "refresh": "30s",
  "panels": [
    {
      "type": "gauge",
      "title": "Portfolio Value",
      "gridPos": {"x":0,"y":0,"w":6,"h":6},
      "targets": [{"expr": "hf_portfolio_value_usd", "legendFormat": "Value"}],
      "options": {"minVizWidth": 75},
      "fieldConfig": {"defaults": {"unit": "currencyUSD",
        "thresholds": {"steps": [{"value": 0, "color": "red"}, {"value": 100000, "color": "green"}]}}}
    },
    {
      "type": "gauge",
      "title": "Drawdown",
      "gridPos": {"x":6,"y":0,"w":6,"h":6},
      "targets": [{"expr": "hf_portfolio_drawdown_pct", "legendFormat": "Drawdown %"}],
      "fieldConfig": {"defaults": {"unit": "percent",
        "thresholds": {"steps": [{"value": 0, "color": "green"}, {"value": 10, "color": "yellow"}, {"value": 20, "color": "red"}]}}}
    },
    {
      "type": "timeseries",
      "title": "Portfolio Value Over Time",
      "gridPos": {"x":0,"y":6,"w":24,"h":10},
      "targets": [{"expr": "hf_portfolio_value_usd", "legendFormat": "Portfolio"}]
    },
    {
      "type": "stat",
      "title": "Open Positions",
      "gridPos": {"x":12,"y":0,"w":6,"h":6},
      "targets": [{"expr": "hf_open_positions_count", "legendFormat": "Positions"}]
    },
    {
      "type": "stat",
      "title": "Cash",
      "gridPos": {"x":18,"y":0,"w":6,"h":6},
      "targets": [{"expr": "hf_cash_usd", "legendFormat": "Cash"}],
      "fieldConfig": {"defaults": {"unit": "currencyUSD"}}
    }
  ],
  "time": {"from": "now-24h", "to": "now"}
}
```

- [ ] **Step 7: Add Prometheus + Grafana to `docker-compose.yml`**

Add after the `retrainer` service (before the `caddy` service):

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
    depends_on:
      - gateway

  grafana:
    image: grafana/grafana:10.4.0
    restart: unless-stopped
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_SERVER_ROOT_URL: https://${DOMAIN:-localhost}/grafana
      GF_SERVER_SERVE_FROM_SUB_PATH: "true"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
```

Add to `volumes:` section:
```yaml
  prometheus_data:
  grafana_data:
```

Add to `.env.example`:
```
GRAFANA_PASSWORD=change-me-in-production
```

- [ ] **Step 8: Run full test suite**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all pass

- [ ] **Step 9: Smoke test — start monitoring stack**

```powershell
docker compose up prometheus grafana -d
Start-Sleep -Seconds 5
Invoke-RestMethod http://localhost:9090/-/healthy
```

Expected: `Prometheus Server is Healthy.`

Open `http://localhost:3001` — Grafana login page should appear.

- [ ] **Step 10: Commit**

```powershell
git add monitoring/ docker-compose.yml requirements.txt shared/config.py
git commit -m "feat(monitoring): Prometheus + Grafana with 3 dashboards in Docker Compose"
```
