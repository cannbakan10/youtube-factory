from elevenlabs.client import ElevenLabs
import os
import uuid
import subprocess

class TTSService:
    def __init__(self, output_dir="assets/cache"):
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.cache_dir = output_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        # ElevenLabs 'Bella' or 'Adam' are great. 
        # For Turkish, Multilingual v2 is the gold standard.
        self.voice_id = "21m00Tcm4TlvDq8ikWAM" # Bella
        self.model_id = "eleven_multilingual_v2"

    def generate_audio_with_subtitles(self, text, language="tr"):
        """
        Generates PREMIUM ElevenLabs audio and returns (audio_path, subs_path, duration).
        """
        id = str(uuid.uuid4())
        audio_path = os.path.join(self.cache_dir, f"{id}.mp3")
        subs_path = os.path.join(self.cache_dir, f"{id}.srt")
        
        # Proper punctuation for natural flow
        clean_text = text.replace(".", ". ").replace("!", "! ").replace("?", "? ").strip()
        
        try:
            print(f"      🎙️ [ElevenLabs TTS - Bella Premium]: Deep, rich and natural Turkish...")
            audio_generator = self.client.generate(
                text=clean_text,
                voice=self.voice_id,
                model=self.model_id
            )
            
            # Save the generator content to file
            with open(audio_path, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)
                    
        except Exception as e:
            print(f"      ❌ ElevenLabs TTS Error: {e}")
            return None, None, 0

        # Get actual duration for perfect sync
        duration = self._get_duration(audio_path)
        
        # Professional Sync Logic
        self._create_dynamic_srt(clean_text, duration, subs_path)
        
        return audio_path, subs_path, duration

    def _get_duration(self, audio_path):
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]
            return float(subprocess.check_output(cmd).decode().strip())
        except:
            return 0.0

    def _create_dynamic_srt(self, text, duration, subs_path):
        words = text.split()
        # 1-2 words per chunk for best Shorts readability and fitting
        chunk_size = 1 
        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
        
        total_chars = sum(len(w) for w in words)
        current_time = 0.0
        
        with open(subs_path, "w", encoding="utf-8") as f:
            for i, chunk in enumerate(chunks):
                chunk_text = " ".join(chunk)
                chunk_chars = sum(len(w) for w in chunk)
                
                # Proportional duration based on characters
                chunk_duration = (chunk_chars / total_chars) * duration if total_chars > 0 else 0
                
                start_time = self._format_srt_time(current_time)
                # Ensure it doesn't overlap or go beyond duration
                current_time += chunk_duration
                end_time = self._format_srt_time(min(current_time, duration))
                
                f.write(f"{i+1}\n{start_time} --> {end_time}\n{chunk_text.upper()}\n\n")

    def _format_srt_time(self, seconds):
        td_hours = int(seconds // 3600)
        td_minutes = int((seconds % 3600) // 60)
        td_seconds = int(seconds % 60)
        td_millis = int((seconds % 1) * 1000)
        return f"{td_hours:02}:{td_minutes:02}:{td_seconds:02},{td_millis:03}"
