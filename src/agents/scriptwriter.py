import os
import json
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from openai import OpenAI

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
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.client = genai.Client(api_key=self.gemini_key)
        self.oa_client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        self.model = "gemini-2.0-flash-exp"
        self.oa_model = "gpt-4o-mini"

    def generate_narrative(self, research_data, topic, language="en", mode="info"):
        """
        Step 1: Create a dramatic narrative.
        Supports 'info' (Standard) and 'horror' (Storytelling) modes.
        """
        lang_name = "English" if language == "en" else "Turkish"
        
        if mode == "horror":
            prompt = f"""
            Using the provided research about REAL terrifying events or urban legends, 
            write a spine-chilling narration for a 60-second YouTube Short. 
            The story MUST be based on the TRUE facts found in the research.
            Everything MUST be in {lang_name}.
            
            RESEARCH DATA (The Raw Horror): {research_data}
            TOPIC: {topic}
            
            STORYTELLING RULES:
            - Start with: "Did you know this actually happened?" or a similar topic-specific 'True Horror' hook.
            - Focus on the most disturbing parts of the research.
            - SENTENCE STRUCTURE (Turkish): Use standard, formal sentences. DO NOT use inverted (devrik) sentences.
            - Use a 'true crime' or 'chilling mystery' tone (not 'cheesy' fiction).
            - Word count: ~110-130 words (measured, dramatic intervals).
            - Language: STRICTLY {lang_name} only.
            """
        else:
            prompt = f"""
            Using the following research data, write an exciting narration script for YouTube Shorts.
            The script MUST be entirely in {lang_name}.
            
            RESEARCH DATA: {research_data}
            TOPIC: {topic}
            
            PACING & STYLE RULES:
            - RETENTION HOOK: Every script MUST start with a variation of: "Number 1 will absolutely shock you!" 
              (Turkish: "1 numara sizi kesinlikle şok edecek!") to keep viewers until the end.
            - COUNTDOWN STRUCTURE: If the topic involves a list (e.g., "5 reasons", "Top 3"), ALWAYS start from the HIGHEST number and count down to 1. 
              (Example: Start at 5, finish at 1). Save the most incredible part for Number 1.
            - SENTENCE STRUCTURE (Turkish): Use standard KURALLI sentences (Subject-Object-Verb). NEVER use DEVRİK (inverted) sentences; they sound unprofessional in AI narration.
            - Use simple, punchy sentences to maintain energy.
            - Tone: Energetic, professional, and slightly dramatic.
            - Target: ~130 words maximum for a 60-second video.
            - Language: STRICTLY {lang_name} only.
            """
        
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"   ⚠️ Gemini Narrative Error: {e}. Falling back to OpenAI...")
            if not self.oa_client: return None
            oa_response = self.oa_client.chat.completions.create(
                model=self.oa_model,
                messages=[{"role": "user", "content": prompt}]
            )
            return oa_response.choices[0].message.content.strip()

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
        2. CLEAN TEXT: DO NOT include stage directions, timestamps (e.g., 0:15), 
           headers (e.g., Intro:), or narrator notes in the scene "text" field. 
           Only include the EXACT sentence to be spoken.
           
        3. VISUAL INTELLIGENCE & SAFETY:
           - For RELIGIOUS topics (Dua, Mosque, etc.): Use keywords like "Mosque architecture", "Praying hands (cinematic)", "Antique Quran", "Peaceful nature", "Stars and sky". 
             NEVER use keywords like "model", "beach", "fashion" or generic "people".
           - For HISTORICAL figures (Pargalı Ibrahim, Sultan, etc.): Use "Ottoman archive", "Topkapi Palace", "Imperial architecture", "Antique portrait", "Historical museum", "16th century aesthetic".
           - GENERAL: Be specific. Instead of "Dog", use "Golden Retriever puppy playing".
           
        4. Generate professional YouTube Title, Description, and Tags in {lang_name}.

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
              "text": "ONLY THE SPOKEN TEXT. NO BRACKETS. NO DIRECTIONS.",
              "keywords": ["specific", "visual", "keywords", "in", "english"],
              "language": "{language}"
            }}
          ]
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model, 
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(response.text.strip())
        except Exception as e:
            print(f"   ⚠️ Gemini Blueprint Error: {e}. Falling back to OpenAI...")
            if not self.oa_client: return None
            oa_response = self.oa_client.chat.completions.create(
                model=self.oa_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = json.loads(oa_response.choices[0].message.content.strip())
            
        return VideoBlueprint(**data)
