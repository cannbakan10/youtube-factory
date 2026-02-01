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
        # Remove meta-commentary
        text = re.sub(r'(?i)(\d+)\s*(dakika|kelime|dk|min|word).*?(video|anlatım|script|hazır).*?(yap|yaz|oluştur|hazır).*?(cağız|ceğiz|acağız|eceğiz|adım|dım|dık|dik)?', '', text)
        text = re.sub(r'(?i)(bu|için|toplam|yaklaşık)\s+\d+\s*(dakika|kelime|dk|min|word).*?(video|anlatım|script)', '', text)
        text = re.sub(r'(?i)(işte|burada|aşağıda)\s+\d+\s*(dakika|kelime).*?(metin|script)', '', text)
        
        # Remove common prefixes
        if language == "tr":
            prefixes = ["ANLATICI:", "SAHNE:", "GİRİŞ:", "SONUÇ:", "NARRATOR:", "SCENE:"]
        else:
            prefixes = ["NARRATOR:", "SCENE:", "INTRO:", "OUTRO:", "CHAPTER:"]
            
        for p in prefixes:
            text = text.replace(p, "")
        # Remove bold/italic markers
        text = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
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
        Supports 'info', 'horror' and now 'long' modes with dynamic duration detection.
        """
        lang_name = "English" if language == "en" else "Turkish"
        is_long = video_type == "long"
        
        # Dynamic Duration Detection
        import re
        duration_match = re.search(r'(\d+)\s*(dakika|minute|dk|min)', topic.lower())
        target_minutes = int(duration_match.group(1)) if duration_match else (8 if is_long else 1)
        
        # Word count calculation: 1 minute of speech is roughly 150 words for a standard documentary pace.
        target_word_count = target_minutes * 150
        
        if is_long:
            # Language-specific warnings
            if language == "tr":
                structure_rule = "SENTENCE STRUCTURE (Turkish): Standard KURALLI sentences only."
                meta_avoid = """
                  1. NEVER mention specific numbers about the video length (AVOID "Bu 8 dakikalık videoda").
                  2. NEVER mention target word counts (AVOID "1200 kelimelik video").
                  3. USE natural transitions like "Şimdilik bu yolculuğun sonuna geldik."
                """
            else:
                structure_rule = f"SENTENCE STRUCTURE ({lang_name}): Professional documentary-style grammar."
                meta_avoid = f"""
                  1. NEVER mention specific numbers about the video length (AVOID "In this {target_minutes} minute video").
                  2. NEVER mention target word counts (AVOID "This {target_word_count} word script").
                  3. USE natural transitions like "That's all for now," or "What do you think about this?"
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
            - 🎞️ TRAILER/HOOK (FIRST 15 SECONDS): Start with a fast-paced, gripping summary or a shocking question.
              This is the "TRAILER/FRAGMAN". It should end with a natural pause for a branding transition.
            - INTRO: High-energy hook. Start DIRECTLY with the topic after the trailer.
            - CHAPTERS: Break the topic into logical sections.
            - TRANSITIONS: Use smooth verbal transitions. 
            - ⚠️ NO TIME REVEAL & NO META-COMMENTARY:
              {meta_avoid}
            - STRICTLY NARRATION ONLY: Include ONLY the words to be spoken. No meta-talk, no narrator notes.
            - DEPTH: Provide interesting details. You MUST expand on the research to reach the {target_word_count} word mark.
            - PACING: Varied sentence lengths.
            - {structure_rule}
            - CONVERSATIONAL PUNCTUATION: Use ! and ...
            - Language: STRICTLY {lang_name} only.
            """
        elif mode == "horror":
            if language == "tr":
                hook_start = "Bunun gerçekten yaşandığını biliyor muydunuz?"
                structure_rule = "SENTENCE STRUCTURE (Turkish): Standart, resmi cümleler kullanın. DEVRİK cümlelerden kaçının."
            else:
                hook_start = "Did you know this actually happened?"
                structure_rule = f"SENTENCE STRUCTURE ({lang_name}): Natural, formal storytelling grammar."

            prompt = f"""
            Using the provided research about REAL terrifying events or urban legends, 
            write a spine-chilling narration for a 60-second YouTube Short. 
            Everything MUST be in {lang_name}.
            
            STORYTELLING RULES:
            - Start with: "{hook_start}" or a similar hook.
            - NO INTRO: Do NOT say "Here is a script". Start DIRECTLY with the story.
            - Focus on the most disturbing parts of the research.
            - {structure_rule}
            - Use a 'true crime' or 'chilling mystery' tone.
            - Word count: ~110-130 words.
            - Language: STRICTLY {lang_name} only.
            """
        else:
            hook_pattern = "[TOPIC] Hakkında bunları biliyor muydunuz?" if language == "tr" else "Did you know these facts about [TOPIC]?"
            countdown_prefix = "numara" if language == "tr" else "Number"
            climax_lead_in = "Gelelim en çılgın gerçeğe..." if language == "tr" else "Now for the most insane fact..."
            
            prompt = f"""
            Using the following research data, write an exciting narration script for YouTube Shorts.
            The script MUST be entirely in {lang_name}.
            
            STRUCTURE & PACING RULES:
            - 🎞️ FRAGMAN / HOOK (MANDATORY): Start EVERY video with a gripping hook. 
              Pattern: "{hook_pattern}" 
              (Example: "Did you know these mysterious facts about Antarctica?")
              This MUST be a separate first sentence/scene.
            - INTRO TRANSITION: The script should lead naturally into a short branding pause after the hook.
            - STRICT 5-STEP COUNTDOWN: You MUST list exactly 5 facts. Start from "5 {countdown_prefix}" and count down sequentially to "1 {countdown_prefix}".
            - NO META-TALK: Do NOT include titles, headers, or instructions. Start DIRECTLY with the hook.
            - THE #1 CLIMAX: 1 {countdown_prefix} MUST be the most shocking fact. Use dramatic lead-ins like "{climax_lead_in}"
            - RETENTION FOCUS: Keep sentences short, punchy, and fast-paced to prevent scrolling.
            - SENTENCE STRUCTURE ({lang_name}): Use standard professional sentences.
            - CONVERSATIONAL PUNCTUATION: Use exclamation marks (!) and ellipses (...) to force the AI to take breaths.
            - EMPHASIS: Use words that trigger emphasis for Number 1.
            - Tone: Energetic, professional, and slightly dramatic.
            - Target: ~130-140 words maximum for a 60-second video.
            - Language: STRICTLY {lang_name} only.
            """
        
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt
            )
            return self._clean_text(response.text.strip(), language=language)
        except Exception as e:
            print(f"   ⚠️ Gemini Narrative Error: {e}. Falling back to OpenAI...")
            if not self.oa_client: return None
            oa_response = self.oa_client.chat.completions.create(
                model=self.oa_model,
                messages=[{"role": "user", "content": prompt}]
            )
            return self._clean_text(oa_response.choices[0].message.content.strip(), language=language)

    def generate_blueprint(self, narrative, topic, language="en", mode="info", video_type="shorts") -> VideoBlueprint:
        """
        Step 2: Scenes and Visual Intelligence.
        Supports both Shorts (Vertical) and Long (Landscape) formats.
        """
        lang_name = "English" if language == "en" else "Turkish"
        is_long = video_type == "long"
        style_context = "Terrifying, dark, cinematic, and atmospheric" if mode == "horror" else "Professional, engaging, and documentary-like"
        scene_duration = "6.0 - 10.0 seconds" if is_long else "3.5 - 5.0 seconds"
        orientation = "LANDSCAPE (16:9)" if is_long else "PORTRAIT (9:16)"
        
        prompt = f"""
        Using the provided {lang_name} narration, create a video production blueprint for a {orientation} video.
        The text and metadata MUST be in {lang_name}.
        
        STYLE: {style_context}
        FORMAT: {video_type.upper()}
        NARRATION: {narrative}
        TOPIC/THEME: {topic}
        LANGUAGE: {lang_name}

        REQUIREMENTS:
        1. Break the script into meaningful scenes (each {scene_duration} long).
        2. CLEAN TEXT: DO NOT include stage directions, timestamps, headers, 
           narrator notes, or meta-commentary. 
           ONLY include the EXACT sentence to be spoken.
           
        3. VISUAL INTELLIGENCE & SAFETY:
           - FORMAT: All keywords should aim for {orientation} visuals.
           - For RELIGIOUS topics: Use architectural/nature keywords. No people unless historic/archival feel.
           - DOCUMENTARY STYLE: Use specific keywords that match the narrative depth.
           - GENERAL: Be specific. Instead of "Dog", use "Golden Retriever puppy playing".
        
        4. AUDIO INTELLIGENCE (SFX):
           - Generate a matching "sfx_prompt" (in English) for each scene.
           - Examples: "cinematic whoosh", "nature ambience", "city traffic hum", "soft piano note".
           - Use "none" if not needed.
           
        5. METADATA & SEO:
           - Generate professional YouTube Title, Description, and Tags in {lang_name}.
           - TITLE RULES: 
             - If format is SHORTS (9:16): Create a viral, high-energy title.
             - If format is LONG (16:9): Create a professional, educational documentary-style title. 
               ⚠️ ZERO TOLERANCE: For LONG videos, you MUST NOT use the word "Shorts" ANYWHERE (Title, Description, Tags).
           - TAG RULES: 
             - If format is SHORTS: Include #Shorts and viral niche tags.
             - If format is LONG: DO NOT use #Shorts. Use deep context tags like #Documentary, #Geopolitics, #History, #Education and topic-specific tags.

        JSON OUTPUT FORMAT:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Video Title",
            "description": "Video Description",
            "tags": ["tag1", "tag2"]
          }},
          "scenes": [
            {{
              "text": "ONLY THE SPOKEN TEXT. NO BRACKETS. NO DIRECTIONS.",
              "keywords": ["specific", "visual", "keywords", "in", "english"],
              "sfx_prompt": "sound effect description in english",
              "is_trailer": true
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
            data = self._extract_json(response.text)
        except Exception as e:
            print(f"   ⚠️ Gemini Blueprint Error: {e}. Falling back to OpenAI...")
            if not self.oa_client: return None
            oa_response = self.oa_client.chat.completions.create(
                model=self.oa_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            data = self._extract_json(oa_response.choices[0].message.content)
            
        if data:
            # Final cleanup of all scene texts in the blueprint
            for i, scene in enumerate(data.get('scenes', [])):
                scene['text'] = self._clean_text(scene.get('text', ''), language=language)
                # Force the first scene to be a trailer for branding transition
                if i == 0:
                    scene['is_trailer'] = True
            return VideoBlueprint(**data)
        return None
