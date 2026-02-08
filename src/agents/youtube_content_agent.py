import os
import json
import random
from src.agents.trend_agent import TrendAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)

class YouTubeContentAgent:
    def __init__(self, factory_instance):
        self.trend_agent = TrendAgent()
        self.factory = factory_instance
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def run_daily_automation(self, region="USA"):
        """
        Finds trends and produces a YouTube Short.
        """
        logger.info(f"Starting YouTube Daily Automation for region: {region}")
        
        # 1. Get Trending Topics
        trends = self.trend_agent.get_trending_topics(region=region, count=5)
        if not trends:
            logger.error("No trending topics found for YouTube.")
            return False
            
        # 2. Select a random trending topic from the top results to avoid repetition
        selected = random.choice(trends)
        topic = selected["topic"]
        lang = selected.get("language", "en")
        
        logger.info(f"Selected Trending Topic: {topic} (Reason: {selected['reason']})")
        
        # 3. Produce and Upload via Factory
        # YoutubeFactory.run handles research, scripting, rendering, and auto-upload
        production_id = self.factory.run(
            topic=topic,
            languages=[lang],
            auto_upload=True,
            video_type="shorts",
            mode="info"
        )
        
        if production_id:
            logger.info(f"YouTube Automation Success: {production_id}")
            return True
        else:
            logger.error("YouTube Automation Failed during production or upload.")
            return False
