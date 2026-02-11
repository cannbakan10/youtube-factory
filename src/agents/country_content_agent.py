import os
import json
import random
from src.agents.trend_agent import TrendAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LongFormContentAgent:
    """
    Produces 10-minute long-form videos based on Google Trends.
    Topics can be anything: science, history, countries, tech, mysteries, etc.
    """

    def __init__(self, factory_instance):
        self.factory = factory_instance
        self.trend_agent = TrendAgent()
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
        )
        self.history_file = os.path.join(self.data_dir, "longform_history.json")
        os.makedirs(self.data_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_automation(self, region="USA"):
        """
        Finds a trending topic via Gemini/Google Trends and produces
        a ~10-minute long-form documentary-style video.
        """
        logger.info(f"Starting Long-Form Trending Automation (region={region})...")

        # 1. Find trending topics suitable for long-form
        trends = self._get_longform_trends(region=region, count=10)

        if not trends:
            logger.error("No trending topics found. Aborting.")
            return False

        # 2. Pick one that hasn't been produced recently
        history = self._load_history()
        available = [t for t in trends if t["topic"] not in history]

        if not available:
            logger.warning("All trending topics already produced. Picking random fresh one anyway.")
            available = trends

        selected = random.choice(available)
        topic_title = selected["topic"]

        logger.info(f"Selected Topic: {topic_title} (Reason: {selected.get('reason', 'N/A')})")

        # 3. Create descriptive topic string for the factory
        topic = f"{topic_title} - 10 minute deep dive documentary"

        # 4. Produce via Factory
        production_id = self.factory.run(
            topic=topic,
            languages=["en"],
            auto_upload=True,
            video_type="long",
            mode="info",
            style_context="Cinematic, educational, visually rich documentary with a strong narrative arc.",
        )

        if production_id:
            logger.info(f"Long-Form Automation Success: {production_id}")
            self._update_history(topic_title)
            return True
        else:
            logger.error(f"Long-Form Automation Failed for: {topic_title}")
            return False

    # ------------------------------------------------------------------
    # Trend Discovery (Long-Form optimized)
    # ------------------------------------------------------------------
    def _get_longform_trends(self, region="USA", count=10):
        """
        Uses TrendAgent with a custom prompt to find topics that are
        specifically suitable for 10-minute deep-dive videos.
        """
        try:
            return self._fetch_longform_trends(region, count)
        except Exception as e:
            logger.warning(f"Custom long-form trend fetch failed: {e}. Falling back to TrendAgent.")
            return self.trend_agent.get_trending_topics(region=region, count=count)

    def _fetch_longform_trends(self, region, count):
        if not self.trend_agent.client:
            logger.warning("Gemini not configured. Using default TrendAgent.")
            return self.trend_agent.get_trending_topics(region=region, count=count)

        from src.utils.retry import APIRateLimiters
        import json as _json

        APIRateLimiters.gemini.wait()

        prompt = f"""
        Find the top {count} currently viral, trending, or highly searched topics 
        that would make excellent 10-MINUTE DEEP DIVE YouTube videos.
        
        Region focus: {region} (but universal appeal preferred).
        Language: English.
        
        IMPORTANT: Topics should be DIVERSE. Include a mix of:
        - Science & Space (e.g. "Black holes that shouldn't exist")
        - History & Mysteries (e.g. "The lost city beneath the Sahara")
        - Technology & AI (e.g. "How quantum computers will change everything")
        - Nature & Animals (e.g. "The deadliest creatures in the Amazon")
        - Psychology & Human Behavior (e.g. "Why your brain lies to you")
        - Countries & Geography (e.g. "Why Norway is the happiest country")
        - Economics & Society (e.g. "How Dubai went from desert to megacity")
        - Health & Medicine (e.g. "The organ that science still can't explain")
        
        Each topic MUST be specific enough for a 10-minute documentary, not too broad, not too narrow.
        
        OUTPUT FORMAT (Strict JSON):
        [
            {{"topic": "Specific Engaging Topic Title", "reason": "Why it is trending or interesting", "language": "en"}},
            ...
        ]
        """

        response = self.trend_agent.client.models.generate_content(
            model=self.trend_agent.model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        topics = _json.loads(response.text)
        logger.info(f"Found {len(topics)} long-form trending topics")
        return topics

    # ------------------------------------------------------------------
    # History Management
    # ------------------------------------------------------------------
    def _load_history(self):
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r") as f:
                data = json.load(f)
                # Only keep the last 100 entries to avoid infinite blocking
                return data[-100:] if len(data) > 100 else data
        except Exception:
            return []

    def _update_history(self, topic):
        history = self._load_history()
        history.append(topic)
        with open(self.history_file, "w") as f:
            json.dump(history, f, ensure_ascii=False)
