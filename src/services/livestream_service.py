"""
YouTube Live Stream Service
Loops an ambient video indefinitely via RTMP to YouTube Live.
"""
import os
import subprocess
import signal
import time
import json
from typing import Optional, Dict, List
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ─── STREAM PRESETS ─────────────────────────────────────────────
# Each preset defines the YouTube Live metadata + video/audio keywords
LIVESTREAM_PRESETS: Dict[str, Dict] = {
    "rainy_car": {
        "title": "🌧️ Rain Sounds for Sleeping | Soft Rain & Thunder on Cozy Car | 24/7 Live",
        "description": (
            "🌧️ Gentle rain and soft thunder on a cozy car window.\n"
            "Perfect for deep sleep, relaxation, and stress relief.\n\n"
            "🔔 Subscribe for more 24/7 ambient streams!\n\n"
            "🎯 Benefits:\n"
            "• Deep sleep & insomnia relief\n"
            "• Stress & anxiety reduction\n"
            "• Study & focus boost\n"
            "• ASMR & white noise alternative\n\n"
            "#rainsounds #sleepsounds #rain #thunderstorm #cozysleep #relaxing #deepsleep #asmr"
        ),
        "tags": ["rain sounds", "rain for sleeping", "thunder", "cozy car rain",
                 "deep sleep", "relaxing", "white noise", "asmr rain", "rain on car",
                 "sleep sounds", "rain and thunder", "gentle thunder"],
        "category": "22",  # People & Blogs
        "video_keywords": ["rain on car window night", "rain drops windshield", "rainy night car"],
        "audio_queries": ["rain on car roof", "gentle rain thunder"],
    },
    "fireplace": {
        "title": "🔥 Cozy Fireplace with Crackling Sounds | 24/7 Live for Sleep & Relaxation",
        "description": (
            "🔥 Crackling fireplace for deep sleep and ultimate relaxation.\n"
            "Let the warm ambience soothe your mind all night long.\n\n"
            "🔔 Subscribe for more 24/7 ambient streams!\n\n"
            "🎯 Benefits:\n"
            "• Deep sleep & insomnia relief\n"
            "• Stress reduction\n"
            "• Cozy winter atmosphere\n"
            "• Perfect background for reading & studying\n\n"
            "#fireplace #crackling #cozy #sleep #relaxing #ambience #wintervibes"
        ),
        "tags": ["fireplace", "crackling fire", "cozy fireplace", "sleep",
                 "relaxing", "ambience", "winter", "fire sounds", "fireplace 24/7"],
        "category": "22",
        "video_keywords": ["steady fireplace burning", "cozy fireplace close up", "fire burning log"],
        "audio_queries": ["fireplace crackling ambience", "fire crackling wood"],
    },
    "rain_window": {
        "title": "🌧️ Rain on Window at Night | Relaxing Rain Sounds for Sleep | 24/7 Live",
        "description": (
            "🌧️ Watch the rain fall on a dark window and drift into deep sleep.\n"
            "Hours of continuous, uninterrupted rain ambience.\n\n"
            "🔔 Subscribe for more 24/7 ambient streams!\n\n"
            "🎯 Benefits:\n"
            "• Fall asleep faster\n"
            "• Block out distracting noise\n"
            "• Reduce stress & anxiety\n"
            "• Improve focus & concentration\n\n"
            "#rain #rainsounds #rainsleep #windowrain #relaxing #deepsleep #whitenoise"
        ),
        "tags": ["rain on window", "rain sounds", "rain sleep", "night rain",
                 "relaxing rain", "window rain", "deep sleep", "white noise"],
        "category": "22",
        "video_keywords": ["rain window night", "rain drops on glass", "rainy window close up"],
        "audio_queries": ["heavy rain window", "night rain ambience"],
    },
    "ocean_waves": {
        "title": "🌊 Ocean Waves for Deep Sleep | Calm Sea Sounds | 24/7 Live",
        "description": (
            "🌊 Gentle ocean waves and calm sea sounds all night long.\n"
            "The perfect natural white noise for deep, restful sleep.\n\n"
            "🔔 Subscribe for more 24/7 ambient streams!\n\n"
            "🎯 Benefits:\n"
            "• Natural white noise for sleep\n"
            "• Stress & anxiety relief\n"
            "• Meditation & mindfulness\n"
            "• Baby sleep aid\n\n"
            "#oceanwaves #seasounds #deepsleep #relaxing #whitenoise #ocean #waves #nature"
        ),
        "tags": ["ocean waves", "sea sounds", "deep sleep", "relaxing",
                 "white noise", "ocean", "waves", "nature sounds", "beach"],
        "category": "22",
        "video_keywords": ["calm ocean waves night", "gentle waves beach", "moonlit ocean"],
        "audio_queries": ["ocean waves sleep", "calm sea ambience"],
    },
    "thunderstorm": {
        "title": "⛈️ Heavy Thunderstorm & Rain | Deep Sleep Sounds | 24/7 Live",
        "description": (
            "⛈️ Powerful thunderstorm with heavy rain for deep sleep.\n"
            "Rolling thunder and intense rain to block everything out.\n\n"
            "🔔 Subscribe for more 24/7 ambient streams!\n\n"
            "🎯 Benefits:\n"
            "• Deep sleep in minutes\n"
            "• Block all distractions\n"
            "• Powerful stress relief\n"
            "• Natural sound therapy\n\n"
            "#thunderstorm #heavyrain #thunder #lightning #deepsleep #rain #storm #relaxing"
        ),
        "tags": ["thunderstorm", "heavy rain", "thunder", "lightning",
                 "deep sleep", "storm sounds", "rain sleep", "rolling thunder"],
        "category": "22",
        "video_keywords": ["lightning storm night", "thunder rain dark sky", "heavy rain city"],
        "audio_queries": ["heavy thunderstorm rain", "rolling thunder close"],
    },
    "snow_cabin": {
        "title": "❄️ Cozy Cabin in Snowstorm | Blizzard & Fireplace Sounds | 24/7 Live",
        "description": (
            "❄️ Safe and warm inside a cozy cabin while a blizzard howls outside.\n"
            "The ultimate winter sleep experience with crackling fire.\n\n"
            "🔔 Subscribe for more 24/7 ambient streams!\n\n"
            "🎯 Benefits:\n"
            "• Immersive winter atmosphere\n"
            "• Deep sleep & stress relief\n"
            "• Perfect for cold nights\n"
            "• Cozy study background\n\n"
            "#snowstorm #blizzard #cozycabin #winter #fireplace #cozy #deepsleep"
        ),
        "tags": ["snowstorm", "blizzard", "cozy cabin", "winter",
                 "fireplace", "snow", "cabin", "winter ambience"],
        "category": "22",
        "video_keywords": ["snowy cabin window", "blizzard forest night", "cozy cabin fireplace"],
        "audio_queries": ["blizzard howling wind", "wind and fire crackling"],
    },
}


