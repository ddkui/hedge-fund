# Researcher Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement two daily-running researcher agents that fetch academic papers from arXiv/SSRN, score them for relevance/impact, and generate trading signals (supervisor) or GitHub issues (maintainer).

**Architecture:** Supervisor researcher fetches quant strategy papers, scores by relevance to current strategies, generates draft signals fed to aggregator. Maintainer researcher fetches system improvement papers, scores by impact/feasibility, creates GitHub issues. Both store findings in database and send daily Slack digests.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, arXiv API, SSRN API, sentence-transformers, APScheduler, Slack SDK, PyGithub, pytest

---

## File Structure Overview

```
agents/
├── supervisor_researcher/
│   ├── __init__.py
│   ├── main.py                     # APScheduler entry point
│   ├── agent.py                    # Core orchestration logic
│   ├── paper_fetcher.py            # Query arXiv/SSRN
│   ├── scorer.py                   # Relevance/academic scoring
│   ├── signal_generator.py         # Create draft signals
│   ├── models.py                   # Pydantic models
│   └── requirements.txt
├── maintainer_researcher/
│   ├── __init__.py
│   ├── main.py                     # APScheduler entry point
│   ├── agent.py                    # Core orchestration logic
│   ├── paper_fetcher.py            # Query arXiv/SSRN
│   ├── issue_generator.py          # Create GitHub issues
│   ├── scorer.py                   # Impact/feasibility scoring
│   ├── models.py                   # Pydantic models
│   └── requirements.txt

shared/
├── academic_research.py            # DB models + helpers
├── system_improvements.py          # DB models + helpers
└── slack_notifier.py               # Shared Slack utilities

gateway/routers/
├── research.py                     # Research API endpoints

tests/
├── agents/supervisor_researcher/
│   ├── test_paper_fetcher.py
│   ├── test_scorer.py
│   ├── test_signal_generator.py
│   └── test_agent.py
├── agents/maintainer_researcher/
│   ├── test_paper_fetcher.py
│   ├── test_scorer.py
│   ├── test_issue_generator.py
│   └── test_agent.py
└── integration/test_researchers.py
```

---

### Task 1: Database Models (academic_research, system_improvements)

**Files:**
- Create: `shared/academic_research.py`
- Create: `shared/system_improvements.py`
- Create: `tests/shared/test_academic_research.py`
- Create: `tests/shared/test_system_improvements.py`

- [ ] **Step 1: Write failing test for academic_research model**

```python
# tests/shared/test_academic_research.py
import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from shared.academic_research import AcademicResearch, add_research_record
from gateway.database import Base, engine

def test_add_academic_research_record():
    """Test adding an academic research record to database."""
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        record = add_research_record(
            session=session,
            source="arxiv",
            paper_id="2406.12345",
            title="Machine Learning for Momentum Trading",
            authors="Smith, J.; Jones, K.",
            abstract="We propose a deep learning approach...",
            url="https://arxiv.org/abs/2406.12345",
            publication_date=datetime(2026, 6, 7).date(),
            relevance_score=82.5,
            academic_score=78.0,
            confidence_score=80.3,
            strategy_tags="momentum,ml",
            generated_signal_id=None
        )
        
        assert record.id is not None
        assert record.source == "arxiv"
        assert record.relevance_score == 82.5
        assert record.slack_alert_sent is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:\Users\jomik\hedge-fund
pytest tests/shared/test_academic_research.py::test_add_academic_research_record -v
```

Expected: `FAILED - ModuleNotFoundError: No module named 'shared.academic_research'`

- [ ] **Step 3: Create academic_research.py model**

