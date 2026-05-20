# AI Hedge Fund

Self-hosted AI-powered hedge fund. Runs fully locally — no cloud AI dependencies.

## Quick Start

**Prerequisites:**
- Python 3.11+
- Docker Desktop (for Redis + TimescaleDB)
- [Ollama](https://ollama.ai) installed and running locally

**Setup:**

1. Clone and enter the repo
2. Copy env template: `cp .env.example .env` and fill in your values
3. Install dependencies: `pip install -r requirements.txt`
4. Start services: `docker compose up -d`
5. Create database schema: `python scripts/setup_db.py`
6. Pull Ollama models: `ollama pull llama3.1:8b && ollama pull mistral:7b && ollama pull phi3:mini`
7. Start agents: `python scripts/start_all.py`

## Architecture

See `docs/superpowers/specs/2026-05-20-ai-hedge-fund-design.md` for the full design spec.

## Development

Run tests: `pytest tests/ -v`
