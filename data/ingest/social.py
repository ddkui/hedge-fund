import asyncio
import praw
from data.ingest.base import DataIngestAgent

SUBREDDITS = "wallstreetbets+investing+stocks+CryptoCurrency+SecurityAnalysis"


class SocialIngestAgent(DataIngestAgent):
    def __init__(self, *args, client_id: str, client_secret: str, user_agent: str = "hedgefund/1.0", **kwargs):
        super().__init__(*args, **kwargs)
        self._reddit_creds = {
            "client_id": client_id,
            "client_secret": client_secret,
            "user_agent": user_agent,
        }

    def _fetch_posts(self) -> list[dict]:
        reddit = praw.Reddit(**self._reddit_creds)
        posts = []
        for post in reddit.subreddit(SUBREDDITS).hot(limit=25):
            posts.append({
                "id": post.id,
                "title": post.title,
                "score": post.score,
                "subreddit": str(post.subreddit),
                "url": post.url,
                "created_utc": post.created_utc,
            })
        return posts

    async def run_once(self):
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(None, self._fetch_posts)
        await self.bus.publish("data.social.updated", {
            "post_count": len(posts),
            "source": "reddit",
            "posts": posts,
        })
        self.logger.info("social_ingested", posts=len(posts))
