"""
APScheduler entry point for maintainer researcher agent.
Runs daily at 7 AM UTC to fetch papers and generate actionable issues.
"""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from gateway.database import SessionLocal
from agents.maintainer_researcher.agent import MaintainerResearcherAgent

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

scheduler = BackgroundScheduler()

RESEARCH_QUERIES = [
    "distributed system consensus algorithm",
    "real-time data processing streaming",
    "automated trading execution architecture",
    "machine learning portfolio optimization",
    "fault tolerance distributed computing"
]


def run_researcher_job():
    """
    Run maintainer researcher job.
    Fetches papers, scores them, and saves to database.

    Returns:
        Dict with job results
    """
    logger.info("Starting maintainer researcher job")
    session = SessionLocal()
    try:
        agent = MaintainerResearcherAgent(session=session)
        results = agent.run(
            search_queries=RESEARCH_QUERIES,
            max_papers=50,
            min_overall_score=65.0
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
    Start APScheduler for daily researcher runs at 7 AM UTC.
    Idempotent: safe to call multiple times.
    """
    existing_job = scheduler.get_job('maintainer_researcher_daily')
    if existing_job is None:
        scheduler.add_job(
            run_researcher_job,
            'cron',
            hour=7,
            minute=0,
            id='maintainer_researcher_daily'
        )
        logger.info("Maintainer researcher scheduler started (daily at 7 AM UTC)")

    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    """
    Stop the scheduler.
    Idempotent: safe to call multiple times.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Maintainer researcher scheduler stopped")


if __name__ == "__main__":
    result = run_researcher_job()
    print(result)
