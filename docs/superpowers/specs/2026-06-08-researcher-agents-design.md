# Researcher Agents System Design

**Date**: 2026-06-08  
**Status**: Approved  
**Author**: Claude Code

---

## Executive Summary

Implement two daily-running researcher agents:
1. **Supervisor's Researcher** - Monitors academic papers on quant strategies, generates draft trading signals
2. **Maintainer's Researcher** - Monitors academic papers on system improvements, creates actionable GitHub issues

Both agents query arXiv, SSRN, and academic APIs daily, rank findings by relevance/impact, store results in database, and send Slack digests.

---

## Goals

- **Supervisor Researcher**: Continuously discover cutting-edge quant strategies from academia and convert them into trading signals
- **Maintainer Researcher**: Identify system improvements (execution, risk, architecture) backed by academic research
- **Integration**: Results feed into supervisor agent (signals) and GitHub issue tracker (improvements)
- **Transparency**: Full audit trail of which papers influenced which decisions

---

## Architecture

```
Academic Sources (arXiv, SSRN, APIs)
    ↓
Supervisor Researcher Agent → Draft Signals → Supervisor Review → Aggregator Signals
    ↓
    Database (academic_research table)
    ↓
    Slack Digest (#research)

System Improvement Researcher Agent → GitHub Issues (high-impact only)
    ↓
    Database (system_improvements table)
    ↓
    Slack Digest (#maintenance)
```

---

## Component 1: Supervisor's Researcher Agent

**Purpose**: Find academic papers on quant strategies, generate draft trading signals

**Daily Workflow** (runs at 6 AM UTC):
1. Query arXiv, SSRN for papers on: momentum, mean reversion, pairs trading, ML strategies, alternative data
2. Filter by: published in last 7 days, high relevance match to your current strategies
3. Score each paper:
   - Relevance score (0-100): how applicable to your current portfolio/strategies
   - Academic score (0-100): citation count + venue reputation
   - **Combined confidence = 0.5 × relevance + 0.3 × recency + 0.2 × academic**
4. Create draft signals for papers with confidence > 60%
5. Store findings in `academic_research` table
6. Send Slack digest: top 5 papers with signal recommendations

**Scoring Logic**:
- **Relevance**: Sentence similarity between paper abstract and your existing strategy descriptions
- **Recency**: (Days since publication) / 7 → newer papers score higher
- **Academic**: (Citation count / max_citations_in_dataset) → peer review validation

**Output**:
- Draft signals → Supervisor agent reviews → auto-approves (conf > 75%) or flags marginal ones
- Database record: paper title, authors, URL, relevance score, generated signal (if any)
- Slack: "5 new papers today: [Title] (75% confidence, suggests long momentum positions)"

---

## Component 2: Maintainer's Researcher Agent

**Purpose**: Find academic papers on system improvements, create actionable recommendations

**Daily Workflow** (runs at 6 AM UTC):
1. Query arXiv, SSRN for papers on: 
   - Execution optimization, market microstructure
   - Risk management, volatility models, hedging techniques
   - System architecture, distributed computing, low-latency design
2. Filter by: published in last 30 days, high citations, addresses known system limitations
3. Evaluate each paper:
   - **Impact score**: Does it solve a current system weakness? (0-100)
   - **Feasibility score**: Can we implement in <2 weeks? (0-100)
   - **Academic score**: Peer-reviewed, well-cited? (0-100)
4. Create GitHub issue ONLY if: (impact × feasibility × academic) / 1,000,000 > 0.7 (i.e., geometric mean > 70)
5. Store all findings in `system_improvements` table
6. Send Slack digest: top 3-5 papers with implementation ideas

**Output**:
- GitHub Issues: Auto-created for actionable improvements with implementation outline
- Database record: paper title, problem area (execution/risk/architecture), why it matters, implementation outline
- Slack: "Found optimization idea for order execution latency (refs Narang 2023)"

---

## Data Models

### academic_research Table

```python
- id (primary key)
- date_discovered (datetime)
- source (str: "arxiv" or "ssrn")
- paper_id (str: arxiv ID or SSRN ID)
- title (str)
- authors (str, comma-separated)
- abstract (text)
- url (str)
- publication_date (date)
- relevance_score (float 0-100): how applicable to current strategies
- academic_score (float 0-100): citations + venue
- confidence_score (float 0-100): weighted combination
- strategy_tags (str, comma-separated: "momentum,mean_reversion,ml")
- generated_signal_id (int or null): if draft signal created
- slack_alert_sent (bool)
- created_at (datetime)
```

### system_improvements Table

```python
- id (primary key)
- date_discovered (datetime)
- source (str: "arxiv" or "ssrn")
- paper_id (str)
- title (str)
- authors (str)
- abstract (text)
- url (str)
- publication_date (date)
- impact_area (str: "execution" or "risk" or "architecture" or "performance")
- impact_score (float 0-100): solves current weakness
- feasibility_score (float 0-100): implementable in <2 weeks
- academic_score (float 0-100): peer review validation
- combined_score (float 0-100): geometric mean
- implementation_idea (text): proposed solution from paper
- github_issue_created (int or null): GitHub issue number
- issue_title (str or null): GitHub issue title
- slack_alert_sent (bool)
- created_at (datetime)
```

---

## File Structure

