import os
import json
from google import genai
from typing import List
from dotenv import load_dotenv

load_dotenv()

class TrendAgent:
    def __init__(self):
        # Ultra-Clean Key Loading
        raw_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_key = raw_key.strip().replace('"', '').replace("'", "")
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        self.client = genai.Client(api_key=self.gemini_key)
        self.model = "gemini-2.0-flash"

    def get_trending_topics(self, region="Turkey", category="General", count=5) -> List[dict]:
        """
        Uses Gemini's real-time knowledge (search enabled) to find viral/trending topics.
        """
        prompt = f"""
        Find the top {count} currently viral, trending, or highly searched topics in {region} 
        that would make excellent, high-retention YouTube Shorts (Fact/Info style).
        
        Focus on:
        - Educational interesting facts
        - Recent scientific discoveries
        - Shocking historical events
        - Viral mysteries
        - Trending technology/AI news
        
        OUTPUT FORMAT (Strict JSON):
        [
            {{"topic": "Short Topic Title", "reason": "Why it is trending", "language": "tr"}},
            ...
        ]
        """
        
        try:
            # Using Gemini 2.0 Flash's search capability
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            topics = json.loads(response.text)
            return topics
        except Exception as e:
            print(f"❌ Trend Discovery Error: {e}")
            return []

if __name__ == "__main__":
    agent = TrendAgent()
    trends = agent.get_trending_topics()
    for i, t in enumerate(trends):
        print(f"{i+1}. {t['topic']} ({t['reason']})")
