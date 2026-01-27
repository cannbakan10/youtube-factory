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
        
        # Native English Professional Voices (Using standard ElevenLabs IDs)
        self.voices = {
            "male": [
                "pNInz6ob8mW8mY4Rnd87", # Adam (Classic Native English)
                "erXw78R7V9rS2S753JkO", # Antoni (Clear British/American)
            ],
            "female": [
                "21m00Tcm4TbcDqjt8gaZ", # Rachel (Professional Native English)
                "EXAVITQu4vr4xnSDxMaL", # Bella (Calm Native English)
            ]
        }
        self.current_voice_id = self.voices["male"][0] 
        self.model_id = "eleven_multilingual_v2" # Best for sync and variety

    def set_voice(self, gender=None, voice_id=None):
        """Sets the voice for production. Optimized for NATIVE English tone."""
        if voice_id:
            self.current_voice_id = voice_id
        elif gender in self.voices:
            self.current_voice_id = random.choice(self.voices[gender])
        else:
            all_ids = self.voices["male"] + self.voices["female"]
            self.current_voice_id = random.choice(all_ids)
        
        print(f"      🎭 [TTSService]: Native English Voice -> {self.current_voice_id}")

    def generate_audio_with_subtitles(self, text, language="en"):
        """
        Hyper-Sync Edition: Uses ElevenLabs Timestamps for perfect alignment.
        """
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        
        clean_text = text.strip()
        
        try:
            print(f"      🎙️ [ElevenLabs Hyper-Sync]: Narrating with Native Voice ({self.current_voice_id})...")
            
            # stability: 0.65 for more measured, articulated speech (less speed)
            response = self.client.text_to_speech.convert_with_timestamps(
                voice_id=self.current_voice_id,
                text=clean_text,
                model_id=self.model_id,
                voice_settings={
                    "stability": 0.65,
                    "similarity_boost": 0.75,
                    "style": 0.05,
                    "use_speaker_boost": True
                }
            )
            
            audio_bytes = base64.b64decode(response.audio_base_64)
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            alignment = response.alignment
            # Now grouping words in subtitles to avoid "ultra-fast flickering" and fit screen better
            self._alignment_to_srt_grouped(alignment, subs_path)
            
            duration = self._get_duration(audio_path)
            return audio_path, subs_path, duration
                    
        except Exception as e:
            print(f"      ❌ ElevenLabs Error: {e}. Falling back to account voices...")
            # Fallback to confirmed account voices if native IDs fail (some accounts restricted)
            self.current_voice_id = "z2ObNnp0E5ZGeTlSXkX0" # Mert Aksoy (Confirmed fallback)
            return self._generate_audio_fallback_retry(clean_text)

    def _alignment_to_srt_grouped(self, alignment, subs_path, words_per_chunk=3):
        """Groups words to make subtitles more readable and less 'busy'."""
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
        
        # Group words into chunks
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
        # Similar logic to standard fallback but uses grouped SRT
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        try:
            audio_generator = self.client.text_to_speech.convert(voice_id=self.current_voice_id, text=text, model_id=self.model_id)
            with open(audio_path, "wb") as f:
                for chunk in audio_generator: f.write(chunk)
            duration = self._get_duration(audio_path)
            
            # Simple word split for fallback (no exact alignment available)
            words = text.split()
            chunks = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]
            with open(subs_path, "w", encoding="utf-8") as f:
                for i, c in enumerate(chunks):
                    t = (i/len(chunks))*duration
                    next_t = ((i+1)/len(chunks))*duration
                    f.write(f"{i+1}\n{self._format_srt_time(t)} --> {self._format_srt_time(next_t)}\n{c.upper()}\n\n")
            return audio_path, subs_path, duration
        except: return None, None, 0

    def generate_sfx(self, prompt, duration_seconds=None): return None
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