```
agents/
├── supervisor_researcher/
│   ├── __init__.py
│   ├── main.py                     # Entry point (APScheduler)
│   ├── agent.py                    # Core logic
│   ├── paper_fetcher.py            # arXiv/SSRN API calls
│   ├── signal_generator.py         # Draft signal creation
│   ├── scorer.py                   # Relevance/academic scoring
│   ├── models.py                   # Pydantic models
│   └── requirements.txt
├── maintainer_researcher/
│   ├── __init__.py
│   ├── main.py                     # Entry point (APScheduler)
│   ├── agent.py                    # Core logic
│   ├── paper_fetcher.py            # arXiv/SSRN API calls
│   ├── issue_generator.py          # GitHub issue creation
│   ├── scorer.py                   # Impact/feasibility scoring
│   ├── models.py                   # Pydantic models
│   └── requirements.txt

shared/
├── academic_research.py            # DB models + helpers
├── system_improvements.py          # DB models + helpers
└── slack_notifier.py               # Shared Slack sending

gateway/routers/
├── research.py                     # API: GET /api/research/papers, /api/research/improvements

tests/
├── agents/supervisor_researcher/   # Unit tests
│   ├── test_paper_fetcher.py
│   ├── test_signal_generator.py
│   ├── test_scorer.py
│   └── test_agent.py
├── agents/maintainer_researcher/   # Unit tests
│   ├── test_paper_fetcher.py
│   ├── test_issue_generator.py
│   ├── test_scorer.py
│   └── test_agent.py
└── integration/test_researchers.py # E2E tests
```

---

## Integration Points

1. **Supervisor Researcher → Supervisor Agent**
   - Supervisor agent queries `academic_research` table daily
   - Filters for confidence_score > 75%, generated_signal_id NOT NULL
   - Reviews draft signals, auto-approves high-confidence ones
   - Feeds approved signals into aggregator via existing signal table

2. **Maintainer Researcher → GitHub**
   - Auto-creates GitHub issues for high-impact improvements
   - Links to paper, implementation idea in issue body
   - Maintainer converts to dev tasks

3. **Both → Database**
   - Historical record for audit trail
   - Searchable by date, topic, relevance, strategy tags (supervisor) / impact area (maintainer)

4. **Both → Slack**
   - Daily digests at 6:30 AM UTC (5 min after researchers finish)
   - Links to papers, confidence/impact scores, next actions

---

## Technology Stack

- **Paper Sources**:
  - arXiv API v3 (free, no auth required)
  - SSRN API (free, no auth required)
  - Exa Search API (optional, via Exa MCP server already configured)
  
- **NLP for Relevance Scoring**:
  - Sentence-transformers (pre-trained model for semantic similarity)
  - TF-IDF for keyword matching to strategy names
  
- **Scheduling**: APScheduler (daily at 6 AM UTC)
  
- **Integration**: 
  - Slack SDK (send digests)
  - GitHub API via `gh` CLI (create issues)
  - FastAPI endpoints for querying research
  
- **Storage**: 
  - SQLAlchemy ORM for research tables
  - Existing SQLite database

---

## Dependencies

```
requests>=2.28.0          # HTTP calls to arXiv/SSRN
arxiv>=2.1.0              # arXiv API wrapper
sentence-transformers>=2.2.0  # Semantic similarity scoring
scikit-learn>=1.3.0       # TF-IDF vectorization
APScheduler>=3.10.0       # Daily job scheduling
slack-sdk>=3.23.0         # Slack notifications
PyGithub>=2.1.1           # GitHub API (alternative to gh CLI)
```

---

## Scheduling

Both agents run daily at **6:00 AM UTC**:
- Supervisor Researcher: Fetch papers, score, generate signals, save to DB, send Slack at 6:30 AM
- Maintainer Researcher: Fetch papers, score, create GitHub issues, save to DB, send Slack at 6:30 AM

Can be overridden via:
- API endpoint: `POST /api/research/run-supervisor` (manual trigger)
- API endpoint: `POST /api/research/run-maintainer` (manual trigger)

---

## Security & Compliance

- **No auth required** for arXiv/SSRN APIs (public data)
- **GitHub token** stored in `.env` as `GITHUB_TOKEN` (for issue creation)
- **Slack token** stored in `.env` as `SLACK_BOT_TOKEN` (for digests)
- **Database**: Results stored in audit-logged database tables
- **Audit trail**: Every paper → signal/issue conversion logged with timestamp

---

## Success Criteria

✅ Supervisor Researcher:
- Fetches 50+ papers/day from arXiv/SSRN
- Scores 80%+ accurately (relevance to actual strategies)
- Generates 2-5 draft signals/day (confidence > 60%)
- Slack digest sent daily at 6:30 AM
- Signals visible in supervisor agent's consideration

✅ Maintainer Researcher:
- Fetches 50+ papers/day from arXiv/SSRN
- Identifies 1-3 actionable improvements/week (combined_score > 70)
- GitHub issues auto-created with clear implementation outlines
- Slack digest sent daily at 6:30 AM
- Issues prioritized by impact score

✅ Integration:
- Supervisor signals flow into aggregator without manual intervention
- Maintainer issues tracked alongside normal dev tasks
- Full audit trail searchable in database
- Zero downtime during research runs

---

## Future Enhancements

- Fine-tune scoring based on signal win rate (if supervisor signals become profitable)
- Add sentiment analysis to paper abstracts (positive/negative for market conditions)
- Integrate with external research platforms (Quantpedia, QuantInsti)
- Auto-generate strategy backtest code from papers
- Citation tracking (follow researchers whose papers are consistently profitable)
