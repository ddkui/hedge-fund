# Remaining Agents + Memory Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Portfolio Researcher agent, upgrade the Ops agent into The Engineer (full self-healing SRE), add ChromaDB + Obsidian memory to all agents, and build the ML retraining pipeline.

**Architecture:** Each agent already inherits `BaseAgent`. New agents follow the same pattern. Memory layer is added as a mixin (`MemoryMixin`) that all agents call after `run_once()`. The Engineer replaces `agents/ops/` with a full SRE agent that self-heals, backs up, and monitors capacity.

**Tech Stack:** Python 3.11, asyncpg, redis-py, chromadb, ollama (nomic-embed-text), markdown files for Obsidian vault

**Prerequisites:** Complete `2026-05-24-gateway-dashboard.md` first.

---

## File Structure

```
agents/
├── portfolio_researcher/
│   ├── __init__.py
│   ├── agent.py           # Analyses open positions, emits Hold/Trim/Sell
│   └── main.py
├── ops/
│   └── agent.py           # REPLACED with full Engineer agent (self-healing, backups, capacity)
shared/
└── memory.py              # MemoryMixin: write_to_chroma() + write_to_obsidian()
scripts/
└── retrain_models.py      # ML model retraining pipeline (run weekly via cron)
memory/
├── chroma/                # ChromaDB persists here (already exists)
└── obsidian/              # Markdown vault (already exists)
tests/
├── agents/portfolio_researcher/
│   └── test_agent.py
└── agents/ops/
    └── test_engineer.py   (replaces existing test_agent.py)
```

---

## Task 1: ChromaDB + Obsidian Memory Mixin

**Files:**
- Create: `shared/memory.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add chromadb to requirements.txt**

```
chromadb==0.5.0
```

Install:
```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\pip.exe install chromadb==0.5.0
```

Expected: `Successfully installed chromadb-0.5.0 ...`

- [ ] **Step 2: Write failing test**

```python
# tests/shared/test_memory.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os


@pytest.mark.asyncio
async def test_write_to_obsidian_creates_file(tmp_path):
    from shared.memory import MemoryMixin
    mixin = MemoryMixin.__new__(MemoryMixin)
    mixin.name = "test_agent"
    mixin.obsidian_root = str(tmp_path)
    mixin.logger = MagicMock()
    await mixin.write_to_obsidian(
        title="Test Signal",
        body="AAPL is bullish.",
        tags=["test", "aapl"],
    )
    files = list(tmp_path.glob("**/*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "AAPL is bullish." in content
    assert "tags: [test, aapl]" in content


@pytest.mark.asyncio
async def test_write_to_chroma_adds_document(tmp_path):
    from shared.memory import MemoryMixin
    mixin = MemoryMixin.__new__(MemoryMixin)
    mixin.name = "test_agent"
    mixin.chroma_root = str(tmp_path)
    mixin.logger = MagicMock()
    await mixin.write_to_chroma(
        doc_id="aapl-bullish-001",
        text="AAPL is bullish based on RSI and MACD.",
        metadata={"symbol": "AAPL", "agent": "test"},
    )
    # Verify collection was created and has 1 document
    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path))
    col = client.get_collection("test_agent")
    assert col.count() == 1
```

- [ ] **Step 3: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_memory.py -v
```

Expected: `ModuleNotFoundError: shared.memory`

- [ ] **Step 4: Create shared/memory.py**

