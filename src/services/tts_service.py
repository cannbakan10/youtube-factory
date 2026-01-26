from elevenlabs.client import ElevenLabs
import os
import uuid
import subprocess
import json
import base64
import random

class TTSService:
    def __init__(self, output_dir="assets/cache"):
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.client = ElevenLabs(api_key=api_key)
        self.cache_dir = output_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Available high-quality Turkish/Multilingual voices
        self.voices = {
            "male": [
                "IuRRIAcbQK5AQk1XevPj", # Doga (Turkish Native)
                "pNInz6obpgDQGcFmaJgB", # Adam (Strong, Social Media)
                "IKne3meq5aSn9XLyUdCD", # Charlie (Energetic)
            ],
            "female": [
                "EXAVITQu4vr4xnSDxMaL", # Sarah (Mature, Professional)
                "Xb7hH8MSUJpSbSDYk0k2", # Alice (Engaging Educator)
                "XrExE9yKIg1WjnnlVkGX", # Matilda (Professional)
            ]
        }
        self.current_voice_id = self.voices["male"][0] # Default
        self.model_id = "eleven_multilingual_v2"

    def set_voice(self, gender=None, voice_id=None):
        """Sets the voice for the current production."""
        if voice_id:
            self.current_voice_id = voice_id
        elif gender in self.voices:
            self.current_voice_id = random.choice(self.voices[gender])
        else:
            # Pick any random voice from all categories
            all_ids = self.voices["male"] + self.voices["female"]
            self.current_voice_id = random.choice(all_ids)
        
        print(f"      🎭 [TTSService]: Voice set to {self.current_voice_id}")

    def generate_audio_with_subtitles(self, text, language="tr"):
        """
        Hyper-Sync Edition: Uses ElevenLabs Timestamps for perfect word-level alignment.
        """
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        
        clean_text = text.strip()
        
        try:
            print(f"      🎙️ [ElevenLabs Hyper-Sync]: Generating audio ({self.current_voice_id})...")
            
            response = self.client.text_to_speech.convert_with_timestamps(
                voice_id=self.current_voice_id,
                text=clean_text,
                model_id=self.model_id,
                voice_settings={
                    "stability": 0.45,
                    "similarity_boost": 0.8,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            )
            
            audio_bytes = base64.b64decode(response.audio_base_64)
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            alignment = response.alignment
            self._alignment_to_srt(alignment, subs_path)
            
            duration = self._get_duration(audio_path)
            return audio_path, subs_path, duration
                    
        except Exception as e:
            print(f"      ❌ ElevenLabs Hyper-Sync Error: {e}")
            return self._generate_audio_fallback(clean_text)

    def generate_sfx(self, prompt, duration_seconds=None):
        if not prompt: return None
        id = str(uuid.uuid4())
        sfx_path = os.path.join(self.cache_dir, f"sfx_{id}.mp3")
        try:
            print(f"      🔊 [ElevenLabs SFX]: Generating '{prompt}'...")
            sfx_generator = self.client.text_to_sound_effects.convert(
                text=prompt,
                duration_seconds=duration_seconds,
                prompt_influence=0.8
            )
            with open(sfx_path, "wb") as f:
                for chunk in sfx_generator:
                    if chunk: f.write(chunk)
            
            if os.path.exists(sfx_path) and os.path.getsize(sfx_path) > 100:
                return sfx_path
        except Exception as e:
            print(f"      ⚠️ SFX Generation failed: {e}")
        return None

    def generate_music(self, prompt):
        if not prompt: return None
        id = str(uuid.uuid4())
        music_path = os.path.join(self.cache_dir, f"music_{id}.mp3")
        try:
            print(f"      🎵 [ElevenLabs Music]: Composing '{prompt}'...")
            music_generator = self.client.music.compose(prompt=prompt)
            with open(music_path, "wb") as f:
                for chunk in music_generator:
                    if chunk: f.write(chunk)
            return music_path
        except Exception as e:
            print(f"      ⚠️ Music Generation failed: {e}")
        return None

    def _alignment_to_srt(self, alignment, subs_path):
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
                    words.append({"text": current_word.strip().upper(), "start": word_start, "end": ends[i]})
                    current_word = ""
                word_start = starts[i+1] if i+1 < len(starts) else (ends[i] if i < len(ends) else 0)
            else:
                if not current_word: word_start = starts[i]
                current_word += char
        with open(subs_path, "w", encoding="utf-8") as f:
            for i, word in enumerate(words):
                f.write(f"{i+1}\n{self._format_srt_time(word['start'])} --> {self._format_srt_time(word['end'])}\n{word['text']}\n\n")

    def _generate_audio_fallback(self, text):
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        try:
            audio_generator = self.client.text_to_speech.convert(voice_id=self.current_voice_id, text=text, model_id=self.model_id)
            with open(audio_path, "wb") as f:
                for chunk in audio_generator: f.write(chunk)
            duration = self._get_duration(audio_path)
            words = text.split()
            with open(subs_path, "w", encoding="utf-8") as f:
                for i, w in enumerate(words):
                    t, next_t = (i/len(words))*duration, ((i+1)/len(words))*duration
                    f.write(f"{i+1}\n{self._format_srt_time(t)} --> {self._format_srt_time(next_t)}\n{w.upper()}\n\n")
            return audio_path, subs_path, duration
        except: return None, None, 0

    def _get_duration(self, audio_path):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            return float(subprocess.check_output(cmd).decode().strip())
        except: return 0.0

    def _format_srt_time(self, seconds):
        td_hours, td_minutes = int(seconds // 3600), int((seconds % 3600) // 60)
        td_seconds, td_millis = int(seconds % 60), int((seconds % 1) * 1000)
        return f"{td_hours:02}:{td_minutes:02}:{td_seconds:02},{td_millis:03}"
