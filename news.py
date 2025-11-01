import os
import random
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
        category: str = None,
        page_size: int = None,
        language: str = None,
    ):
        # Use config defaults if not provided
        self.category = category or get_config("news.category", "general")
        self.page_size = page_size or get_config("news.page_size", 10)
        self.language = language or get_config("news.language", "en")
        self.newsapi = NewsApiClient(api_key=os.getenv("NEWSAPI_API_KEY"))

    def get_headlines(self):
        try:
            top_headlines = self.newsapi.get_top_headlines(
                language=self.language,
                category=self.category,
            )
            articles = top_headlines.get("articles", [])
            sampled_articles = random.sample(
                articles, min(self.page_size, len(articles))
            )
            return [
                Headline(
                    title=article.get("title"), description=article.get("description")
                )
                for article in sampled_articles
            ]
        except Exception as e:
            logger.error(f"Error getting headlines: {e}")
            return []
