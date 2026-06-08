# agents/supervisor_researcher/agent.py
"""
SupervisorResearcherAgent: Orchestrates academic paper discovery, scoring, and signal generation.
Part of the AI hedge fund's research pipeline.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from agents.supervisor_researcher.paper_fetcher import fetch_arxiv_papers, parse_paper_metadata
from agents.supervisor_researcher.scorer import calculate_relevance_score, calculate_academic_score, calculate_confidence_score, tag_strategies
from agents.supervisor_researcher.signal_generator import create_draft_signal
from shared.academic_research import add_research_record

logger = logging.getLogger(__name__)


class SupervisorResearcherAgent:
    """
    Supervisor researcher agent that:
    1. Fetches academic papers from arxiv
    2. Scores them on relevance, academic quality, and confidence
    3. Creates draft trading signals
    4. Saves records to database
    """

    def __init__(self, session: Session):
        """
        Initialize agent with database session.

        Args:
            session: SQLAlchemy Session for database operations
        """
        self.session = session
        self.strategy_descriptions = {
            "momentum": "Buy stocks with positive momentum, sell with negative momentum",
            "mean_reversion": "Trade mean-reverting price movements",
            "pairs_trading": "Trade correlated pairs of stocks",
            "ml": "Use machine learning for signal generation",
            "alternative_data": "Trade on alternative data sources"
        }

    def run(self, search_queries: List[str], max_papers: int = 50, min_confidence: float = 60.0) -> Dict[str, Any]:
        """
        Run researcher agent on list of search queries.

        Args:
            search_queries: List of search terms for arxiv
            max_papers: Maximum papers to fetch per query
            min_confidence: Minimum confidence score to save record

        Returns:
            Dict with results: papers_fetched, papers_scored, draft_signals_created,
                              research_records_saved, errors
        """
        results = {
            'papers_fetched': 0,
            'papers_scored': 0,
            'draft_signals_created': 0,
            'research_records_saved': 0,
            'errors': []
        }

        for query in search_queries:
            try:
                # Fetch papers from arxiv
                papers = fetch_arxiv_papers(search_query=query, max_results=max_papers, days_back=7)
                results['papers_fetched'] += len(papers)
                logger.info(f"Fetched {len(papers)} papers for query: {query}")

                # Process each paper
                for paper in papers:
                    try:
                        # Parse metadata
                        metadata = parse_paper_metadata(paper, source='arxiv')

                        # Calculate scores
                        relevance = calculate_relevance_score(
                            paper.title,
                            paper.summary,
                            self.strategy_descriptions
                        )
                        academic = calculate_academic_score(
                            citations=0,
                            max_citations_in_dataset=100,
                            venue_rank=0.7
                        )
                        days_old = (datetime.utcnow() - paper.published).days
                        confidence = calculate_confidence_score(relevance, academic, days_old)
                        tags = ",".join(tag_strategies(paper.summary))

                        results['papers_scored'] += 1

                        # Only process papers with sufficient confidence
                        if confidence >= min_confidence:
                            # Create draft signal
                            draft_signal = create_draft_signal(metadata, confidence, tags)
                            results['draft_signals_created'] += 1
                            logger.info(f"Created draft signal for: {metadata.title}")

                            # Save research record to database
                            record = add_research_record(
                                session=self.session,
                                source='arxiv',
                                paper_id=metadata.paper_id,
                                title=metadata.title,
                                authors=metadata.authors,
                                abstract=metadata.abstract,
                                url=metadata.url,
                                publication_date=metadata.publication_date,
                                relevance_score=relevance,
                                academic_score=academic,
                                confidence_score=confidence,
                                strategy_tags=tags,
                                generated_signal_id=None
                            )
                            results['research_records_saved'] += 1
                            logger.info(
                                f"Saved research record: {metadata.title} "
                                f"(confidence: {confidence:.1f})"
                            )
                        else:
                            logger.info(
                                f"Skipped low-confidence paper: {metadata.title} "
                                f"(confidence: {confidence:.1f})"
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

        logger.info(f"Supervisor researcher job completed: {results}")
        return results