```python
# shared/academic_research.py
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()

class AcademicResearch(Base):
    """Academic research paper record with scoring and signal generation."""
    __tablename__ = "academic_research"
    
    id = Column(Integer, primary_key=True)
    date_discovered = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), nullable=False)
    paper_id = Column(String(100), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=False)
    abstract = Column(Text, nullable=False)
    url = Column(String(500), nullable=False)
    publication_date = Column(Date, nullable=False)
    relevance_score = Column(Float, nullable=False)
    academic_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    strategy_tags = Column(String(200))
    generated_signal_id = Column(Integer)
    slack_alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def add_research_record(
    session: Session,
    source: str,
    paper_id: str,
    title: str,
    authors: str,
    abstract: str,
    url: str,
    publication_date: date,
    relevance_score: float,
    academic_score: float,
    confidence_score: float,
    strategy_tags: str = None,
    generated_signal_id: int = None
) -> AcademicResearch:
    """Add a research record to the database."""
    record = AcademicResearch(
        source=source,
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        publication_date=publication_date,
        relevance_score=relevance_score,
        academic_score=academic_score,
        confidence_score=confidence_score,
        strategy_tags=strategy_tags,
        generated_signal_id=generated_signal_id
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record

def mark_slack_alert_sent(session: Session, record_id: int) -> AcademicResearch:
    """Mark that Slack alert was sent for this record."""
    record = session.query(AcademicResearch).filter_by(id=record_id).first()
    if record:
        record.slack_alert_sent = True
        session.commit()
        session.refresh(record)
    return record
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/shared/test_academic_research.py::test_add_academic_research_record -v
```

Expected: `PASSED`

- [ ] **Step 5: Write and pass test for system_improvements**

```python
# tests/shared/test_system_improvements.py
import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from shared.system_improvements import SystemImprovement, add_improvement_record
from gateway.database import Base, engine

def test_add_system_improvement_record():
    """Test adding a system improvement record to database."""
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        record = add_improvement_record(
            session=session,
            source="arxiv",
            paper_id="2405.54321",
            title="Low-Latency Order Execution Optimization",
            authors="Narang, A.",
            abstract="We propose VWAP improvements...",
            url="https://arxiv.org/abs/2405.54321",
            publication_date=datetime(2026, 5, 15).date(),
            impact_area="execution",
            impact_score=92.0,
            feasibility_score=88.0,
            academic_score=85.0,
            combined_score=88.3,
            implementation_idea="Implement Narang's VWAP algorithm with ML prediction"
        )
        
        assert record.id is not None
        assert record.impact_area == "execution"
        assert record.combined_score == 88.3
        assert record.slack_alert_sent is False
```

Create `shared/system_improvements.py`:

```python
# shared/system_improvements.py
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()

class SystemImprovement(Base):
    """System improvement idea from academic research."""
    __tablename__ = "system_improvements"
    
    id = Column(Integer, primary_key=True)
    date_discovered = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), nullable=False)
    paper_id = Column(String(100), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=False)
    abstract = Column(Text, nullable=False)
    url = Column(String(500), nullable=False)
    publication_date = Column(Date, nullable=False)
    impact_area = Column(String(50), nullable=False)
    impact_score = Column(Float, nullable=False)
    feasibility_score = Column(Float, nullable=False)
    academic_score = Column(Float, nullable=False)
    combined_score = Column(Float, nullable=False)
    implementation_idea = Column(Text, nullable=False)
    github_issue_created = Column(Integer)
    issue_title = Column(String(500))
    slack_alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def add_improvement_record(
    session: Session,
    source: str,
    paper_id: str,
    title: str,
    authors: str,
    abstract: str,
    url: str,
    publication_date: date,
    impact_area: str,
    impact_score: float,
    feasibility_score: float,
    academic_score: float,
    combined_score: float,
    implementation_idea: str,
    github_issue_created: int = None,
    issue_title: str = None
) -> SystemImprovement:
    """Add a system improvement record to the database."""
    record = SystemImprovement(
        source=source,
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        publication_date=publication_date,
        impact_area=impact_area,
        impact_score=impact_score,
        feasibility_score=feasibility_score,
        academic_score=academic_score,
        combined_score=combined_score,
        implementation_idea=implementation_idea,
        github_issue_created=github_issue_created,
        issue_title=issue_title
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record

def mark_slack_alert_sent(session: Session, record_id: int) -> SystemImprovement:
    """Mark that Slack alert was sent for this record."""
    record = session.query(SystemImprovement).filter_by(id=record_id).first()
    if record:
        record.slack_alert_sent = True
        session.commit()
        session.refresh(record)
    return record
```

