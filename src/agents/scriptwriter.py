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
    is_trailer: bool = False

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
        self.model = "gemini-2.0-flash"
        self.oa_model = "gpt-4o-mini"

    def _clean_text(self, text, language="en"):
        """Removes AI trash, stage directions, and common unwanted markers."""
        import re
        if not text: return ""
        # Remove markdown headers like ### or ##
        text = re.sub(r'#+\s*', '', text)
        # Remove stage directions like [Enerjik giriş], (15 seconds), [INTRO]
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        # Remove timestamps like 0:15, 01:20
        text = re.sub(r'\d{1,2}:\d{2}', '', text)
        
        # --- PRO FILTER: Remove intro/logo stage directions that sometimes leak ---
        text = re.sub(r'(?i)kısa müzik|kanal logosu|introdan sonra|fragman|hook|abone ol|like atın', '', text)
        
        # Remove meta-commentary
        text = re.sub(r'(?i)(\d+)\s*(dakika|kelime|dk|min|word).*?(video|anlatım|script|hazır).*?(yap|yaz|oluştur|hazır).*?(cağız|ceğiz|acağız|eceğiz|adım|dım|dık|dik)?', '', text)
        text = re.sub(r'(?i)(bu|için|toplam|yaklaşık)\s+\d+\s*(dakika|kelime|dk|min|word).*?(video|anlatım|script)', '', text)
        text = re.sub(r'(?i)(işte|burada|aşağıda)\s+\d+\s*(dakika|kelime).*?(metin|script)', '', text)
        
        # Remove common prefixes
        if language == "tr":
            prefixes = ["ANLATICI:", "SAHNE:", "GİRİŞ:", "SONUÇ:", "NARRATOR:", "SCENE:", "BAŞLIK:"]
        else:
            prefixes = ["NARRATOR:", "SCENE:", "INTRO:", "OUTRO:", "CHAPTER:", "TITLE:"]
            
        for p in prefixes:
            text = text.replace(p, "")
            
        # Remove bold/italic markers
        text = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
        
        # Final cleanup for punctuation and spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_json(self, text):
        """Resilient JSON extraction from AI response (handles markdown blocks)."""
        import re
        if not text: return None
        try:
            # Try direct parse
            return json.loads(text.strip())
        except:
            # Try to find json block
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                try: return json.loads(match.group(1))
                except: pass
            
            # Try to find anything between { and }
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                try: return json.loads(match.group(1))
                except: pass
        return None

    def generate_narrative(self, research_data, topic, language="en", mode="info", video_type="shorts"):
        """
        Step 1: Create a dramatic narrative.
        """
        lang_name = "English" if language == "en" else "Turkish"
        is_long = video_type == "long"
        
        import re
        duration_match = re.search(r'(\d+)\s*(dakika|minute|dk|min)', topic.lower())
        target_minutes = int(duration_match.group(1)) if duration_match else (8 if is_long else 1)
        target_word_count = target_minutes * 150
        
        if is_long:
            if language == "tr":
                structure_rule = "SENTENCE STRUCTURE (Turkish): Standard KURALLI sentences only."
                meta_avoid = """
                  1. NEVER mention specific numbers about the video length.
                  2. NEVER mention target word counts.
                  3. USE natural transitions.
                """
            else:
                structure_rule = f"SENTENCE STRUCTURE ({lang_name}): Professional documentary-style grammar."
                meta_avoid = f"""
                  1. NEVER mention specific numbers about the video length.
                  2. NEVER mention target word counts.
                  3. USE natural transitions.
                """

            prompt = f"""
            Using the provided research data, write a DEEP and ENGAGING documentary-style narration script.
            Everything MUST be in {lang_name}.
            
            RESEARCH DATA: {research_data}
            TOPIC: {topic}
            
            PRODUCTION SPECIFICATIONS:
            - TARGET PACING: {target_minutes} minutes
            - WORD COUNT TARGET: {target_word_count} words
            
            STRUCTURE & STYLE RULES:
            - 🎞️ TRAILER/HOOK (FIRST 15 SECONDS): Start with a fast-paced, gripping summary.
            - CONTINUOUS NARRATIVE: Avoid numbered lists.
            - INTRO: High-energy hook. Start DIRECTLY with the topic after the trailer.
            - ⚠️ NO TIME REVEAL & NO META-COMMENTARY: {meta_avoid}
            - STRICTLY NARRATION ONLY: Include ONLY spoken words. No meta-talk.
            - Language: STRICTLY {lang_name} only.
            """
        elif mode == "horror":
            hook_start = "Bunun gerçekten yaşandığını biliyor muydunuz?" if language == "tr" else "Did you know this actually happened?"
            prompt = f"""
            Using the provided research about REAL terrifying events, write a 60-second narration.
            Everything MUST be in {lang_name}.
            
            STORYTELLING RULES:
            - Start with: "{hook_start}"
            - NO INTRO: Start DIRECTLY with the story.
            - Word count: ~110-130 words.
            - Language: STRICTLY {lang_name} only.
            """
        else:
            climax_lead_in = "Gelelim en çarpıcı noktaya..." if language == "tr" else "Now for the most striking part..."
            prompt = f"""
            Using the following research data, write an exciting narration script for YouTube Shorts.
            Entirely in {lang_name}.
            
            TOPIC: {topic}
            
            STRUCTURE & PACING RULES:
            - 🎞️ ACT 1: FRAGMAN / HOOK (MANDATORY): Start with a unique hook directly related to "{topic}".
            - 🎬 ACT 2: INTRO TRANSITION: Naturally lead into a short pause for the branding intro.
            - 📖 ACT 3: INFORMATION BODY: Continuous narrative, facts, NO numbered lists.
            - 🔥 ACT 4: THE CLIMAX & WRAP: End with shock using "{climax_lead_in}".
            - 🏁 ACT 5: OUTRO / CTA: The VERY LAST sentence MUST be like, subscribe, comment.
            - Language: STRICTLY {lang_name} only.
            - ⚠️ WARNING: DO NOT include meta-labels like [Kısa Müzik] or [Logo].
            """
        
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            return self._clean_text(response.text.strip(), language=language)
        except Exception as e:
            if not self.oa_client: return None
            oa_response = self.oa_client.chat.completions.create(model=self.oa_model, messages=[{"role": "user", "content": prompt}])
            return self._clean_text(oa_response.choices[0].message.content.strip(), language=language)

    def generate_blueprint(self, narrative, topic, language="en", mode="info", video_type="shorts") -> VideoBlueprint:
        """
        Step 2: Scenes and Visual Intelligence.
        """
        lang_name = "English" if language == "en" else "Turkish"
        is_long = video_type == "long"
        scene_duration = "6.0 - 10.0 seconds" if is_long else "3.5 - 5.0 seconds"
        orientation = "LANDSCAPE (16:9)" if is_long else "PORTRAIT (9:16)"
        
        prompt = f"""
        Using the provided {lang_name} narration, create a video production blueprint for a {orientation} video.
        
        STYLE: Documentary
        FORMAT: {video_type.upper()}
        NARRATION: {narrative}
        TOPIC: {topic}
        
        REQUIREMENTS:
        1. Break into scenes (each {scene_duration} long).
        2. CLEAN TEXT: ONLY include the EXACT sentence to be spoken. No brackets, no notes.
        3. VISUALS: Match keywords to narrative.
        4. SFX: English prompts for sound effects.
        5. METADATA: SEO-friendly Title, Description, Tags in {lang_name}.
        
        JSON OUTPUT FORMAT:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Title", "description": "Desc", "tags": []
          }},
          "scenes": [
            {{
              "text": "ONLY SPOKEN TEXT",
              "keywords": ["keywords"],
              "sfx_prompt": "sfx",
              "is_trailer": false
            }}
          ]
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt, config={'response_mime_type': 'application/json'}
            )
            data = self._extract_json(response.text)
        except Exception as e:
            if not self.oa_client: return None
            oa_response = self.oa_client.chat.completions.create(
                model=self.oa_model, messages=[{"role": "user", "content": prompt}], response_format={ "type": "json_object" }
            )
            data = self._extract_json(oa_response.choices[0].message.content)
            
        if data:
            for i, scene in enumerate(data.get('scenes', [])):
                scene['text'] = self._clean_text(scene.get('text', ''), language=language)
                if i == 0: scene['is_trailer'] = True
            return VideoBlueprint(**data)
        return None
