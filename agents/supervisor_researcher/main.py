# agents/supervisor_researcher/main.py
"""
APScheduler entry point for supervisor researcher agent.
Runs daily at 6 AM UTC to fetch and score academic papers.
"""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from gateway.database import SessionLocal
from agents.supervisor_researcher.agent import SupervisorResearcherAgent

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# APScheduler background scheduler
scheduler = BackgroundScheduler()

# Research queries for academic paper discovery
RESEARCH_QUERIES = [
    "quant momentum trading machine learning",
    "mean reversion statistical arbitrage",
    "pairs trading cointegration",
    "alternative data sentiment analysis trading"
]


def run_researcher_job():
    """
    Run supervisor researcher job.
    Fetches papers, scores them, and saves to database.

    Returns:
        Dict with job results (papers_fetched, papers_scored, etc.)
    """
    logger.info("Starting supervisor researcher job")
    session = SessionLocal()
    try:
        agent = SupervisorResearcherAgent(session=session)
        results = agent.run(
            search_queries=RESEARCH_QUERIES,
            max_papers=50,
            min_confidence=60.0
        )
        logger.info(f"Job completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Error in researcher job: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        session.close()


def start_scheduler():
    """
    Start APScheduler for daily researcher runs at 6 AM UTC.
    Idempotent: safe to call multiple times.
    """
    # Only add job if not already present
    existing_job = scheduler.get_job('supervisor_researcher_daily')
    if existing_job is None:
        scheduler.add_job(
            run_researcher_job,
            'cron',
            hour=6,
            minute=0,
            id='supervisor_researcher_daily'
        )
        logger.info("Supervisor researcher scheduler started (daily at 6 AM UTC)")

    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    """
    Stop the scheduler.
    Idempotent: safe to call multiple times.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Supervisor researcher scheduler stopped")


if __name__ == "__main__":
    # Run immediately when executed as script
    result = run_researcher_job()
    print(result)
