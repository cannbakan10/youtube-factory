import os
import json
import re
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from openai import OpenAI
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters

logger = get_logger(__name__)


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
    GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        self.oa_client = None
        if self.openai_key:
            import httpx
            # Warn if key looks malformed (helps diagnose Connection error)
            if not (self.openai_key.startswith("sk-") or self.openai_key.startswith("sess-")):
                logger.warning(
                    f"OPENAI_API_KEY does not start with 'sk-' (starts with {self.openai_key[:6]!r}). "
                    "This may cause Connection error."
                )
            self.oa_client = OpenAI(
                api_key=self.openai_key,
                timeout=httpx.Timeout(60.0, connect=10.0),
                max_retries=3,
            )
        self.model = "gemini-2.5-flash"
        self.oa_model = "gpt-4o-mini"
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def _load_retention_feedback(self) -> Optional[str]:
        """Load retention feedback text from data/retention_insights.json if present."""
        path = os.path.join(self.project_root, "data", "retention_insights.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("source") == "analytics_api" and data.get("feedback_text"):
                return data["feedback_text"]
        except Exception as e:
            logger.warning(f"Retention feedback load failed: {e}")
        return None

    def _clean_text(self, text, language="en"):
        """Removes AI trash, stage directions, meta-commentary, and unwanted markers."""
        if not text:
            return ""
        # Remove markdown headers like ### or ##
        text = re.sub(r'#+\s*', '', text)
        # Remove stage directions like [Enerjik giriş], (15 seconds), [INTRO]
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        # Remove timestamps like 0:15, 01:20
        text = re.sub(r'\d{1,2}:\d{2}', '', text)

        # --- PRO FILTER: Remove intro/logo stage directions that sometimes leak ---
        text = re.sub(r'(?i)kısa müzik|kanal logosu|introdan sonra|fragman|hook|abone ol|like atın', '', text)

        # Remove meta-commentary (Be careful not to remove actual script content)
        text = re.sub(r'(?i)\[Video içeriği.*?\]', '', text)
        text = re.sub(r'(?i)\[Hazırlanan metin.*?\]', '', text)

        # ── CRITICAL: Remove AI self-referential meta-text ──
        # AI sometimes writes "Here's a YouTube short script..." or "Okay, get ready..."
        # These meta-instructions must NEVER be narrated in the video
        meta_patterns = [
            r"(?i)^\s*okay[,.]?\s*here'?s\s+(a|the|your|my).*?script.*?[\.!]",
            r"(?i)^\s*here'?s\s+(a|the|your|my).*?script.*?[\.!]",
            r"(?i)^\s*get\s+ready\s+for.*?[\.!]",
            r"(?i)following\s+(all\s+)?your\s+guidelines[,.]?",
            r"(?i)here'?s\s+a\s+youtube\s+short",
            r"(?i)this\s+is\s+a\s+\d+[- ]second\s+(script|video|narration)",
            r"(?i)i'?ll\s+(now\s+)?write\s+(a|the)\s+(script|narration)",
            r"(?i)let\s+me\s+(create|write|generate)\s+(a|the)",
            r"(?i)sure!?\s+(here|i)",
            r"(?i)^\s*absolutely!?",
            r"(?i)^\s*of\s+course!?",
            r"(?i)as\s+(requested|per\s+your|you\s+asked)",
            r"(?i)based\s+on\s+(the|your)\s+(research|guidelines|instructions|prompt)",
            r"(?i)following\s+(the|your)\s+(structure|format|guidelines|rules)",
            r"(?i)word\s+count[:\s]*\d+",
            r"(?i)target\s+duration",
            r"(?i)act\s+\d+\s*:",
        ]
        for pattern in meta_patterns:
            text = re.sub(pattern, '', text)

        # Remove common prefixes
        if language == "tr":
            prefixes = ["ANLATICI:", "SAHNE:", "GİRİŞ:", "SONUÇ:", "NARRATOR:", "SCENE:", "BAŞLIK:",
                        "FRAGMAN:", "HOOK:", "KAPANIŞ:", "CTA:"]
        else:
            prefixes = ["NARRATOR:", "SCENE:", "INTRO:", "OUTRO:", "CHAPTER:", "TITLE:",
                        "HOOK:", "CTA:", "TRAILER:", "ACT 1:", "ACT 2:", "ACT 3:", "ACT 4:", "ACT 5:"]

        for p in prefixes:
            text = text.replace(p, "")

        # Remove bold/italic markers
        text = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")

        # Remove lines that are just labels (e.g., single word followed by colon)
        lines = text.split('\n')
        lines = [l for l in lines if not re.match(r'^\s*[A-Z][A-Z\s]{0,20}:\s*$', l)]
        text = ' '.join(lines)

        # Final cleanup for punctuation and spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_json(self, text):
        """Resilient JSON extraction from AI response (handles markdown blocks)."""
        if not text:
            return None
        try:
            # Try direct parse
            return json.loads(text.strip())
        except Exception:
            pass

        # Try to find json block
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try to find anything between { and }
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        return None

    def generate_narrative(self, research_data, topic, language="en", mode="info", video_type="shorts", style_context=None, retention_feedback=None):
        """
        Step 1: Create a dramatic narrative.

        retention_feedback: Optional string from YouTubeAnalyticsAgent.get_retention_insights()
                            describing channel drop-off patterns. Auto-loaded from
                            data/retention_insights.json if None.
        """
        lang_map = {"en": "English", "tr": "Turkish", "es": "Spanish"}
        lang_name = lang_map.get(language, "English")
        is_long = video_type == "long"

        duration_match = re.search(r'(\d+)\s*(?:dakika|minute|dk|min|dakikalık|minutelık)', topic.lower())
        target_minutes = int(duration_match.group(1)) if duration_match else (10 if is_long else 1)
        target_word_count = target_minutes * 140 # Average narration speed

        extra_style = f"\nSTYLE CONTEXT: {style_context}\n" if style_context else ""

        # Auto-load retention feedback from disk if not passed
        if retention_feedback is None:
            retention_feedback = self._load_retention_feedback()

        prompt = self._build_narrative_prompt(
            research_data, topic, language, lang_name, mode, is_long,
            target_minutes, target_word_count, style_context, retention_feedback
        )

        try:
            narrative = self._generate_narrative_gemini(prompt, language)
            return narrative
        except Exception as e:
            logger.warning(f"Gemini narrative generation failed: {e}")
            if not self.oa_client:
                logger.error("OpenAI client not configured. Cannot generate narrative.")
                return None
            try:
                narrative = self._generate_narrative_openai(prompt, language)
                return narrative
            except Exception as oe:
                logger.error(f"OpenAI narrative generation also failed: {oe}")
                return None

    def _build_narrative_prompt(self, research_data, topic, language, lang_name, mode, is_long, target_minutes, target_word_count, style_context=None, retention_feedback=None):
        """Build the narrative prompt based on mode and video type."""
        extra_style = f"\nSTYLE CONTEXT / VIRAL STYLE TO REPLICATE:\n{style_context}\n" if style_context else ""
        retention_block = f"\n{retention_feedback}\n" if retention_feedback else ""
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

            return f"""
            Using the provided research data, write an EXHAUSTIVE and DEEP documentary-style narration script.
            This is for a VERY LONG video ({target_minutes} minutes).
            You must provide at least {target_word_count} words of high-quality narration.

            Everything MUST be in {lang_name}.
            {extra_style}
            {retention_block}
            RESEARCH DATA: {research_data}
            TOPIC: {topic}

            PRODUCTION SPECIFICATIONS:
            - TARGET DURATION: {target_minutes} minutes
            - WORD COUNT TARGET: {target_word_count} words (STRICT MINIMUM)
            - MUST COVER: History, Geography, Culture, Economy, Gastronomy, and Modern Life of {topic.split()[-1]}.

            STRUCTURE & STYLE RULES:
            - 🎞️ TRAILER/HOOK (FIRST 30 SECONDS): Start with an IRRESISTIBLE hook — a shocking fact, a mystery, or a bold claim that makes viewers NEED to keep watching. Use curiosity gaps and open loops.
            - DEEP DIVE: Divide the script into clear thematic sections (Introduction, History, Culture, etc.).
            - CONTINUOUS NARRATIVE: Avoid numbered lists. Use smooth transitions between topics.
            - ⚠️ NO TIME REVEAL & NO META-COMMENTARY: {meta_avoid}
            - STRICTLY NARRATION ONLY: Include ONLY spoken words. No scene descriptions or labels.
            - Language: STRICTLY {lang_name} only.
            
            FAILURE TO REACH {target_word_count} WORDS WILL RESULT IN PRODUCTION FAILURE. BE DETAILED.
            """
        elif mode == "horror":
            if language == "tr":
                hook_options = [
                    "Karanlıkta bir ses duyduğunuzda sakın arkınıza bakmayın...",
                    "Bu hikaye gerçek ve kimse açıklayamıyor...",
                    "Bu olaydan sonra o mahallede kimse yaşamıyor..."
                ]
            elif language == "es":
                hook_options = [
                    "Cuando escuches un ruido en la oscuridad, no mires atrás...",
                    "Esta historia es real y nadie puede explicarla...",
                    "Después de este evento, nadie vive en ese barrio..."
                ]
            else:
                hook_options = [
                    "When you hear a sound in the dark, never look back...",
                    "This story is real and no one can explain it...",
                    "After this happened, no one ever lived there again..."
                ]

            return f"""
            Using the provided research about REAL terrifying events, write a 60-second narration.
            Everything MUST be in {lang_name}.
            {extra_style}

            RESEARCH DATA: {research_data}
            TOPIC: {topic}

            STORYTELLING RULES:
            - HOOK: Start with one of these styles: {', '.join(f'"{h}"' for h in hook_options)}
            - NO INTRO: Start DIRECTLY with the story. The first sentence must send chills.
            - NO RHETORICAL QUESTIONS: After the hook, deliver facts as BOLD STATEMENTS.
            - Build DREAD: Each sentence should escalate the tension. Use short, punchy sentences.
            - SENSORY DETAILS: Describe what was seen, heard, felt. Make the viewer feel like they're THERE.
            - END with a chilling final line that lingers in the viewer's mind.
            - STRICTLY NARRATION ONLY: No brackets, no labels, no meta-text.
            - Word count: ~110-130 words.
            - Language: STRICTLY {lang_name} only.
            """
        elif mode == "quiz":
            if language == "tr":
                pause_phrase = "Düşün bakalım... Üç... İki... Bir..."
                cta = "Kaç doğru bildin? Yorumlara yaz ve abone olmayı unutma!"
            elif language == "es":
                pause_phrase = "Piénsalo... Tres... Dos... Uno..."
                cta = "¿Cuántas has acertado? ¡Comenta y suscríbete!"
            else:
                pause_phrase = "Think about it... Three... Two... One..."
                cta = "How many did you get right? Comment below and subscribe!"

            quiz_count = 7 if is_long else 4

            return f"""
            Create a fun and engaging QUIZ video script about "{topic}".
            Everything MUST be in {lang_name}.
            {extra_style}

            RESEARCH DATA: {research_data}

            QUIZ FORMAT RULES:
            - Generate exactly {quiz_count} quiz questions about "{topic}".
            - Each question MUST follow this EXACT spoken pattern:
              1. Ask the question clearly.
              2. Say EXACTLY: "{pause_phrase}"
              3. Reveal the answer with a fun fact explanation (1-2 sentences).
            - HOOK: Start with an exciting intro like "Test your knowledge!" or "How well do you know {topic}?"
            - ENDING: Finish with "{cta}"
            - Questions should go from easy to hard.
            - Make questions surprising and fun, not boring textbook trivia.
            - STRICTLY NARRATION ONLY: No brackets, no labels, no meta-text.
            - Language: STRICTLY {lang_name} only.
            - Word count: ~{target_word_count} words.
            """
        elif mode == "reddit":
            if language == "tr":
                hook_options = ["Reddit'te bir kullanıcı şunu yazdı...", "Bu hikayeyi okuyunca çenemi yerden topladım...", "İnternette okuduğum en çılgın gerçek hikaye..."]
                cta = "Bu hikaye hakkında ne düşünüyorsun? Yorumlara yaz!"
            elif language == "es":
                hook_options = ["Un usuario de Reddit publicó esto y se volvió viral...", "Esta historia te dejará sin palabras...", "La historia real más loca que he leído online..."]
                cta = "¿Qué piensas de esta historia? ¡Comenta abajo!"
            else:
                hook_options = ["A Reddit user posted this and it blew up...", "This story will leave you speechless...", "The craziest true story I've ever read online..."]
                cta = "What do you think about this story? Comment below!"

            return f"""
            Write a gripping, emotional STORYTELLING narration based on a Reddit-style true story.
            Everything MUST be in {lang_name}.
            {extra_style}

            TOPIC/THEME: {topic}
            RESEARCH DATA: {research_data}

            REDDIT STORY RULES:
            - HOOK: Start with one of these styles: {', '.join(f'"{h}"' for h in hook_options)}
            - Write as if narrating a real person's experience. Use first or third person.
            - Build TENSION: Start calm, escalate drama, deliver a twist or emotional climax.
            - Keep it conversational and raw - like someone telling a story to a friend.
            - Include realistic details that make it feel authentic.
            - NO lists, NO bullet points. Pure continuous storytelling.
            - ENDING: Wrap with reflection + "{cta}"
            - STRICTLY NARRATION ONLY: No brackets, no labels, no meta-text.
            - Language: STRICTLY {lang_name} only.
            - Word count: ~{target_word_count} words.
            """
        else:
            if language == "tr":
                climax_lead_in = "Gelelim en çarpıcı noktaya..."
                hook_techniques = """
            🎣 HOOK TEKNİKLERİ (İlk cümle MUTLAKA bunlardan biri olmalı):
            - ŞOKUN İSTATİSTİK: "Dünya nüfusunun %90'ı bunu bilmiyor..."
            - MERİK BOŞLUĞU: "Bu ülke herkesten bir şey saklıyor..."
            - TERS SEZGI: "Bilim insanları yıllarca yanılmış..."
            - YASAK BİLGİ: "Bu bilgiyi öğrenmeniz istenmiyordu..."
            - MEYDAN OKUMA: "Bunu duyduktan sonra her şeyi sorgulayacaksınız..."
            """
            elif language == "es":
                climax_lead_in = "Ahora, la parte más impactante..."
                hook_techniques = """
            🎣 HOOK TECHNIQUES (First sentence MUST use one of these):
            - SHOCKING STAT: "El 90% del mundo no sabe esto..."
            - CURIOSITY GAP: "Este país esconde algo de todos..."
            - COUNTER-INTUITIVE: "Los científicos estuvieron equivocados durante años..."
            - FORBIDDEN KNOWLEDGE: "No quieren que sepas esta información..."
            - CHALLENGE: "Después de escuchar esto, cuestionarás todo..."
            """
            else:
                climax_lead_in = "Now for the most striking part..."
                hook_techniques = """
            🎣 HOOK TECHNIQUES (First sentence MUST use one of these):
            - SHOCKING STAT: "90% of the world doesn't know this..."
            - CURIOSITY GAP: "This country is hiding something from everyone..."
            - COUNTER-INTUITIVE: "Scientists were wrong about this for decades..."
            - FORBIDDEN KNOWLEDGE: "You were never supposed to learn this..."
            - CHALLENGE: "After hearing this, you'll question everything..."
            """
            return f"""
            Using the following research data, write an exciting narration script for YouTube Shorts.
            Entirely in {lang_name}.
            {extra_style}
            {retention_block}
            TOPIC: {topic}

            ⛔ CRITICAL OUTPUT RULES (VIOLATION = IMMEDIATE REJECTION):
            - Output ONLY the words that will be SPOKEN ALOUD by a narrator.
            - NEVER start with "Here's a script" or "Okay, get ready" or any self-referential meta-text.
            - NEVER mention that this is a script, video, or YouTube content.
            - NEVER reference guidelines, word counts, acts, or production notes.
            - The VERY FIRST WORD must be the actual content hook — start talking about {topic} IMMEDIATELY.
            - NO labels like ACT 1, SCENE, HOOK, CTA, INTRO, OUTRO.
            - NO brackets, no parentheses, no stage directions.

            {hook_techniques}

            STRUCTURE & PACING RULES:
            - ⛔ NO RHETORICAL QUESTIONS: Stop asking "Did you know?" or "What if?". Deliver information as BOLD, DIRECT STATEMENTS.
            - ⏱️ INSTANT VALUE: Deliver the first mind-blowing fact within the first 10 seconds. No long setups.
            - 🎯 TITLE ALIGNMENT: The very first sentence must confirm the promise made in the title "{topic}".
            - 🧲 CURIOSITY GAP: Every sentence should make the viewer NEED to hear the next one. Use open loops.
            - 🔥 EMOTIONAL INTENSITY: Write with urgency and passion. Use power words: "shocking", "unbelievable", "terrifying", "incredible".
            - Deliver 3-5 high-information facts in rapid succession.
            - Build to a climax using "{climax_lead_in}".
            - End with a natural call to action (like, subscribe, comment).
            - Language: STRICTLY {lang_name} only.
            - Word count: 110-140 words.
            - Write as if you're a narrator speaking directly to the viewer with authority and speed.
            """

    def _generate_narrative_gemini(self, prompt, language):
        """Generate narrative using Gemini with model fallback chain."""
        if not self.client:
            raise ValueError("Gemini client not configured")

        last_err = None
        for model in self.GEMINI_MODELS:
            try:
                APIRateLimiters.gemini.wait()
                logger.info(f"Generating narrative with Gemini ({model})...")
                response = self.client.models.generate_content(model=model, contents=prompt)
                text = getattr(response, "text", None)
                if not text or not text.strip():
                    raise ValueError(f"{model} returned empty response")
                return self._clean_text(text.strip(), language=language)
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "resource_exhausted" in err_str or "quota" in err_str or "429" in err_str:
                    logger.warning(f"Gemini {model} credits exhausted, trying next model...")
                    continue
                raise
        raise last_err or RuntimeError("All Gemini models exhausted")

    @retry_with_backoff(max_retries=3, base_delay=3.0)
    def _generate_narrative_openai(self, prompt, language):
        """Generate narrative using OpenAI with retry support."""
        logger.info("Generating narrative with OpenAI fallback...")

        oa_response = self.oa_client.chat.completions.create(
            model=self.oa_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._clean_text(oa_response.choices[0].message.content.strip(), language=language)

    def generate_blueprint(self, narrative, topic, language="en", mode="info", video_type="shorts") -> VideoBlueprint:
        """
        Step 2: Scenes and Visual Intelligence.
        """
        lang_map = {"en": "English", "tr": "Turkish", "es": "Spanish"}
        lang_name = lang_map.get(language, "English")
        is_long = video_type == "long"
        scene_duration = "12.0 - 20.0 seconds" if is_long else "3.5 - 5.0 seconds"
        orientation = "LANDSCAPE (16:9)" if is_long else "PORTRAIT (9:16)"

        # Mode-specific visual keyword strategy
        if mode == "quiz":
            visual_strategy = f"""
        3. VISUAL INTELLIGENCE (KEYWORDS):
           - You MUST generate 3-5 specific visual keywords in ENGLISH for each scene.
           - For QUESTION scenes: Use keywords related to the question subject (e.g., "world map countries", "solar system planets").
           - For ANSWER/REVEAL scenes: Use keywords showing the answer visually (e.g., "Sweden flag landscape", "Jupiter close up space").
           - STRIKE RULE: Include "{topic}" in every scene's keyword list.
           - Use vivid, concrete imagery. Avoid abstract terms."""
        elif mode == "reddit":
            visual_strategy = f"""
        3. VISUAL INTELLIGENCE (KEYWORDS):
           - You MUST generate 3-5 specific visual keywords in ENGLISH for each scene.
           - Use CINEMATIC and EMOTIONAL visuals: "person walking alone city night", "dramatic sunset ocean".
           - For tense moments: "dark hallway", "rain window night", "empty road fog".
           - For emotional moments: "sunrise hope", "people hugging", "happy ending celebration".
           - Mix in satisfying/gameplay background keywords: "minecraft parkour", "subway surfers gameplay", "satisfying slime".
           - STRIKE RULE: Include "{topic}" in every scene's keyword list."""
        else:
            visual_strategy = f"""
        3. VISUAL INTELLIGENCE (KEYWORDS):
           - You MUST generate 3-5 specific visual keywords in ENGLISH for each scene.
           - STRIKE RULE: You MUST include the main TOPIC ("{topic}") in every scene's keyword list to maintain context.
           - BE SPECIFIC: If the topic is Japan, use "Japan Tokyo street" not just "City street".
           - Avoid abstract terms. Use concrete physical objects and actions."""

        style_label = {"quiz": "Quiz / Trivia", "reddit": "Reddit Story / Emotional Narrative"}.get(mode, "Documentary")

        prompt = f"""
        Using the provided {lang_name} narration, create a video production blueprint for a {orientation} video.

        STYLE: {style_label}
        FORMAT: {video_type.upper()}
        NARRATION: {narrative}
        TOPIC: {topic}

        REQUIREMENTS:
        1. Break into scenes (each {scene_duration} long).
        2. CLEAN TEXT: ONLY include the EXACT sentence to be spoken. No brackets, no notes.
        {visual_strategy}

        4. SFX: English prompts for sound effects.
        5. METADATA:
           - SEO-friendly Title, Description, Tags in {lang_name}.
           - Tags: You MUST generate AT LEAST 8 relevant, searchable tags. Include a mix of broad and niche tags.
           - Description: Write a compelling, natural description. Do NOT include any branding, credits, or "generated by" text.

        JSON OUTPUT FORMAT:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Title", "description": "Desc", "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"]
          }},
          "scenes": [
            {{
              "text": "ONLY SPOKEN TEXT",
              "keywords": ["specific", "contextual", "keywords", "including", "topic"],
              "sfx_prompt": "sfx",
              "is_trailer": false
            }}
          ]
        }}
        
        IMPORTANT: For long-form videos, ensure the JSON structure is complete and not truncated. Focus on high-impact scenes that accurately cover the narrative.
        """

        try:
            data = self._generate_blueprint_gemini(prompt)
        except Exception as e:
            logger.warning(f"Gemini blueprint generation failed: {e}")
            if not self.oa_client:
                logger.error("OpenAI client not configured. Cannot generate blueprint.")
                return None
            try:
                data = self._generate_blueprint_openai(prompt)
            except Exception as oe:
                logger.error(f"OpenAI blueprint generation also failed: {oe}")
                return None

        if data:
            for i, scene in enumerate(data.get('scenes', [])):
                scene['text'] = self._clean_text(scene.get('text', ''), language=language)
                if i == 0:
                    scene['is_trailer'] = True
            logger.info(f"Blueprint generated with {len(data.get('scenes', []))} scenes")
            return VideoBlueprint(**data)

        logger.error("Failed to extract valid JSON from blueprint response")
        return None

    def _generate_blueprint_gemini(self, prompt):
        """Generate blueprint using Gemini with model fallback chain."""
        if not self.client:
            raise ValueError("Gemini client not configured")

        last_err = None
        for model in self.GEMINI_MODELS:
            try:
                APIRateLimiters.gemini.wait()
                logger.info(f"Generating blueprint with Gemini ({model})...")
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                text = getattr(response, "text", None)
                if not text or not text.strip():
                    raise ValueError(f"{model} returned empty response")
                data = self._extract_json(text)
                if data:
                    return data
                raise ValueError(f"{model} returned non-JSON response")
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "resource_exhausted" in err_str or "quota" in err_str or "429" in err_str:
                    logger.warning(f"Gemini {model} credits exhausted, trying next model...")
                    continue
                raise
        raise last_err or RuntimeError("All Gemini models exhausted")

    @retry_with_backoff(max_retries=3, base_delay=3.0)
    def _generate_blueprint_openai(self, prompt):
        """Generate blueprint using OpenAI with retry support."""
        logger.info("Generating blueprint with OpenAI fallback...")

        oa_response = self.oa_client.chat.completions.create(
            model=self.oa_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return self._extract_json(oa_response.choices[0].message.content)
