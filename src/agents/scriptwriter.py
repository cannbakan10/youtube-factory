import os
import json
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

class SceneBlueprint(BaseModel):
    text: str
    keywords: List[str]
    sfx_prompt: str = ""
    sfx_path: str = ""
    audio_path: str = ""
    subs_path: str = ""
    video_path: str = ""
    duration: float = 0.0

class VideoBlueprint(BaseModel):
    video_id: str
    metadata: dict
    music_prompt: str = ""
    music_path: str = ""
    scenes: List[SceneBlueprint]

class ScriptWriter:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash-exp"

    def generate_narrative(self, research_data, topic):
        """
        Step 1: Create a dramatic and engaging narrative in English.
        """
        prompt = f"""
        Using the following research data, write an exciting, mysterious, and high-impact narration script for YouTube Shorts.
        The script MUST be entirely in English.
        
        RESEARCH DATA: {research_data}
        TOPIC: {topic}
        
        RULES:
        - Tone: Energetic, professional, and storytelling-oriented.
        - Duration: Suitable for Shorts (approx. 50-60 seconds, 140-160 words).
        - Hook: Start with a powerful attention-grabbing first sentence.
        - Language: STRICTLY English only.
        """
        
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return response.text.strip()

    def generate_blueprint(self, narrative, topic, language="en") -> VideoBlueprint:
        """
        Step 2: Scenes and Visual Intelligence in English.
        """
        prompt = f"""
        Using the provided English narration, create a video production blueprint.
        Everything MUST be in English. No background music or SFX prompts needed.
        
        NARRATION: {narrative}
        TOPIC: {topic}
        LANGUAGE: English

        REQUIREMENTS:
        1. Break the script into meaningful scenes (each 3-5 seconds long).
        2. Assign keywords for Pexels video search (must be highly relevant English keywords).
        3. Generate YouTube metadata (Title, Description, Tags) in English.
        4. Focus on professional pacing and vocabulary.

        JSON OUTPUT FORMAT:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Shorts Title in English",
            "description": "Engaging English description with hashtags",
            "tags": ["tag1", "tag2", "english"]
          }},
          "scenes": [
            {{
              "text": "The narration text for this specific scene",
              "keywords": ["visual", "keywords", "for", "search"],
              "language": "en"
            }}
          ]
        }}
        """
        
        response = self.client.models.generate_content(
            model=self.model, 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        data = json.loads(response.text.strip())
        return VideoBlueprint(**data)
