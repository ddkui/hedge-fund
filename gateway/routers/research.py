"""
FastAPI router for research endpoints.
Provides access to academic research papers and system improvements.
"""
from fastapi import APIRouter, Query
from sqlalchemy.orm import Session
from gateway.database import SessionLocal
from shared.academic_research import AcademicResearch
from shared.system_improvements import SystemImprovement

router = APIRouter()


@router.get("/api/research/papers")
async def get_research_papers(skip: int = Query(0), limit: int = Query(10)):
    """
    Get academic research papers.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum records to return (default 10, max 100)

    Returns:
        Dict with count and list of papers
    """
    # Validate limits
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    session = SessionLocal()
    try:
        papers = (
            session.query(AcademicResearch)
            .order_by(AcademicResearch.date_discovered.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {
            "count": len(papers),
            "skip": skip,
            "limit": limit,
            "papers": [
                {
                    "id": p.id,
                    "title": p.title,
                    "authors": p.authors,
                    "source": p.source,
                    "paper_id": p.paper_id,
                    "url": p.url,
                    "publication_date": str(p.publication_date),
                    "confidence_score": p.confidence_score,
                    "relevance_score": p.relevance_score,
                    "academic_score": p.academic_score,
                    "strategy_tags": p.strategy_tags,
                    "date_discovered": p.date_discovered.isoformat() if p.date_discovered else None,
                }
                for p in papers
            ]
        }
    finally:
        session.close()


@router.get("/api/research/improvements")
async def get_system_improvements(skip: int = Query(0), limit: int = Query(10)):
    """
    Get system improvement ideas derived from research.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum records to return (default 10, max 100)

    Returns:
        Dict with count and list of improvements
    """
    # Validate limits
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    session = SessionLocal()
    try:
        improvements = (
            session.query(SystemImprovement)
            .order_by(SystemImprovement.combined_score.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {
            "count": len(improvements),
            "skip": skip,
            "limit": limit,
            "improvements": [
                {
                    "id": i.id,
                    "title": i.title,
                    "authors": i.authors,
                    "source": i.source,
                    "paper_id": i.paper_id,
                    "url": i.url,
                    "publication_date": str(i.publication_date),
                    "impact_area": i.impact_area,
                    "impact_score": i.impact_score,
                    "feasibility_score": i.feasibility_score,
                    "academic_score": i.academic_score,
                    "combined_score": i.combined_score,
                    "implementation_idea": i.implementation_idea,
                    "github_issue_created": i.github_issue_created,
                    "issue_title": i.issue_title,
                    "date_discovered": i.date_discovered.isoformat() if i.date_discovered else None,
                }
                for i in improvements
            ]
        }
    finally:
        session.close()


@router.post("/api/research/run-supervisor")
async def run_supervisor_researcher():
    """
    Trigger the supervisor researcher job.
    Fetches academic papers and generates trading signals.

    Returns:
        Job execution results
    """
    try:
        from agents.supervisor_researcher.main import run_researcher_job
        result = run_researcher_job()
        return {
            "status": "success",
            "job": "supervisor_researcher",
            "results": result
        }
    except Exception as e:
        return {
            "status": "error",
            "job": "supervisor_researcher",
            "error": str(e)
        }


@router.post("/api/research/run-maintainer")
async def run_maintainer_researcher():
    """
    Trigger the maintainer researcher job.
    Fetches academic papers and generates GitHub issues.

    Returns:
        Job execution results
    """
    try:
        from agents.maintainer_researcher.main import run_researcher_job
        result = run_researcher_job()
        return {
            "status": "success",
            "job": "maintainer_researcher",
            "results": result
        }
    except Exception as e:
        return {
            "status": "error",
            "job": "maintainer_researcher",
            "error": str(e)
        }


@router.get("/api/research/stats")
async def get_research_stats():
    """
    Get research database statistics.

    Returns:
        Stats on papers and improvements
    """
    session = SessionLocal()
    try:
        papers_count = session.query(AcademicResearch).count()
        improvements_count = session.query(SystemImprovement).count()

        # Get highest scoring papers
        top_paper = (
            session.query(AcademicResearch)
            .order_by(AcademicResearch.confidence_score.desc())
            .first()
        )

        # Get highest scoring improvements
        top_improvement = (
            session.query(SystemImprovement)
            .order_by(SystemImprovement.combined_score.desc())
            .first()
        )

        return {
            "papers_count": papers_count,
            "improvements_count": improvements_count,
            "top_paper": {
                "title": top_paper.title,
                "score": top_paper.confidence_score
            } if top_paper else None,
            "top_improvement": {
                "title": top_improvement.title,
                "score": top_improvement.combined_score
            } if top_improvement else None
        }
    finally:
        session.close()
