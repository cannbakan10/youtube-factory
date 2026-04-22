from elevenlabs.client import ElevenLabs
from openai import OpenAI
import os
import time
import uuid
import subprocess
import base64
import random
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters

logger = get_logger(__name__)


class TTSService:
    def __init__(self, output_dir="assets/cache"):
        # Ultra-Clean Key Loading: Strips quotes and newlines that cause header errors
        raw_key = os.getenv("ELEVENLABS_API_KEY", "")
        api_key = raw_key.strip().replace('"', '').replace("'", "")
        self.client = ElevenLabs(api_key=api_key)
        
        # OpenAI Fallback Client
        oa_key = os.getenv("OPENAI_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.oa_client = OpenAI(api_key=oa_key) if oa_key else None
        
        self.cache_dir = output_dir
        self.elevenlabs_quota_exceeded = False
        self._quota_exceeded_at = None

        # Audio Library (Not cleaned every run)
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.library_dir = os.path.join(self.project_root, "assets", "library", "music")

        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.library_dir, exist_ok=True)

        # Language-Specific Voice Settings (Optimized for Prosody)
        self.voices_config = {
            "tr": {
                "male": ["uvU9jrgGLWNPeNA4NgNT", "NNn9dv8zq2kUo7d3JSGG"],
                "female": ["bj1uMlYGikistcXNmFoh"],
                "default": "uvU9jrgGLWNPeNA4NgNT"
            },
            "en": {
                "male": ["XfNU2rGpBa01ckF309OY", "pNInz6ob8mW8mY4Rnd87"],
                "female": ["XfNU2rGpBa01ckF309OY", "EXAVITQu4vr4xnSDxMaL"],
                "default": "XfNU2rGpBa01ckF309OY"
            },
            "es": {
                "male": ["pNInz6ob8mW8mY4Rnd87", "TX380q0664cnvofS9ntW"], # Adam, etc
                "female": ["z9fAnlkUCvXgqy7Df9uJ"], # Glinda
                "default": "z9fAnlkUCvXgqy7Df9uJ"
            }
        }

        # Voice rotation pool for variety (English & Spanish)
        # Each voice has optimal use cases to avoid monotony
        self.voice_pool = {
            "narrator": "XfNU2rGpBa01ckF309OY",       # Default narrator
            "deep": "pNInz6ob8mW8mY4Rnd87",            # Deep voice
            "energetic": "XfNU2rGpBa01ckF309OY",       # Energetic
            "calm": "EXAVITQu4vr4xnSDxMaL",            # Calm female
        }

        self.current_voice_id = self.voices_config["en"]["default"]
        # Upgraded to Turbo v2.5 - Much more natural for Turkish and faster
        self.model_id = "eleven_turbo_v2_5"

    def set_voice(self, language="en", gender=None, voice_id=None):
        """Sets the voice based on language and preferences."""
        lang_cfg = self.voices_config.get(language, self.voices_config["en"])

        if voice_id:
            self.current_voice_id = voice_id
        elif gender and gender in lang_cfg:
            self.current_voice_id = random.choice(lang_cfg[gender])
        else:
            self.current_voice_id = lang_cfg["default"]

        logger.info(f"Voice selected -> {self.current_voice_id} ({language.upper()})")

    def set_voice_for_content(self, topic="", mode="info", language="en"):
        """
        Intelligently select voice based on content type and topic.
        Prevents monotony by matching voice character to content.
        """
        if language != "en":
            # For non-English, use language default
            self.set_voice(language=language)
            return

        topic_lower = topic.lower()

        # Mode-based selection
        if mode in ("horror", "mystery"):
            voice_key = "deep"
        elif mode == "quiz":
            voice_key = "energetic"
        elif mode in ("nature", "ambient"):
            voice_key = "calm"
        # Topic-based fallback
        elif any(w in topic_lower for w in ["sleep", "rain", "relax", "calm", "asmr", "ambient", "peaceful"]):
            voice_key = "calm"
        elif any(w in topic_lower for w in ["mystery", "dark", "unknown", "creepy", "unexplained"]):
            voice_key = "deep"
        elif any(w in topic_lower for w in ["fun", "amazing", "incredible", "mind", "blow"]):
            voice_key = "energetic"
        else:
            voice_key = "narrator"

        self.current_voice_id = self.voice_pool.get(voice_key, self.voice_pool["narrator"])
        logger.info(f"Voice matched -> {voice_key} ({self.current_voice_id}) for '{topic[:30]}'")


    def generate_audio_with_subtitles(self, text, language="en", mode="info"):
        """
        Hyper-Sync Edition: Uses ElevenLabs Timestamps for perfect alignment.
        Now with smart quota failover to OpenAI.
        """
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")

        clean_text = text.strip()

        if self.elevenlabs_quota_exceeded:
            if self._quota_exceeded_at and (time.time() - self._quota_exceeded_at) > 3600:
                logger.info("ElevenLabs quota cooldown expired (1h). Retrying ElevenLabs...")
                self.elevenlabs_quota_exceeded = False
                self._quota_exceeded_at = None
            else:
                if self.oa_client:
                    return self._generate_with_openai(clean_text, language)
                return None, None, 0

        # Mode-aware voice settings for maximum engagement
        voice_presets = {
            "tr": {
                "info":   {"stability": 0.45, "style": 0.35},
                "horror": {"stability": 0.35, "style": 0.50},
                "quiz":   {"stability": 0.50, "style": 0.40},
                "reddit": {"stability": 0.38, "style": 0.48},
            },
            "en": {
                "info":   {"stability": 0.58, "style": 0.30},
                "horror": {"stability": 0.40, "style": 0.50},
                "quiz":   {"stability": 0.55, "style": 0.35},
                "reddit": {"stability": 0.42, "style": 0.45},
            },
            "es": {
                "info":   {"stability": 0.50, "style": 0.30},
                "horror": {"stability": 0.38, "style": 0.48},
                "quiz":   {"stability": 0.52, "style": 0.38},
                "reddit": {"stability": 0.40, "style": 0.45},
            },
        }
        lang_presets = voice_presets.get(language, voice_presets["en"])
        preset = lang_presets.get(mode, lang_presets["info"])
        stability = preset["stability"]
        style = preset["style"]

        try:
            # We don't use @retry decorator on internal methods anymore
            # so we can catch quota errors immediately.
            result = self._generate_with_timestamps(
                clean_text, audio_path, subs_path, stability, style, language
            )
            return result
        except Exception as e:
            err_msg = str(e).lower()
            if "quota_exceeded" in err_msg or "status_code: 401" in err_msg:
                logger.warning("💎 ElevenLabs Quota EXCEEDED. Switching to OpenAI fallback (retry in 1h).")
                self.elevenlabs_quota_exceeded = True
                self._quota_exceeded_at = time.time()
            
            logger.info(f"ElevenLabs primary method failed (Reason: {e}). Attempting fallback...")
            
            if self.elevenlabs_quota_exceeded or "quota_exceeded" in err_msg:
                if self.oa_client:
                    return self._generate_with_openai(clean_text, language)
                return None, None, 0

            # Last-ditch ElevenLabs retry (no timestamps)
            res = self._generate_audio_fallback_retry(clean_text, language)
            if res[0]:
                return res
            
            if self.oa_client:
                return self._generate_with_openai(clean_text, language)
            
            return None, None, 0

    @retry_with_backoff(max_retries=1, base_delay=1.0) # Reduced retries for faster failover
    def _generate_with_timestamps(self, text, audio_path, subs_path, stability, style, language):
        """Generate audio with timestamps - with retry support."""
        # Rate limiting
        APIRateLimiters.elevenlabs.wait()

        logger.info(f"[ElevenLabs V2.5]: Narrating ({language.upper()}) | Stability: {stability} | Style: {style}")

        response = self.client.text_to_speech.convert_with_timestamps(
            voice_id=self.current_voice_id,
            text=text,
            model_id=self.model_id,
            voice_settings={
                "stability": stability,
                "similarity_boost": 0.75,
                "style": style,
                "use_speaker_boost": True
            }
        )

        audio_bytes = base64.b64decode(response.audio_base_64)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        # Added a tiny padding to the end of the audio using FFmpeg to avoid abrupt cuts
        padded_audio_path = audio_path.replace(".mp3", "_padded.mp3")
        pad_cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-af", "apad=pad_dur=0.8",
            padded_audio_path
        ]
        result = subprocess.run(pad_cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and os.path.exists(padded_audio_path):
            os.replace(padded_audio_path, audio_path)

        alignment = response.alignment
        # Grouping 2 words at a time for even smaller, more readable lines
        self._alignment_to_srt_grouped(alignment, subs_path, words_per_chunk=2)

        duration = self._get_duration(audio_path)
        return audio_path, subs_path, duration

    def _alignment_to_srt_grouped(self, alignment, subs_path, words_per_chunk=2):
        chars = alignment.characters
        starts = alignment.character_start_times_seconds
        ends = alignment.character_end_times_seconds

        words = []
        current_word = ""
        word_start = 0.0

        for i in range(len(chars)):
            char = chars[i]
            if char == " " or i == len(chars) - 1:
                if i == len(chars) - 1 and char != " ":
                    current_word += char
                if current_word:
                    words.append({
                        "text": current_word.strip().upper(),
                        "start": word_start,
                        "end": ends[i]
                    })
                    current_word = ""
                word_start = starts[i + 1] if i + 1 < len(starts) else (ends[i] if i < len(ends) else 0)
            else:
                if not current_word:
                    word_start = starts[i]
                current_word += char

        chunks = []
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            if not chunk_words:
                continue
            combined_text = " ".join([w["text"] for w in chunk_words])
            chunks.append({
                "text": combined_text,
                "start": chunk_words[0]["start"],
                "end": chunk_words[-1]["end"]
            })

        with open(subs_path, "w", encoding="utf-8") as f:
            for i, chunk in enumerate(chunks):
                f.write(f"{i + 1}\n{self._format_srt_time(chunk['start'])} --> {self._format_srt_time(chunk['end'])}\n{chunk['text']}\n\n")

    def _generate_audio_fallback_retry(self, text, language="en"):
        """Fallback method without timestamps."""
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")

        try:
            # Rate limiting
            APIRateLimiters.elevenlabs.wait()

            logger.info(f"Using ElevenLabs fallback for {language.upper()}")
            audio_generator = self.client.text_to_speech.convert(
                voice_id=self.current_voice_id,
                text=text,
                model_id=self.model_id
            )
            with open(audio_path, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)

            duration = self._get_duration(audio_path)
            self._generate_simple_subtitles(text, subs_path, duration)
            return audio_path, subs_path, duration

        except Exception as e:
            logger.error(f"ElevenLabs fallback failed: {e}")
            return None, None, 0

    def _generate_with_openai(self, text, language="en"):
        """Emergency fallback using OpenAI TTS."""
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")

        # Map voices roughly
        oa_voice = "onyx" if language == "tr" else "alloy" 
        if language == "es":
            oa_voice = "shimmer" # More natural for Spanish
        # alloy, echo, fable, onyx, nova, shimmer
        
        try:
            logger.info(f"🚀 [OpenAI TTS]: Narrating using '{oa_voice}'...")
            response = self.oa_client.audio.speech.create(
                model="tts-1",
                voice=oa_voice,
                input=text
            )
            response.stream_to_file(audio_path)
            
            duration = self._get_duration(audio_path)
            self._generate_simple_subtitles(text, subs_path, duration)
            
            return audio_path, subs_path, duration
        except Exception as e:
            logger.error(f"OpenAI TTS fallback also failed: {e}")
            return None, None, 0

    def _generate_simple_subtitles(self, text, subs_path, duration):
        """Helper to generate basic time-based SRT."""
        words = text.split()
        chunks = [" ".join(words[i:i + 2]) for i in range(0, len(words), 2)]
        with open(subs_path, "w", encoding="utf-8") as f:
            for i, c in enumerate(chunks):
                t = (i / len(chunks)) * duration
                next_t = ((i + 1) / len(chunks)) * duration
                f.write(f"{i + 1}\n{self._format_srt_time(t)} --> {self._format_srt_time(next_t)}\n{c.upper()}\n\n")

    def generate_sfx(self, prompt, duration_seconds=None):
        """Generates a custom sound effect using ElevenLabs AI."""
        if not prompt or prompt.lower() == "none":
            return None

        id = str(uuid.uuid4())
        sfx_path = os.path.join(self.cache_dir, f"sfx_{id}.mp3")

        try:
            # Rate limiting
            APIRateLimiters.elevenlabs.wait()

            logger.info(f"[ElevenLabs SFX]: Generating '{prompt}'...")

            # The correct method in the SDK 2.x is text_to_sound_effects.convert
            # It returns an iterator of bytes
            iterator = self.client.text_to_sound_effects.convert(
                text=prompt,
                duration_seconds=duration_seconds
            )

            with open(sfx_path, "wb") as f:
                for chunk in iterator:
                    f.write(chunk)

            if os.path.exists(sfx_path):
                logger.info(f"[SFX SUCCESS]: Created '{prompt}'")
                return sfx_path

        except Exception as e:
            logger.error(f"ElevenLabs SFX Error: {e}")

        return None

    def generate_music(self, prompt):
        return None

    def _get_duration(self, audio_path):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
            return 0.0

    def _format_srt_time(self, seconds):
        td_hours, td_minutes = int(seconds // 3600), int((seconds % 3600) // 60)
        td_seconds, td_millis = int(seconds % 60), int((seconds % 1) * 1000)
        return f"{td_hours:02}:{td_minutes:02}:{td_seconds:02},{td_millis:03}"