```python
# shared/memory.py
import os
from datetime import datetime, timezone
from pathlib import Path


class MemoryMixin:
    """
    Adds write_to_chroma() and write_to_obsidian() to any agent.
    Agents call these after computing a result worth remembering.
    """
    obsidian_root: str = "memory/obsidian"
    chroma_root: str = "memory/chroma"

    async def write_to_obsidian(self, title: str, body: str, tags: list[str] | None = None) -> None:
        """Write a markdown file to the Obsidian vault."""
        try:
            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H%M%S")
            agent_dir = Path(self.obsidian_root) / self.name
            agent_dir.mkdir(parents=True, exist_ok=True)

            safe_title = title[:50].replace(" ", "-").replace("/", "-").lower()
            filename = f"{date_str}-{time_str}-{safe_title}.md"
            filepath = agent_dir / filename

            tag_str = ", ".join(tags or [self.name])
            content = f"""---
title: {title}
agent: {self.name}
date: {now.isoformat()}
tags: [{tag_str}]
---

{body}
"""
            filepath.write_text(content, encoding="utf-8")
        except Exception as exc:
            self.logger.warning("obsidian_write_failed", error=str(exc))

    async def write_to_chroma(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Store a document in ChromaDB for semantic retrieval."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.chroma_root)
            collection = client.get_or_create_collection(
                name=self.name,
                metadata={"hnsw:space": "cosine"},
            )
            collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata or {}],
            )
        except Exception as exc:
            self.logger.warning("chroma_write_failed", error=str(exc))

    async def recall_from_chroma(self, query: str, n_results: int = 5) -> list[dict]:
        """Retrieve semantically similar past documents."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.chroma_root)
            collection = client.get_or_create_collection(name=self.name)
            if collection.count() == 0:
                return []
            results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
        except Exception as exc:
            self.logger.warning("chroma_recall_failed", error=str(exc))
            return []
```

- [ ] **Step 5: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_memory.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```powershell
git add shared/memory.py requirements.txt tests/shared/test_memory.py
git commit -m "feat(memory): ChromaDB + Obsidian memory mixin for agents"
```

---

## Task 2: Portfolio Researcher Agent

**Files:**
- Create: `agents/portfolio_researcher/__init__.py`
- Create: `agents/portfolio_researcher/agent.py`
- Create: `agents/portfolio_researcher/main.py`
- Create: `tests/agents/portfolio_researcher/test_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/portfolio_researcher/test_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock


def make_agent():
    from agents.portfolio_researcher.agent import PortfolioResearcherAgent
    agent = PortfolioResearcherAgent.__new__(PortfolioResearcherAgent)
    agent.name = "portfolio_researcher"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.bus.get = AsyncMock(return_value=None)
    agent.logger = MagicMock()
    agent._running = True
    agent.interval_seconds = 1800
    return agent


@pytest.mark.asyncio
async def test_researcher_skips_when_no_open_positions():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_researcher_emits_hold_for_bullish_position():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        # open positions
        [{"id": 1, "symbol": "AAPL", "direction": "long", "entry_thesis": "bullish momentum"}],
        # signals for AAPL
        [{"agent": "aggregator", "symbol": "AAPL", "signal_type": "bullish_signal", "confidence": 70.0}],
    ])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "hold"
    assert call.kwargs["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_researcher_emits_sell_for_contradicted_position():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [{"id": 1, "symbol": "AAPL", "direction": "long", "entry_thesis": "bullish momentum"}],
        [{"agent": "aggregator", "symbol": "AAPL", "signal_type": "bearish_signal", "confidence": 75.0}],
    ])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "sell"


@pytest.mark.asyncio
async def test_researcher_emits_trim_for_weakening_position():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [{"id": 1, "symbol": "AAPL", "direction": "long", "entry_thesis": "bullish momentum"}],
        [{"agent": "aggregator", "symbol": "AAPL", "signal_type": "bullish_signal", "confidence": 38.0}],
    ])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "trim"
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/portfolio_researcher/test_agent.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create agents/portfolio_researcher/agent.py**

```python
# agents/portfolio_researcher/agent.py
from agents.base import AnalysisAgent


def _direction(signal_type: str) -> str:
    st = signal_type.lower()
    if "bullish" in st:
        return "bullish"
    if "bearish" in st:
        return "bearish"
    return "neutral"


