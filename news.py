import os
from datetime import datetime, timedelta
from typing import NamedTuple

from newsapi import NewsApiClient
from setup import get_logger, get_config

logger = get_logger(__name__)


class Headline(NamedTuple):
    title: str
    description: str


class FreshHeadlinesRetriever:
    def __init__(
        self,
        sources: list[str] = None,
        page_size: int = None,
        sort_by: str = None,
        language: str = None,
        query: str = None,
        from_days: int = None,
    ):
        # Use config defaults if not provided
        self.sources = ",".join(sources or get_config("news.sources", ["the-verge"]))
        self.page_size = page_size or get_config("news.page_size", 10)
        self.sort_by = sort_by or get_config("news.sort_by", "popularity")
        self.language = language or get_config("news.language", "en")
        self.query = query or get_config("news.query", "News")
        self.from_days = from_days or get_config("news.from_days", 7)
        self.newsapi = NewsApiClient(api_key=os.getenv("NEWSAPI_API_KEY"))

    def get_headlines(self, target_date: datetime.date):
        today = target_date.strftime("%Y-%m-%d")
        yesterday = (target_date - timedelta(days=self.from_days)).strftime("%Y-%m-%d")
        try:
            top_headlines = self.newsapi.get_everything(
                q=self.query,
                language=self.language,
                from_param=yesterday,
                to=today,
                sources=self.sources,
                sort_by=self.sort_by,
                page_size=self.page_size,
            )
            return [
                Headline(
                    title=article.get("title"), description=article.get("description")
                )
                for article in top_headlines.get("articles", [])
            ]
        except Exception as e:
            logger.error(f"Error getting headlines: {e}")
            return []
