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
        self.model = "gemini-2.5-flash"
        self.fallback_models = ["gemini-2.0-flash-lite", "gemini-1.5-flash"]

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

        # Try primary model, then fallbacks if 404/quota error
        last_err = None
        for model in [self.model] + self.fallback_models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                topics = json.loads(response.text)
                logger.info(f"Found {len(topics)} trending topics ({model})")
                return topics
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "not_found" in err_str or "404" in err_str or "resource_exhausted" in err_str or "429" in err_str:
                    logger.warning(f"Trends: {model} unavailable, trying next...")
                    continue
                raise
        raise last_err or RuntimeError("All Gemini models exhausted")


if __name__ == "__main__":
    agent = TrendAgent()
    trends = agent.get_trending_topics()
    for i, t in enumerate(trends):
        print(f"{i + 1}. {t['topic']} ({t['reason']})")