- [ ] **Step 6: Run both tests to verify they pass**

```bash
pytest tests/shared/test_academic_research.py tests/shared/test_system_improvements.py -v
```

Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add shared/academic_research.py shared/system_improvements.py tests/shared/test_academic_research.py tests/shared/test_system_improvements.py
git commit -m "feat: database models for academic research and system improvements"
```

---

### Task 2-6: Supervisor Researcher Implementation

Follow TDD pattern for each module:
1. Write failing test
2. Run to verify fail
3. Implement module
4. Run to verify pass
5. Commit

**Modules to implement:**
- `agents/supervisor_researcher/models.py` - Pydantic schemas
- `agents/supervisor_researcher/paper_fetcher.py` - arXiv/SSRN API
- `agents/supervisor_researcher/scorer.py` - Relevance/academic scoring
- `agents/supervisor_researcher/signal_generator.py` - Draft signal creation
- `agents/supervisor_researcher/agent.py` - Core orchestration
- `agents/supervisor_researcher/main.py` - APScheduler entry point

*Detailed code provided in supplementary plan document*

- [ ] **Complete all supervisor researcher modules and tests**
- [ ] **Run full test suite: `pytest tests/agents/supervisor_researcher/ -v`**
- [ ] **Commit each module separately**

---

### Task 7-11: Maintainer Researcher Implementation

Follow same TDD pattern as Tasks 2-6:

**Modules to implement:**
- `agents/maintainer_researcher/models.py` - Pydantic schemas
- `agents/maintainer_researcher/paper_fetcher.py` - arXiv/SSRN API
- `agents/maintainer_researcher/scorer.py` - Impact/feasibility scoring
- `agents/maintainer_researcher/issue_generator.py` - GitHub issue creation
- `agents/maintainer_researcher/agent.py` - Core orchestration
- `agents/maintainer_researcher/main.py` - APScheduler + API endpoints

*Detailed code provided in supplementary plan document*

- [ ] **Complete all maintainer researcher modules and tests**
- [ ] **Run full test suite: `pytest tests/agents/maintainer_researcher/ -v`**
- [ ] **Commit each module separately**

---

### Task 12: Integration & API

- [ ] **Create `gateway/routers/research.py` with endpoints:**
  - `GET /api/research/papers` - Query academic papers
  - `GET /api/research/improvements` - Query system improvements
  - `POST /api/research/run-supervisor` - Manual trigger
  - `POST /api/research/run-maintainer` - Manual trigger

- [ ] **Create `shared/slack_notifier.py` helper**

- [ ] **Update `gateway/main.py` to:**
  - Include research router
  - Start both schedulers on startup

- [ ] **Write integration tests in `tests/integration/test_researchers.py`**

- [ ] **Run full test suite: `pytest tests/ -v`**

- [ ] **Final commit: `git commit -m "feat: researcher agents system complete with API and integration tests"`**

---

## Requirements Installation

```bash
pip install arxiv requests sentence-transformers scikit-learn APScheduler slack-sdk PyGithub sqlalchemy pydantic
```

## Environment Variables Required

```bash
export SLACK_BOT_TOKEN=xoxb-...
export GITHUB_TOKEN=ghp_...
```

## Scheduling

- **Both researchers**: Daily at 6:00 AM UTC
- **Slack digests**: Sent 30 min after completion
- **Manual triggers**: Available via POST endpoints

## Success Criteria

✅ **Supervisor Researcher:**
- Fetches 50+ papers/day
- Generates 2-5 draft signals/day (confidence > 60%)
- Slack digest sent daily at 6:30 AM
- Signals integrated with aggregator

✅ **Maintainer Researcher:**
- Fetches 50+ papers/day
- Identifies 1-3 improvements/week (combined_score > 70)
- GitHub issues auto-created
- Slack digest sent daily at 6:30 AM

✅ **Integration:**
- All tests passing
- API endpoints functional
- Full audit trail in database
- Zero downtime during runs
