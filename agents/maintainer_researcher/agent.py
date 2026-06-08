"""
MaintainerResearcherAgent: Discovers papers with actionable GitHub issue potential.
Scores based on implementability, strategic value, maintainer relevance.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from agents.maintainer_researcher.paper_fetcher import fetch_arxiv_papers, parse_paper_metadata
from agents.maintainer_researcher.scorer import (
    calculate_implementability_score,
    calculate_strategic_value_score,
    calculate_maintainer_relevance_score,
    calculate_overall_score,
    tag_issue_types
)
from agents.maintainer_researcher.issue_generator import create_draft_github_issue
from shared.academic_research import add_research_record

logger = logging.getLogger(__name__)


class MaintainerResearcherAgent:
    """
    Maintainer researcher agent that:
    1. Fetches academic papers from arxiv
    2. Scores them on implementability, strategic value, maintainer relevance
    3. Creates draft GitHub issues
    4. Saves records to database
    """

    def __init__(self, session: Session):
        """
        Initialize agent with database session.

        Args:
            session: SQLAlchemy Session for database operations
        """
        self.session = session

    def run(
        self,
        search_queries: List[str],
        max_papers: int = 50,
        min_overall_score: float = 65.0
    ) -> Dict[str, Any]:
        """
        Run researcher agent on list of search queries.

        Args:
            search_queries: List of search terms for arxiv
            max_papers: Maximum papers to fetch per query
            min_overall_score: Minimum overall score to save record

        Returns:
            Dict with results: papers_fetched, papers_scored, draft_issues_created,
                              research_records_saved, errors
        """
        results = {
            'papers_fetched': 0,
            'papers_scored': 0,
            'draft_issues_created': 0,
            'research_records_saved': 0,
            'errors': []
        }

        for query in search_queries:
            try:
                papers = fetch_arxiv_papers(search_query=query, max_results=max_papers, days_back=7)
                results['papers_fetched'] += len(papers)
                logger.info(f"Fetched {len(papers)} papers for query: {query}")

                for paper in papers:
                    try:
                        metadata = parse_paper_metadata(paper, source='arxiv')

                        days_old = (datetime.utcnow() - paper.published).days

                        implementability = calculate_implementability_score(
                            paper.title,
                            paper.summary
                        )
                        strategic_value = calculate_strategic_value_score(
                            paper.title,
                            paper.summary
                        )
                        maintainer_relevance = calculate_maintainer_relevance_score(
                            paper.title,
                            paper.summary,
                            days_old
                        )
                        overall_score = calculate_overall_score(
                            implementability,
                            strategic_value,
                            maintainer_relevance
                        )

                        results['papers_scored'] += 1

                        if overall_score >= min_overall_score:
                            tags = ",".join(tag_issue_types(paper.summary))
                            draft_issue = create_draft_github_issue(
                                metadata,
                                implementability,
                                strategic_value,
                                maintainer_relevance,
                                overall_score,
                                tags
                            )
                            results['draft_issues_created'] += 1
                            logger.info(f"Created draft issue for: {metadata.title}")

                            record = add_research_record(
                                session=self.session,
                                source='arxiv',
                                paper_id=metadata.paper_id,
                                title=metadata.title,
                                authors=metadata.authors,
                                abstract=metadata.abstract,
                                url=metadata.url,
                                publication_date=metadata.publication_date,
                                relevance_score=implementability,
                                academic_score=strategic_value,
                                confidence_score=overall_score,
                                strategy_tags=tags,
                                generated_signal_id=None
                            )
                            results['research_records_saved'] += 1
                            logger.info(
                                f"Saved research record: {metadata.title} "
                                f"(overall: {overall_score:.1f})"
                            )
                        else:
                            logger.info(
                                f"Skipped low-score paper: {metadata.title} "
                                f"(overall: {overall_score:.1f})"
                            )

                    except Exception as e:
                        logger.error(f"Error processing paper: {e}", exc_info=True)
                        results['errors'].append(str(e))

            except Exception as e:
                logger.error(
                    f"Error fetching papers for query '{query}': {e}",
                    exc_info=True
                )
                results['errors'].append(str(e))

        logger.info(f"Maintainer researcher job completed: {results}")
        return results