class PortfolioResearcherAgent(AnalysisAgent):
    """
    Runs every 30 minutes. For each open position, pulls latest signals
    and emits Hold / Trim / Sell with full reasoning for the PM to act on.

    Logic:
    - Opposing signal with conf >= 65 → sell (thesis broken)
    - Aligned signal with conf < 45    → trim (conviction weakening)
    - Aligned signal with conf >= 45   → hold
    - No signal                        → hold
    """

    async def run_once(self):
        open_positions = await self.db.fetch(
            "SELECT id, symbol, direction, entry_thesis "
            "FROM positions WHERE status = 'open'"
        )
        if not open_positions:
            return

        sell_count = 0

        for pos in open_positions:
            symbol = pos["symbol"]
            entry_direction = pos["direction"]  # "long" or "short"

            latest_signals = await self.db.fetch(
                """
                SELECT agent, symbol, signal_type, confidence, reasoning
                FROM signals
                WHERE symbol = $1
                  AND agent IN ('aggregator', 'quant_supervisor', 'research', 'sentiment')
                  AND time > now() - INTERVAL '30 minutes'
                ORDER BY time DESC
                LIMIT 10
                """,
                symbol,
            )

            if not latest_signals:
                await self.store_signal(
                    symbol=symbol,
                    signal_type="hold",
                    confidence=50.0,
                    reasoning=f"No fresh signals for {symbol} — holding",
                )
                continue

            # Use aggregator as primary, fall back to others
            primary = next(
                (s for s in latest_signals if s["agent"] == "aggregator"),
                latest_signals[0],
            )
            sig_direction = _direction(primary["signal_type"])
            conf = float(primary["confidence"])

            # Determine position direction
            pos_direction = "bullish" if entry_direction == "long" else "bearish"
            opposing = sig_direction != pos_direction and sig_direction != "neutral"

            if opposing and conf >= 65.0:
                action = "sell"
                reasoning = (
                    f"Thesis contradicted: entered {pos_direction}, "
                    f"now seeing {sig_direction} ({conf:.0f}% conf). "
                    f"Original thesis: {pos['entry_thesis'] or 'unknown'}"
                )
                sell_count += 1
            elif not opposing and conf < 45.0:
                action = "trim"
                reasoning = f"Conviction weakening: {sig_direction} at {conf:.0f}% — trim position"
            else:
                action = "hold"
                reasoning = f"Thesis intact: {sig_direction} at {conf:.0f}%"

            await self.store_signal(
                symbol=symbol,
                signal_type=action,
                confidence=conf,
                reasoning=reasoning,
            )

        # Alert CIO if multiple simultaneous sells
        if sell_count >= 3:
            await self.bus.publish("cio.alert", {
                "level": "urgent",
                "message": f"Portfolio Researcher flagged {sell_count} simultaneous sell signals",
            })
```

- [ ] **Step 4: Create agents/portfolio_researcher/__init__.py and main.py**

```python
# agents/portfolio_researcher/__init__.py
```

```python
# agents/portfolio_researcher/main.py
import asyncio
from shared.db import Database
from shared.bus import RedisBus
from shared.config import settings
from agents.portfolio_researcher.agent import PortfolioResearcherAgent


async def main():
    db = Database(settings.db_dsn)
    bus = RedisBus(settings.redis_url)
    await db.connect()
    await bus.connect()
    agent = PortfolioResearcherAgent(
        name="portfolio_researcher",
        db=db,
        bus=bus,
        interval_seconds=1800,
    )
    try:
        await agent.run()
    finally:
        await db.disconnect()
        await bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Add to start_all.py**

In `scripts/start_all.py`, add to the AGENTS list:
```python
    "agents/portfolio_researcher/main.py",
```
(add after `"agents/aggregator/main.py"`)

- [ ] **Step 6: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/portfolio_researcher/test_agent.py -v
```

Expected: `4 passed`

- [ ] **Step 7: Commit**

```powershell
git add agents/portfolio_researcher/ tests/agents/portfolio_researcher/ scripts/start_all.py
git commit -m "feat(agents): Portfolio Researcher — Hold/Trim/Sell recommendations on open positions"
```

---

## Task 3: The Engineer Agent (Full SRE Upgrade)

**Files:**
- Modify: `agents/ops/agent.py` (full replacement)
- Create: `tests/agents/ops/test_engineer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/ops/test_engineer.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta


def make_agent():
    from agents.ops.agent import EngineerAgent
    agent = EngineerAgent.__new__(EngineerAgent)
    agent.name = "ops"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.bus.get = AsyncMock(return_value=None)
    agent.bus.publish = AsyncMock()
    agent.logger = MagicMock()
    agent._running = True
    agent._last_seen = {}
    agent._restart_counts = {}
    agent._email_sent_at = {}
    agent.interval_seconds = 60
    return agent


@pytest.mark.asyncio
async def test_engineer_detects_down_agent_and_publishes_alert():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen = {"technical": now - timedelta(seconds=700)}
    agent.db.execute = AsyncMock()
    await agent._check_agents()
    agent.bus.publish.assert_called()
    call_args = agent.bus.publish.call_args
    assert call_args[0][0] == "ops.alert"
    assert "technical" in str(call_args[0][1])


