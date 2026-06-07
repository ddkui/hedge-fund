import arxiv
from datetime import datetime
from typing import List
from agents.supervisor_researcher.models import PaperMetadata


def fetch_arxiv_papers(search_query: str, max_results: int = 50, days_back: int = 7) -> List[arxiv.Result]:
    """Fetch papers from arXiv matching search query, last N days."""
    client = arxiv.Client()
    query = f"{search_query} AND (cat:q-fin.TR OR cat:q-fin.ST OR cat:math.ST OR cat:stat.ML)"
    papers = []
    for result in client.results(arxiv.Search(query=query, max_results=max_results)):
        days_old = (datetime.utcnow() - result.published).days
        if days_old <= days_back:
            papers.append(result)
    return papers


def fetch_ssrn_papers(search_keywords: List[str], max_results: int = 50) -> List[dict]:
    """Fetch papers from SSRN. Returns empty list (API requires web scraping)."""
    # SSRN doesn't provide structured API; would require BeautifulSoup/Selenium
    return []


def parse_paper_metadata(paper, source: str) -> PaperMetadata:
    """Parse paper object into standardized metadata."""
    if source == "arxiv":
        paper_id = paper.entry_id.split('/abs/')[-1]
        authors_list = [author.name for author in paper.authors]
        return PaperMetadata(
            paper_id=paper_id,
            source="arxiv",
            title=paper.title,
            authors=", ".join(authors_list),
            abstract=paper.summary,
            url=paper.pdf_url,
            publication_date=paper.published.date()
        )
    elif source == "ssrn":
        return PaperMetadata(
            paper_id=paper['id'],
            source="ssrn",
            title=paper['title'],
            authors=paper['authors'],
            abstract=paper['abstract'],
            url=paper['url'],
            publication_date=paper['publication_date']
        )
    raise ValueError(f"Unknown source: {source}")
