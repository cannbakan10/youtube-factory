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
        Optimized for a MEASURED and CLEAR pace.
        """
        prompt = f"""
        Using the following research data, write an exciting narration script for YouTube Shorts.
        The script MUST be entirely in English.
        
        RESEARCH DATA: {research_data}
        TOPIC: {topic}
        
        PACING RULES:
        - Use simple, punchy sentences.
        - Avoid long, winded paragraphs that cause fast talking.
        - Tone: Energetic but professional.
        - Words: ~130 words for 60 seconds (to ensure a slower, native-like pace).
        - Hook: Start with something that halts the scroll.
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
        Everything MUST be in English.
        
        NARRATION: {narrative}
        TOPIC: {topic}
        LANGUAGE: English

        REQUIREMENTS:
        1. Break the script into meaningful scenes (each 3.5 - 5 seconds long).
        2. Assign HIGH-QUALITY English keywords for Pexels search.
        3. Generate professional YouTube Title, Description, and Tags.

        JSON OUTPUT FORMAT:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Shorts Title",
            "description": "Shorts Description",
            "tags": ["space", "facts", "short"]
          }},
          "scenes": [
            {{
              "text": "The narration text for this specific scene",
              "keywords": ["epic", "cinematic", "galaxy"],
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
