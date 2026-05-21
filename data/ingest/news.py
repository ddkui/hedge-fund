import httpx
from datetime import datetime
from data.ingest.base import DataIngestAgent

NEWSAPI_URL = "https://newsapi.org/v2/everything"
QUERY = "stock market OR cryptocurrency OR finance OR earnings"


class NewsIngestAgent(DataIngestAgent):
    def __init__(self, *args, api_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key

    async def run_once(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                NEWSAPI_URL,
                params={
                    "q": QUERY,
                    "apiKey": self.api_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                },
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])

        rows = [
            (
                datetime.fromisoformat(art["publishedAt"].replace("Z", "+00:00")),
                art.get("source", {}).get("name", "unknown"),
                art["title"],
                art.get("url", ""),
                None,
            )
            for art in articles
        ]
        if rows:
            await self.db.executemany(
                "INSERT INTO news_items (time, source, headline, url, sentiment_score) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                rows,
            )
        await self.bus.publish("data.news.updated", {"article_count": len(articles)})
        self.logger.info("news_ingested", articles=len(articles))