class LivestreamService:
    """Manages YouTube Live Streams using FFmpeg RTMP."""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.cache_dir = os.path.join(self.project_root, "assets", "cache", "livestream")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.stream_key = os.getenv("YOUTUBE_STREAM_KEY", "").strip()
        self.rtmp_url = os.getenv("YOUTUBE_RTMP_URL", "rtmp://a.rtmp.youtube.com/live2").strip()
        self.process: Optional[subprocess.Popen] = None

        # Import media services
        from src.services.pexels_service import PexelsService
        from src.services.pixabay_service import PixabayService
        self.pexels = PexelsService(output_dir=self.cache_dir)
        self.pixabay = PixabayService(output_dir=self.cache_dir)

    def prepare_loop_video(self, preset_name: str, duration_minutes: int = 30) -> Optional[str]:
        """
        Prepares a short loop video (e.g. 30 min) that FFmpeg will loop infinitely for the stream.
        Shorter = less disk space, FFmpeg loops it seamlessly.
        """
        preset = LIVESTREAM_PRESETS.get(preset_name)
        if not preset:
            logger.error(f"Unknown livestream preset: {preset_name}")
            return None

        loop_path = os.path.join(self.cache_dir, f"loop_{preset_name}.mp4")

        # Skip if already prepared
        if os.path.exists(loop_path):
            file_size = os.path.getsize(loop_path)
            if file_size > 1_000_000:  # > 1MB means it's valid
                logger.info(f"Loop video already exists: {loop_path} ({file_size / 1_000_000:.1f}MB)")
                return loop_path

        logger.info(f"Preparing loop video for '{preset_name}' ({duration_minutes} min)...")

        # 1. Collect video clips
        keywords = preset["video_keywords"]
        video_sources = []

        try:
            video_sources = self.pexels.get_multiple_videos(keywords, count=6, orientation="landscape")
        except Exception as e:
            logger.warning(f"Pexels fetch failed: {e}")

        if not video_sources:
            try:
                video_sources = self.pixabay.get_multiple_videos(keywords, count=6, orientation="landscape")
            except Exception as e:
                logger.warning(f"Pixabay fetch failed: {e}")

        if not video_sources:
            logger.error("No video sources found for livestream loop!")
            return None

        logger.info(f"Found {len(video_sources)} video clips for loop")

        # 2. Collect audio
        audio_source = None
        for query in preset.get("audio_queries", []):
            try:
                audio_source = self.pixabay.get_audio(str(query), category="ambient")
                if audio_source and os.path.exists(audio_source):
                    break
            except Exception:
                continue

        # 3. Build concat file
        concat_path = os.path.join(self.cache_dir, f"concat_{preset_name}.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            for vs in video_sources:
                if os.path.exists(vs):
                    f.write(f"file '{vs}'\n")

        # 4. Render loop video
        duration_seconds = duration_minutes * 60

        input_args = ["-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", concat_path]

        if audio_source and os.path.exists(audio_source):
            input_args.extend(["-stream_loop", "-1", "-i", audio_source])
        else:
            input_args.extend(["-f", "lavfi", "-i", "anoisesrc=color=pink:sample_rate=44100:amplitude=0.05"])

        filter_complex = (
            "[0:v]fps=24,setsar=1,"
            "scale=w=1920:h=1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,format=yuv420p[vout];"
            f"[1:a]atrim=duration={duration_seconds},"
            "asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.0[aout]"
        )

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-t", str(duration_seconds),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-b:v", "4500k", "-maxrate", "4500k", "-bufsize", "9000k",
            "-g", "48",  # keyframe interval (2 seconds at 24fps)
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            loop_path,
        ]

        logger.info("Rendering loop video... This may take a while.")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Loop render failed: {result.stderr[:500]}")
                return None
            logger.info(f"Loop video ready: {loop_path} ({os.path.getsize(loop_path) / 1_000_000:.1f}MB)")
            return loop_path
        except Exception as e:
            logger.error(f"Loop render crashed: {e}")
            return None

    def start_stream(self, preset_name: str, loop_video_path: Optional[str] = None) -> bool:
        """Start streaming the loop video to YouTube Live via RTMP."""
        if not self.stream_key:
            logger.error("YOUTUBE_STREAM_KEY is not set! Add it to your .env file.")
            logger.info("Get your stream key from: YouTube Studio → Go Live → Stream → Stream Key")
            return False

        # Prepare loop if not provided
        if not loop_video_path:
            loop_video_path = self.prepare_loop_video(preset_name)

        if not loop_video_path or not os.path.exists(loop_video_path):
            logger.error("No loop video available for streaming!")
            return False

        rtmp_dest = f"{self.rtmp_url}/{self.stream_key}"
        preset = LIVESTREAM_PRESETS.get(preset_name, {})

        logger.info(f"🔴 Starting YouTube Live Stream: {preset.get('title', preset_name)}")
        logger.info(f"   Loop video: {loop_video_path}")
        logger.info(f"   RTMP: {self.rtmp_url}/****")

        # FFmpeg command: loop video infinitely → stream to YouTube
        cmd = [
            "ffmpeg",
            "-re",                    # Read at realtime speed (crucial for live)
            "-stream_loop", "-1",     # Loop forever
            "-i", loop_video_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", "4500k",
            "-maxrate", "4500k",
            "-bufsize", "9000k",
            "-pix_fmt", "yuv420p",
            "-g", "48",              # Keyframe every 2 sec
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-f", "flv",
            rtmp_dest,
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info("🔴 LIVE STREAM STARTED! Press Ctrl+C to stop.")
            logger.info(f"   Title: {preset.get('title', '')}")
            logger.info(f"   Set this title and description in YouTube Studio → Go Live")
            return True
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False

    def stop_stream(self):
        """Stop the running stream."""
        if self.process:
            logger.info("Stopping live stream...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            logger.info("Live stream stopped.")
        else:
            logger.warning("No active stream to stop.")

    def stream_with_auto_restart(self, preset_name: str, loop_video_path: Optional[str] = None):
        """
        Streams with automatic restart if FFmpeg crashes.
        This is the main entry point for 24/7 streaming.
        """
        if not loop_video_path:
            loop_video_path = self.prepare_loop_video(preset_name)

        if not loop_video_path:
            logger.error("Cannot start auto-restart stream without a loop video.")
            return

        restart_count = 0
        max_restarts = 100  # Safety limit

        while restart_count < max_restarts:
            try:
                logger.info(f"Stream attempt #{restart_count + 1}")
                success = self.start_stream(preset_name, loop_video_path)

                if not success:
                    logger.error("Stream failed to start. Retrying in 30s...")
                    time.sleep(30)
                    restart_count += 1
                    continue

                # Wait for process to finish (it shouldn't unless it crashes)
                self.process.wait()

                exit_code = self.process.returncode
                logger.warning(f"Stream ended with exit code {exit_code}. Restarting in 10s...")
                time.sleep(10)
                restart_count += 1

            except KeyboardInterrupt:
                logger.info("Stream stopped by user (Ctrl+C).")
                self.stop_stream()
                break
            except Exception as e:
                logger.error(f"Stream error: {e}. Restarting in 30s...")
                time.sleep(30)
                restart_count += 1

        if restart_count >= max_restarts:
            logger.error(f"Max restarts ({max_restarts}) reached. Stopping.")

    def get_stream_info(self, preset_name: str) -> Optional[Dict]:
        """Returns the title, description, and tags for a preset (for YouTube Studio setup)."""
        preset = LIVESTREAM_PRESETS.get(preset_name)
        if not preset:
            return None
        return {
            "title": preset["title"],
            "description": preset["description"],
            "tags": preset["tags"],
            "category": preset.get("category", "22"),
        }

    @staticmethod
    def list_presets() -> List[str]:
        return list(LIVESTREAM_PRESETS.keys())

    @staticmethod
    def print_presets():
        print("\n" + "=" * 60)
        print("📡 YOUTUBE LIVESTREAM PRESETS")
        print("=" * 60)
        for name, preset in LIVESTREAM_PRESETS.items():
            print(f"\n  🎬 {name}")
            print(f"     {preset['title']}")
        print("\n" + "=" * 60)
