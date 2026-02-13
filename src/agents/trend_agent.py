import os
import json
from google import genai
from typing import List
from dotenv import load_dotenv
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters

load_dotenv()

logger = get_logger(__name__)


class TrendAgent:
    def __init__(self):
        # Ultra-Clean Key Loading
        raw_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_key = raw_key.strip().replace('"', '').replace("'", "")
        self.client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        self.model = "gemini-2.0-flash"

    def get_trending_topics(self, region="USA", category="General", count=5) -> List[dict]:
        """
        Uses Gemini's real-time knowledge (search enabled) to find viral/trending topics.
        """
        try:
            return self._fetch_trends(region, category, count)
        except Exception as e:
            logger.error(f"Trend Discovery Error: {e}")
            return []

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _fetch_trends(self, region, category, count) -> List[dict]:
        """Fetch trends with retry support."""
        if not self.client:
            logger.warning("Gemini not configured. Trend discovery disabled.")
            return []
        APIRateLimiters.gemini.wait()

        prompt = f"""
        Find the top {count} currently viral, trending, or highly searched topics in {region}
        that would make excellent, high-retention YouTube Shorts (Fact/Info style).

        Focus on:
        - Educational interesting facts
        - Recent scientific discoveries
        - Shocking historical events
        - Viral mysteries
        - Trending technology/AI news

        ALL content must be in ENGLISH. This is for a US audience.

        OUTPUT FORMAT (Strict JSON):
        [
            {{"topic": "Short Topic Title", "reason": "Why it is trending", "language": "en"}},
            ...
        ]
        """

        # Using Gemini 2.0 Flash's search capability
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        topics = json.loads(response.text)
        logger.info(f"Found {len(topics)} trending topics")
        return topics


if __name__ == "__main__":
    agent = TrendAgent()
    trends = agent.get_trending_topics()
    for i, t in enumerate(trends):
        print(f"{i + 1}. {t['topic']} ({t['reason']})")