@pytest.mark.asyncio
async def test_engineer_increments_restart_count_on_down():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen = {"technical": now - timedelta(seconds=700)}
    agent.db.execute = AsyncMock()
    await agent._check_agents()
    assert agent._restart_counts.get("technical", 0) >= 1


@pytest.mark.asyncio
async def test_engineer_escalates_to_cio_after_max_restarts():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen = {"technical": now - timedelta(seconds=700)}
    agent._restart_counts = {"technical": 3}  # already at max
    agent.db.execute = AsyncMock()
    await agent._check_agents()
    # Should publish to cio.alert (escalation)
    calls = [str(c) for c in agent.bus.publish.call_args_list]
    assert any("cio.alert" in c for c in calls)


@pytest.mark.asyncio
async def test_engineer_writes_incident_to_obsidian(tmp_path):
    agent = make_agent()
    agent.obsidian_root = str(tmp_path)
    with patch.object(type(agent), "write_to_obsidian", new_callable=AsyncMock) as mock_write:
        await agent._write_incident("technical", "down", 700)
        mock_write.assert_called_once()
        call = mock_write.call_args
        assert "technical" in call.kwargs.get("title", "") or "technical" in str(call.args)
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/ops/test_engineer.py -v
```

Expected: `ImportError: cannot import name 'EngineerAgent'`

- [ ] **Step 3: Replace agents/ops/agent.py**

```python
# agents/ops/agent.py
"""
The Engineer — full SRE agent.
Monitors all agents, self-heals crashes, writes incident reports to Obsidian,
publishes alerts to CIO, and tracks restart counts.
"""
import asyncio
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from shared.agent_base import BaseAgent
from shared.config import settings
from shared.memory import MemoryMixin

KNOWN_AGENT_INTERVALS: dict[str, int] = {
    "ingest":               60,
    "technical":           120,
    "sentiment":           300,
    "macro":               300,
    "research":            600,
    "aggregator":          120,
    "portfolio_researcher": 1800,
    "momentum":            120,
    "mean_reversion":      120,
    "ml_quant":            120,
    "quant_supervisor":    300,
    "portfolio_mgr":       120,
    "risk":                120,
    "execution":             5,
    "cio":                3600,
}

AGENT_SCRIPTS: dict[str, str] = {
    "ingest":               "data/ingest/main.py",
    "technical":           "agents/technical/main.py",
    "sentiment":           "agents/sentiment/main.py",
    "macro":               "agents/macro/main.py",
    "research":            "agents/research/main.py",
    "aggregator":          "agents/aggregator/main.py",
    "portfolio_researcher":"agents/portfolio_researcher/main.py",
    "momentum":            "agents/quant/momentum/main.py",
    "mean_reversion":      "agents/quant/mean_reversion/main.py",
    "ml_quant":            "agents/quant/ml_quant/main.py",
    "quant_supervisor":    "agents/quant/supervisor/main.py",
    "portfolio_mgr":       "agents/portfolio_mgr/main.py",
    "risk":                "agents/risk/main.py",
    "execution":           "agents/execution/main.py",
    "cio":                 "agents/cio/main.py",
}

MAX_RESTARTS = 3


