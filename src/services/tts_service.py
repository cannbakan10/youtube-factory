from elevenlabs.client import ElevenLabs
import os
import uuid
import subprocess
import json
import base64
import random
import hashlib

class TTSService:
    def __init__(self, output_dir="assets/cache"):
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.client = ElevenLabs(api_key=api_key)
        self.cache_dir = output_dir
        
        # Audio Library (Not cleaned every run)
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.library_dir = os.path.join(self.project_root, "assets", "library", "music")
        
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.library_dir, exist_ok=True)
        
        # Language-Specific Voice Settings (Optimized for Prosody)
        self.voices_config = {
            "tr": {
                # 'z2ObNnp0E5ZGeTlSXkX0' is Mert Aksoy (Verified available)
                # '6H6FG7kAHiOf7LXnwus7' is Cahit (Verified available)
                "male": ["z2ObNnp0E5ZGeTlSXkX0", "6H6FG7kAHiOf7LXnwus7"],
                "female": ["bj1uMlYGikistcXNmFoh"],
                "default": "z2ObNnp0E5ZGeTlSXkX0" 
            },
            "en": {
                "male": ["XfNU2rGpBa01ckF309OY", "pNInz6ob8mW8mY4Rnd87"],
                "female": ["XfNU2rGpBa01ckF309OY", "EXAVITQu4vr4xnSDxMaL"],
                "default": "XfNU2rGpBa01ckF309OY"
            }
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
        
        print(f"      🎭 [TTSService]: Voice selected -> {self.current_voice_id} ({language.upper()})")

    def generate_audio_with_subtitles(self, text, language="en"):
        """
        Hyper-Sync Edition: Uses ElevenLabs Timestamps for perfect alignment.
        """
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        
        clean_text = text.strip()
        
        # Adaptive Voice Settings: Turkish needs more emotional soul (lower stability, higher style)
        if language == "tr":
            stability = 0.45 # Lower stability = More variance/pitch/emotion
            style = 0.35     # Higher style = More expressive delivery
        else:
            stability = 0.70 # English is more stable at high settings
            style = 0.10
            
        try:
            print(f"      🎙️ [ElevenLabs V2.5]: Narrating ({language.upper()}) | Stability: {stability} | Style: {style}")
            
            response = self.client.text_to_speech.convert_with_timestamps(
                voice_id=self.current_voice_id,
                text=clean_text,
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
                "-af", "apad=pad_dur=0.3", 
                padded_audio_path
            ]
            subprocess.run(pad_cmd, capture_output=True)
            if os.path.exists(padded_audio_path):
                os.replace(padded_audio_path, audio_path)

            alignment = response.alignment
            # Grouping 2 words at a time for even smaller, more readable lines
            self._alignment_to_srt_grouped(alignment, subs_path, words_per_chunk=2)
            
            duration = self._get_duration(audio_path)
            return audio_path, subs_path, duration
                    
        except Exception as e:
            print(f"      ❌ ElevenLabs Error: {e}. Attempting fallback...")
            return self._generate_audio_fallback_retry(clean_text)

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
                if i == len(chars) - 1 and char != " ": current_word += char
                if current_word:
                    words.append({
                        "text": current_word.strip().upper(), 
                        "start": word_start, 
                        "end": ends[i]
                    })
                    current_word = ""
                word_start = starts[i+1] if i+1 < len(starts) else (ends[i] if i < len(ends) else 0)
            else:
                if not current_word: word_start = starts[i]
                current_word += char
        
        chunks = []
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            if not chunk_words: continue
            combined_text = " ".join([w["text"] for w in chunk_words])
            chunks.append({
                "text": combined_text,
                "start": chunk_words[0]["start"],
                "end": chunk_words[-1]["end"]
            })

        with open(subs_path, "w", encoding="utf-8") as f:
            for i, chunk in enumerate(chunks):
                f.write(f"{i+1}\n{self._format_srt_time(chunk['start'])} --> {self._format_srt_time(chunk['end'])}\n{chunk['text']}\n\n")

    def _generate_audio_fallback_retry(self, text):
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        try:
            audio_generator = self.client.text_to_speech.convert(voice_id=self.current_voice_id, text=text, model_id=self.model_id)
            with open(audio_path, "wb") as f:
                for chunk in audio_generator: f.write(chunk)
            duration = self._get_duration(audio_path)
            words = text.split()
            chunks = [" ".join(words[i:i+2]) for i in range(0, len(words), 2)]
            with open(subs_path, "w", encoding="utf-8") as f:
                for i, c in enumerate(chunks):
                    t = (i/len(chunks))*duration
                    next_t = ((i+1)/len(chunks))*duration
                    f.write(f"{i+1}\n{self._format_srt_time(t)} --> {self._format_srt_time(next_t)}\n{c.upper()}\n\n")
            return audio_path, subs_path, duration
        except: return None, None, 0

    def generate_sfx(self, prompt, duration_seconds=None):
        """Generates a custom sound effect using ElevenLabs AI."""
        if not prompt or prompt.lower() == "none":
            return None
            
        id = str(uuid.uuid4())
        sfx_path = os.path.join(self.cache_dir, f"sfx_{id}.mp3")
        
        try:
            print(f"      🔊 [ElevenLabs SFX]: Generating '{prompt}'...")
            
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
                print(f"      ✅ [SFX SUCCESS]: Created '{prompt}'")
                return sfx_path
                
        except Exception as e:
            print(f"      ❌ ElevenLabs SFX Error: {e}")
            
        return None

    def generate_music(self, prompt): return None

    def _get_duration(self, audio_path):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            return float(subprocess.check_output(cmd).decode().strip())
        except: return 0.0

    def _format_srt_time(self, seconds):
        td_hours, td_minutes = int(seconds // 3600), int((seconds % 3600) // 60)
        td_seconds, td_millis = int(seconds % 60), int((seconds % 1) * 1000)
        return f"{td_hours:02}:{td_minutes:02}:{td_seconds:02},{td_millis:03}"
