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

    def generate_narrative(self, research_data, topic, language="en", mode="info"):
        """
        Step 1: Create a dramatic narrative.
        Supports 'info' (Standard) and 'horror' (Storytelling) modes.
        """
        lang_name = "English" if language == "en" else "Turkish"
        
        if mode == "horror":
            prompt = f"""
            Write a terrifying and atmospheric HORROR story for a 60-second YouTube Short.
            Everything MUST be in {lang_name}.
            
            TOPIC/THEME: {topic}
            
            STORYTELLING RULES:
            - Start with a chilling, atmospheric hook that sets the mood instantly.
            - Use sensory details (shadows, cold whispers, footsteps).
            - Build suspense rapidly and end with a disturbing twist or cliffhanger.
            - Style: Dark, mysterious, and creepy.
            - Word count: ~120-140 words (to allow for slow, dramatic pauses).
            - Language: STRICTLY {lang_name} only.
            """
        else:
            prompt = f"""
            Using the following research data, write an exciting narration script for YouTube Shorts.
            The script MUST be entirely in {lang_name}.
            
            RESEARCH DATA: {research_data}
            TOPIC: {topic}
            
            PACING & STYLE RULES:
            - Hook: Start with a powerful, TOPIC-SPECIFIC sentence that captures curiosity in 2 seconds.
            - Use simple, punchy sentences to maintain energy.
            - Tone: Energetic, professional, and slightly dramatic.
            - Target: ~130 words maximum for a 60-second video.
            - Language: STRICTLY {lang_name} only.
            """
        
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return response.text.strip()

    def generate_blueprint(self, narrative, topic, language="en", mode="info") -> VideoBlueprint:
        """
        Step 2: Scenes and Visual Intelligence.
        In horror mode, keywords are optimized for cinematic/scary visuals.
        """
        lang_name = "English" if language == "en" else "Turkish"
        style_context = "Terrifying, dark, cinematic, and atmospheric" if mode == "horror" else "Professional, engaging, and clear"
        
        prompt = f"""
        Using the provided {lang_name} narration, create a video production blueprint.
        The text and metadata MUST be in {lang_name}.
        
        STYLE: {style_context}
        NARRATION: {narrative}
        TOPIC/THEME: {topic}
        LANGUAGE: {lang_name}

        REQUIREMENTS:
        1. Break the script into meaningful scenes (each 3.5 - 5 seconds long).
        2. Assign HIGH-QUALITY English keywords for Pexels search.
           {'CRITICAL: Use dark, cinematic, horror-themed keywords.' if mode == 'horror' else ''}
        3. Generate professional YouTube Title, Description, and Tags in {lang_name}.

        JSON OUTPUT FORMAT:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Shorts Title",
            "description": "Shorts Description",
            "tags": ["tag1", "tag2"]
          }},
          "scenes": [
            {{
              "text": "The narration text for this specific scene",
              "keywords": ["cinematic", "visual", "keywords"],
              "language": "{language}"
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