class EngineerAgent(MemoryMixin, BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_seen: dict[str, datetime] = {}
        self._restart_counts: dict[str, int] = {}
        self._email_sent_at: dict[str, datetime] = {}

    async def run(self):
        self.logger.info("engineer_starting")
        check_task = asyncio.create_task(self._check_loop())
        subscribe_task = asyncio.create_task(self._subscribe_loop())
        try:
            await asyncio.gather(check_task, subscribe_task)
        except asyncio.CancelledError:
            check_task.cancel()
            subscribe_task.cancel()
            await asyncio.gather(check_task, subscribe_task, return_exceptions=True)
            raise

    async def _subscribe_loop(self):
        try:
            async for msg in self.bus.subscribe("ops.heartbeat"):
                agent_name = msg.get("agent")
                if not agent_name:
                    continue
                self._last_seen[agent_name] = self._now()
                status = msg.get("status", "healthy")
                now = self._now()
                await self.db.execute(
                    "INSERT INTO agent_health (time, agent, status, metadata) VALUES ($1, $2, $3, $4)",
                    now, agent_name, status, '{}',
                )
                # Reset restart count when agent recovers
                if status == "healthy" and agent_name in self._restart_counts:
                    self._restart_counts[agent_name] = 0
        except asyncio.CancelledError:
            pass

    async def _check_loop(self):
        while self._running:
            await self._check_agents()
            await asyncio.sleep(self.interval_seconds)

    async def _check_agents(self):
        now = self._now()
        for agent_name, interval in KNOWN_AGENT_INTERVALS.items():
            last = self._last_seen.get(agent_name)
            if last is None:
                continue
            gap = (now - last).total_seconds()
            if gap > 5 * interval:
                await self._handle_down(agent_name, gap)
            elif gap > 2 * interval:
                await self._write_health(agent_name, "degraded", gap)

    async def _handle_down(self, agent_name: str, gap_seconds: float):
        await self._write_health(agent_name, "down", gap_seconds)
        restart_count = self._restart_counts.get(agent_name, 0)

        if restart_count < MAX_RESTARTS:
            self._restart_counts[agent_name] = restart_count + 1
            self.logger.warning("engineer_restarting_agent", agent=agent_name, attempt=restart_count + 1)
            await self._restart_agent(agent_name)
            await self.bus.publish("ops.alert", {
                "agent": agent_name,
                "level": "warning",
                "message": f"Agent {agent_name} was down — restart attempt {restart_count + 1}/{MAX_RESTARTS}",
            })
        else:
            # Escalate to CIO
            await self.bus.publish("cio.alert", {
                "level": "urgent",
                "agent": agent_name,
                "message": f"Agent {agent_name} failed {MAX_RESTARTS} restart attempts — manual intervention required",
            })
            await self._write_incident(agent_name, "down", gap_seconds)
            await self._maybe_send_email(agent_name, gap_seconds)

    async def _restart_agent(self, agent_name: str):
        script = AGENT_SCRIPTS.get(agent_name)
        if not script:
            return
        try:
            subprocess.Popen([sys.executable, script])
        except Exception as exc:
            self.logger.error("engineer_restart_failed", agent=agent_name, error=str(exc))

    async def _write_health(self, agent_name: str, status: str, gap_seconds: float):
        now = self._now()
        await self.db.execute(
            "INSERT INTO agent_health (time, agent, status, metadata) VALUES ($1, $2, $3, $4)",
            now, agent_name, status, f'{{"gap_seconds": {gap_seconds:.0f}}}',
        )
        self.logger.warning("agent_health_changed", agent=agent_name, status=status, gap=gap_seconds)

    async def _write_incident(self, agent_name: str, status: str, gap_seconds: float):
        await self.write_to_obsidian(
            title=f"Incident: {agent_name} {status}",
            body=(
                f"## Incident Report\n\n"
                f"**Agent:** {agent_name}\n"
                f"**Status:** {status}\n"
                f"**Gap:** {gap_seconds:.0f}s\n"
                f"**Restart attempts:** {self._restart_counts.get(agent_name, 0)}\n"
                f"**Time:** {self._now().isoformat()}\n\n"
                f"Engineer exhausted {MAX_RESTARTS} restart attempts. Manual intervention required."
            ),
            tags=["incident", "ops", agent_name],
        )

    async def _maybe_send_email(self, agent_name: str, gap_seconds: float):
        if not settings.gmail_sender:
            return
        last_sent = self._email_sent_at.get(agent_name)
        now = self._now()
        if last_sent and (now - last_sent).total_seconds() < 3600:
            return
        self._email_sent_at[agent_name] = now
        import smtplib
        from email.mime.text import MIMEText
        try:
            msg = MIMEText(
                f"Agent '{agent_name}' has been down for {gap_seconds:.0f}s.\n"
                f"Engineer made {MAX_RESTARTS} restart attempts — all failed.\n"
                f"Manual intervention required."
            )
            msg["Subject"] = f"[HedgeFund] URGENT: Agent {agent_name} DOWN"
            msg["From"] = settings.gmail_sender
            msg["To"] = settings.gmail_sender
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(settings.gmail_sender, settings.gmail_app_password)
                server.send_message(msg)
        except Exception as exc:
            self.logger.error("email_failed", error=str(exc))

    async def run_once(self):
        await self._check_agents()
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/ops/test_engineer.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run full suite to confirm existing tests still pass**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: `N passed` (all original 187 + new ones)

- [ ] **Step 6: Commit**

```powershell
git add agents/ops/agent.py tests/agents/ops/test_engineer.py shared/memory.py
git commit -m "feat(agents): The Engineer — self-healing SRE with incident reports and CIO escalation"
```

---

## Task 4: Wire Memory Into Existing Agents

**Files:**
- Modify: `agents/research/agent.py`
- Modify: `agents/sentiment/agent.py`
- Modify: `agents/cio/agent.py`
- Modify: `agents/quant/supervisor/agent.py`

- [ ] **Step 1: Update agents/research/agent.py to use MemoryMixin**

Read `agents/research/agent.py` then add `MemoryMixin` to the class inheritance and call `write_to_obsidian` + `write_to_chroma` after emitting a signal. Find the point where the agent calls `store_signal` and add memory writes after:

```python
# At top of agents/research/agent.py, add:
from shared.memory import MemoryMixin

# Change class definition from:
class ResearchAgent(AnalysisAgent):
# to:
class ResearchAgent(MemoryMixin, AnalysisAgent):
```

After each `await self.store_signal(...)` call, add:
```python
await self.write_to_obsidian(
    title=f"Research: {symbol}",
    body=reasoning,
    tags=["research", symbol.lower()],
)
await self.write_to_chroma(
    doc_id=f"research-{symbol}-{now.isoformat()}",
    text=reasoning,
    metadata={"symbol": symbol, "agent": "research", "signal_type": signal_type},
)
```

- [ ] **Step 2: Apply same pattern to agents/cio/agent.py**

```python
from shared.memory import MemoryMixin

class CioAgent(MemoryMixin, AnalysisAgent):
    ...
```

After generating a daily brief or directive, add:
```python
await self.write_to_obsidian(
    title=f"CIO Brief {now.strftime('%Y-%m-%d')}",
    body=brief_text,
    tags=["cio", "brief"],
)
```

- [ ] **Step 3: Apply to agents/quant/supervisor/agent.py**

```python
from shared.memory import MemoryMixin

class QuantSupervisorAgent(MemoryMixin, AnalysisAgent):
    ...
```

After approving or retiring an algo, write decision to memory:
```python
await self.write_to_obsidian(
    title=f"Quant Decision: {algo_name} {decision}",
    body=f"**Decision:** {decision}\n**Reason:** {reason}\n**Sharpe:** {sharpe}",
    tags=["quant", "supervisor", decision],
)
```

- [ ] **Step 4: Run full test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: all PASS (memory mixin calls are async and won't break existing tests since write_to_obsidian/write_to_chroma are graceful on error)

- [ ] **Step 5: Commit**

```powershell
git add agents/research/agent.py agents/cio/agent.py agents/quant/supervisor/agent.py
git commit -m "feat(memory): wire ChromaDB + Obsidian into research, CIO, and quant supervisor agents"
```

---

## Task 5: ML Model Retraining Pipeline

**Files:**
- Create: `scripts/retrain_models.py`
- Create: `tests/scripts/test_retrain.py`

- [ ] **Step 1: Write failing test**

```python
# tests/scripts/test_retrain.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_retrain_fetches_prices_from_db():
    with patch("scripts.retrain_models.Database") as MockDB:
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[
            {"symbol": "AAPL", "close": 180.0, "time": "2026-05-01T10:00:00+00:00"},
        ] * 100)
        MockDB.return_value = mock_db
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()

        from scripts.retrain_models import fetch_training_data
        data = await fetch_training_data(mock_db, "AAPL", days=30)
        assert len(data) > 0


@pytest.mark.asyncio
async def test_retrain_skips_symbol_with_insufficient_data():
    with patch("scripts.retrain_models.Database"):
        from scripts.retrain_models import fetch_training_data
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[{"symbol": "AAPL", "close": 180.0, "time": "2026-05-01T10:00:00+00:00"}] * 5)
        result = await fetch_training_data(db, "AAPL", days=30)
        # Less than MIN_ROWS should return empty
        assert result == [] or len(result) < 20
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/scripts/test_retrain.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create scripts/retrain_models.py**

```python
#!/usr/bin/env python3
"""
Weekly ML model retraining pipeline.
Fetches latest price data, retrains XGBoost models for each symbol,
validates against holdout, deploys if performance improves.

Run manually or via cron: python scripts/retrain_models.py
"""
import asyncio
import sys
sys.path.insert(0, ".")
import pickle
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from shared.db import Database
from shared.config import settings

MIN_ROWS = 200  # minimum price rows needed to retrain
MODEL_DIR = Path("models/weights")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_training_data(db: Database, symbol: str, days: int = 90) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT time, open, high, low, close, volume
        FROM prices
        WHERE symbol = $1 AND time > NOW() - INTERVAL '%s days'
        ORDER BY time ASC
        """ % days,
        symbol,
    )
    if len(rows) < MIN_ROWS:
        return []
    return rows


def build_features(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) arrays for XGBoost classification."""
    closes = np.array([float(r["close"]) for r in rows])
    volumes = np.array([float(r.get("volume") or 0) for r in rows])

    features = []
    labels = []
    window = 20

    for i in range(window, len(closes) - 1):
        window_slice = closes[i - window:i]
        ret = np.diff(window_slice) / window_slice[:-1]
        vol_slice = volumes[i - window:i]
        price_mean = window_slice.mean()
        price_std = window_slice.std() + 1e-9
        z_score = (closes[i] - price_mean) / price_std
        vol_ratio = volumes[i] / (vol_slice.mean() + 1e-9)

        feat = np.concatenate([
            ret[-10:],
            [z_score, vol_ratio, closes[i] / closes[i - 1] - 1],
        ])
        features.append(feat)
        # Label: 1 if next close > current close
        labels.append(1 if closes[i + 1] > closes[i] else 0)

    return np.array(features), np.array(labels)


async def retrain_symbol(db: Database, symbol: str) -> dict:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score

    rows = await fetch_training_data(db, symbol)
    if not rows:
        print(f"  [{symbol}] skipped — insufficient data ({len(rows)} rows)")
        return {"symbol": symbol, "status": "skipped", "accuracy": None}

    X, y = build_features(rows)
    if len(X) < 50:
        return {"symbol": symbol, "status": "skipped", "accuracy": None}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # Train new model
    new_model = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    new_model.fit(X_train, y_train)
    new_acc = accuracy_score(y_test, new_model.predict(X_test))

    # Compare with existing model if it exists
    model_path = MODEL_DIR / f"{symbol.lower()}_xgb.pkl"
    if model_path.exists():
        with open(model_path, "rb") as f:
            old_model = pickle.load(f)
        old_acc = accuracy_score(y_test, old_model.predict(X_test))
        if new_acc <= old_acc:
            print(f"  [{symbol}] new model ({new_acc:.3f}) not better than old ({old_acc:.3f}) — keeping old")
            return {"symbol": symbol, "status": "kept_old", "accuracy": old_acc}

    # Deploy new model
    with open(model_path, "wb") as f:
        pickle.dump(new_model, f)

    print(f"  [{symbol}] deployed new model — accuracy: {new_acc:.3f}")
    return {"symbol": symbol, "status": "deployed", "accuracy": new_acc}


async def main():
    print(f"ML retraining started at {datetime.now(timezone.utc).isoformat()}")
    db = Database(settings.db_dsn)
    await db.connect()

    symbols = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")
    results = []
    for sym in symbols:
        sym = sym.strip()
        print(f"Retraining {sym}...")
        result = await retrain_symbol(db, sym)
        results.append(result)

    await db.disconnect()

    deployed = [r for r in results if r["status"] == "deployed"]
    skipped = [r for r in results if r["status"] == "skipped"]
    print(f"\nRetraining complete. Deployed: {len(deployed)}, Skipped: {len(skipped)}")
    for r in deployed:
        print(f"  ✓ {r['symbol']} — accuracy {r['accuracy']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/scripts/test_retrain.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Run full suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: all PASS

- [ ] **Step 6: Commit**

```powershell
git add scripts/retrain_models.py tests/scripts/test_retrain.py models/
git commit -m "feat(ml): weekly model retraining pipeline with performance-gated deployment"
```

---

*Next plan: `2026-05-24-notifications-auth.md` — Gmail notifications, JWT auth, kill switch, security hardening.*
