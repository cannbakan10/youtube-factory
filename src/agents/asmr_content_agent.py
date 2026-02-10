"""
ASMR Shorts Content Agent
Produces daily no-voice, no-text, satisfying/relaxing ASMR Shorts.
Sources visuals from Pexels/Pixabay, adds ambient audio, uploads to YouTube.
"""
import os
import json
import random
import subprocess
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict

from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.services.youtube_service import YouTubeService
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ─── ASMR CATEGORIES ────────────────────────────────────────────
# Each category has video search keywords, audio search keywords, and SEO metadata
ASMR_CATEGORIES = [
    {
        "id": "sand_satisfying",
        "video_keywords": ["kinetic sand cutting", "sand satisfying", "colored sand"],
        "audio_keywords": ["asmr crunching", "sand sounds"],
        "title_templates": [
            "Satisfying Kinetic Sand Cutting ASMR 🤤",
            "Sand Cutting ASMR for Sleep & Relaxation 😴",
            "Oddly Satisfying Sand ASMR #satisfying",
        ],
        "tags": ["asmr", "satisfying", "kinetic sand", "sand cutting", "oddly satisfying",
                 "relaxing", "sleep", "no talking", "asmr no talking"],
    },
    {
        "id": "soap_cutting",
        "video_keywords": ["soap cutting asmr", "soap carving satisfying", "colorful soap"],
        "audio_keywords": ["asmr cutting", "crisp cutting sounds"],
        "title_templates": [
            "Soap Cutting ASMR So Satisfying 🧼✨",
            "Relaxing Soap Carving ASMR | No Talking 😌",
            "Satisfying Soap ASMR for Stress Relief 🧼",
        ],
        "tags": ["asmr", "soap cutting", "satisfying", "soap carving", "oddly satisfying",
                 "relaxing", "no talking", "stress relief"],
    },
    {
        "id": "water_drops",
        "video_keywords": ["water drops slow motion", "rain drops close up", "water ripple calm"],
        "audio_keywords": ["water drops asmr", "gentle rain drops"],
        "title_templates": [
            "Water Drops ASMR 💧 So Calming & Relaxing",
            "Mesmerizing Water Drops for Sleep 💧😴",
            "Gentle Water ASMR | No Talking 💧",
        ],
        "tags": ["asmr", "water drops", "relaxing", "calming", "rain drops",
                 "sleep", "no talking", "water asmr", "satisfying"],
    },
    {
        "id": "fire_closeup",
        "video_keywords": ["fire close up slow motion", "candle flame close", "burning ember"],
        "audio_keywords": ["fire crackling asmr", "campfire ambience"],
        "title_templates": [
            "Fire ASMR 🔥 Cozy Crackling Sounds",
            "Relaxing Fire Close-Up ASMR for Sleep 🔥",
            "Mesmerizing Flames ASMR | No Talking 🔥",
        ],
        "tags": ["asmr", "fire", "crackling", "cozy", "fireplace",
                 "relaxing", "sleep", "no talking", "campfire"],
    },
    {
        "id": "nature_closeup",
        "video_keywords": ["flower blooming timelapse", "morning dew close up", "nature macro"],
        "audio_keywords": ["nature sounds birds", "gentle wind leaves"],
        "title_templates": [
            "Nature Close-Up ASMR 🌿 So Beautiful & Relaxing",
            "Stunning Nature Macro ASMR | No Talking 🌸",
            "Relaxing Nature ASMR for Stress Relief 🌿",
        ],
        "tags": ["asmr", "nature", "macro", "satisfying", "beautiful",
                 "relaxing", "no talking", "flowers", "nature asmr"],
    },
    {
        "id": "ocean_waves",
        "video_keywords": ["ocean waves close up", "sea foam beach", "underwater bubbles"],
        "audio_keywords": ["ocean waves asmr", "beach waves gentle"],
        "title_templates": [
            "Ocean Waves ASMR 🌊 Instant Relaxation",
            "Calming Sea Waves ASMR for Deep Sleep 🌊😴",
            "Mesmerizing Ocean ASMR | No Talking 🌊",
        ],
        "tags": ["asmr", "ocean", "waves", "sea", "beach",
                 "relaxing", "sleep", "no talking", "water sounds"],
    },
    {
        "id": "rain_window",
        "video_keywords": ["rain on window close up", "rain drops glass", "rainy night window"],
        "audio_keywords": ["rain on window asmr", "soft rain ambience"],
        "title_templates": [
            "Rain on Window ASMR 🌧️ Perfect for Sleep",
            "Cozy Rain ASMR | No Talking 🌧️😴",
            "Relaxing Rain Sounds ASMR 🌧️ Stress Relief",
        ],
        "tags": ["asmr", "rain", "rain on window", "cozy", "relaxing",
                 "sleep", "no talking", "rain sounds", "rainy night"],
    },
    {
        "id": "slime_satisfying",
        "video_keywords": ["slime stretching satisfying", "fluffy slime", "slime mixing colors"],
        "audio_keywords": ["slime asmr sounds", "slime squishing"],
        "title_templates": [
            "Slime ASMR So Satisfying 🤩 #slime #asmr",
            "Satisfying Slime Mixing ASMR | No Talking 🫧",
            "Oddly Satisfying Slime ASMR for Relaxation 🫧",
        ],
        "tags": ["asmr", "slime", "satisfying", "slime asmr", "oddly satisfying",
                 "fluffy slime", "relaxing", "no talking"],
    },
    {
        "id": "paint_mixing",
        "video_keywords": ["paint mixing satisfying", "acrylic pour art", "color mixing art"],
        "audio_keywords": ["paint mixing sounds", "liquid pouring asmr"],
        "title_templates": [
            "Paint Mixing ASMR 🎨 So Satisfying!",
            "Mesmerizing Color Mixing ASMR | No Talking 🎨",
            "Satisfying Acrylic Pour ASMR 🎨✨",
        ],
        "tags": ["asmr", "paint mixing", "satisfying", "acrylic pour", "art",
                 "color mixing", "relaxing", "no talking", "oddly satisfying"],
    },
    {
        "id": "clouds_sky",
        "video_keywords": ["clouds timelapse", "sunset sky timelapse", "moving clouds dramatic"],
        "audio_keywords": ["wind ambience calm", "soft ambient drone"],
        "title_templates": [
            "Cloud Timelapse ASMR ☁️ So Peaceful",
            "Mesmerizing Sky ASMR for Relaxation ☁️😴",
            "Beautiful Cloud Movement ASMR | No Talking ☁️",
        ],
        "tags": ["asmr", "clouds", "timelapse", "sky", "sunset",
                 "peaceful", "relaxing", "no talking", "nature"],
    },
    {
        "id": "underwater",
        "video_keywords": ["underwater coral reef", "fish swimming underwater", "deep sea bubbles"],
        "audio_keywords": ["underwater ambience bubbles", "deep ocean sounds"],
        "title_templates": [
            "Underwater ASMR 🐠 So Mesmerizing",
            "Deep Sea ASMR for Sleep & Relaxation 🌊",
            "Calming Underwater World ASMR | No Talking 🐠",
        ],
        "tags": ["asmr", "underwater", "ocean", "coral reef", "fish",
                 "deep sea", "relaxing", "sleep", "no talking"],
    },
    {
        "id": "snow_falling",
        "video_keywords": ["snow falling slow motion", "snowflakes close up", "winter snowfall calm"],
        "audio_keywords": ["winter wind soft", "snow falling silence"],
        "title_templates": [
            "Snow Falling ASMR ❄️ Winter Relaxation",
            "Peaceful Snowfall ASMR for Sleep ❄️😴",
            "Mesmerizing Snow ASMR | No Talking ❄️",
        ],
        "tags": ["asmr", "snow", "snowfall", "winter", "peaceful",
                 "relaxing", "sleep", "no talking", "cozy"],
    },
    {
        "id": "food_satisfying",
        "video_keywords": ["food cutting satisfying", "chocolate breaking close up", "fruit slicing"],
        "audio_keywords": ["food cutting asmr", "crunchy food sounds"],
        "title_templates": [
            "Food ASMR So Satisfying 🍫🤤 #satisfying",
            "Satisfying Food Cutting ASMR | No Talking 🍓",
            "Crunchy Food ASMR for Relaxation 🥒✨",
        ],
        "tags": ["asmr", "food", "satisfying", "food cutting", "crunchy",
                 "oddly satisfying", "relaxing", "no talking"],
    },
    {
        "id": "lava_flow",
        "video_keywords": ["lava flow close up", "molten lava slow", "volcano lava"],
        "audio_keywords": ["lava bubbling", "volcanic rumble ambient"],
        "title_templates": [
            "Lava Flow ASMR 🌋 Mesmerizing & Satisfying",
            "Molten Lava ASMR for Relaxation 🌋🔥",
            "Volcanic Lava ASMR | No Talking 🌋",
        ],
        "tags": ["asmr", "lava", "volcano", "satisfying", "mesmerizing",
                 "relaxing", "no talking", "nature", "oddly satisfying"],
    },
    {
        "id": "galaxy_space",
        "video_keywords": ["galaxy stars timelapse", "aurora borealis night", "milky way sky"],
        "audio_keywords": ["space ambient drone", "cosmic ambience"],
        "title_templates": [
            "Space ASMR ✨ Stars & Galaxy Relaxation",
            "Milky Way ASMR for Deep Sleep 🌌😴",
            "Mesmerizing Galaxy ASMR | No Talking ✨",
        ],
        "tags": ["asmr", "space", "galaxy", "stars", "milky way",
                 "aurora", "relaxing", "sleep", "no talking"],
    },
]


class ASMRContentAgent:
    """Produces daily ASMR Shorts: no voice, no text, just satisfying visuals + ambient audio."""

    def __init__(self, factory_instance=None):
        self.factory = factory_instance
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.project_root, "data")
        self.cache_dir = os.path.join(self.project_root, "assets", "cache", "asmr")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        self.history_file = os.path.join(self.data_dir, "asmr_history.json")
        self.pexels = PexelsService(output_dir=self.cache_dir)
        self.pixabay = PixabayService(output_dir=self.cache_dir)

    def run_daily_automation(self, count: int = 5):
        """Main entry point: Produces and uploads `count` ASMR shorts."""
        logger.info(f"🎬 ASMR Daily Automation: Producing {count} shorts...")

        # Pick categories ensuring no repeats from recent history
        categories = self._pick_categories(count)
        logger.info(f"Selected categories: {[c['id'] for c in categories]}")

        success_count = 0
        for i, category in enumerate(categories):
            logger.info(f"\n{'='*50}")
            logger.info(f"ASMR Short {i+1}/{count}: {category['id']}")
            logger.info(f"{'='*50}")

            try:
                result = self._produce_single_short(category)
                if result:
                    # Upload to YouTube
                    upload_id = self._upload_to_youtube(result)
                    if upload_id:
                        self._log_history(category["id"], upload_id)
                        success_count += 1
                        logger.info(f"✅ ASMR Short {i+1} uploaded! YouTube ID: {upload_id}")
                    else:
                        logger.error(f"❌ ASMR Short {i+1} upload failed.")
                else:
                    logger.error(f"❌ ASMR Short {i+1} production failed.")
            except Exception as e:
                logger.error(f"❌ ASMR Short {i+1} error: {e}")

            # Cooldown between productions
            if i < count - 1:
                logger.info("Cooldown 15s before next short...")
                time.sleep(15)

        logger.info(f"\n🎬 ASMR Daily Automation Complete: {success_count}/{count} shorts produced.")
        return success_count

    def _pick_categories(self, count: int) -> List[Dict]:
        """Pick unique categories avoiding recent history."""
        history = self._load_history()
        recent_ids = [h["category"] for h in history[-20:]]  # Last 20 entries

        # Filter out recently used categories
        available = [c for c in ASMR_CATEGORIES if c["id"] not in recent_ids]

        # If not enough available, reset
        if len(available) < count:
            available = list(ASMR_CATEGORIES)

        random.shuffle(available)
        return available[:count]

    def _produce_single_short(self, category: Dict) -> Optional[Dict]:
        """Produces a single ASMR short: video + audio → rendered MP4."""

        # 1. Find video clips
        video_path = self._find_video(category["video_keywords"])
        if not video_path:
            logger.error(f"No video found for category: {category['id']}")
            return None

        # 2. Find ambient audio
        audio_path = self._find_audio(category["audio_keywords"])

        # 3. Get video duration to decide short length (30-59 seconds)
        video_duration = self._get_duration(video_path)
        target_duration = min(max(video_duration, 15), 59)  # Shorts must be under 60s
        logger.info(f"Source video: {video_duration:.1f}s → Target: {target_duration:.1f}s")

        # 4. Render the final short
        timestamp = int(time.time())
        output_path = os.path.join(self.cache_dir, f"asmr_{category['id']}_{timestamp}.mp4")

        render_ok = self._render_asmr_short(
            video_path=video_path,
            audio_path=audio_path,
            output_path=output_path,
            duration=target_duration,
        )

        if not render_ok:
            return None

        # 5. Build SEO metadata
        title = random.choice(category["title_templates"])
        description = self._build_description(category)
        tags = list(category["tags"]) + ["#Shorts", "Shorts"]

        return {
            "file_path": output_path,
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": category["id"],
        }

    def _find_video(self, keywords: List[str]) -> Optional[str]:
        """Find a single portrait/vertical video from Pexels or Pixabay."""
        # Try each keyword set
        for kw in keywords:
            try:
                path = self.pexels.get_video([kw], orientation="portrait")
                if path:
                    logger.info(f"Video found (Pexels): {kw}")
                    return path
            except Exception:
                pass

            try:
                path = self.pixabay.get_video([kw], orientation="portrait")
                if path:
                    logger.info(f"Video found (Pixabay): {kw}")
                    return path
            except Exception:
                pass

        # Fallback: try combined keywords
        combined = " ".join(keywords[:2])
        try:
            path = self.pexels.get_video([combined], orientation="portrait")
            if path:
                return path
        except Exception:
            pass

        return None

    def _find_audio(self, keywords: List[str]) -> Optional[str]:
        """Find ambient audio from Pixabay."""
        for kw in keywords:
            try:
                path = self.pixabay.get_audio(kw, category="ambient")
                if path and os.path.exists(path):
                    logger.info(f"Audio found: {kw}")
                    return path
            except Exception:
                continue

        # Fallback: check local music folder
        music_dir = os.path.join(self.project_root, "assets", "templates", "music")
        if os.path.exists(music_dir):
            tracks = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
            nature_tracks = [t for t in tracks if any(k in t.lower() for k in ["nature", "ambient", "calm", "lofi"])]
            if nature_tracks:
                return os.path.join(music_dir, random.choice(nature_tracks))
            if tracks:
                return os.path.join(music_dir, random.choice(tracks))

        return None

    def _get_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception:
            return 30.0  # Default

    def _render_asmr_short(self, video_path: str, audio_path: Optional[str],
                           output_path: str, duration: float) -> bool:
        """
        Render ASMR short: video (portrait 9:16) + ambient audio.
        No text overlay, no subtitles, no narration.
        """
        width, height = 1080, 1920
        input_args = []

        # Video input (looped if shorter than duration)
        input_args.extend(["-stream_loop", "-1", "-i", video_path])

        # Audio input
        if audio_path and os.path.exists(audio_path):
            input_args.extend(["-stream_loop", "-1", "-i", audio_path])
            audio_filter = (
                f"[1:a]atrim=duration={duration},"
                "asetpts=PTS-STARTPTS,"
                "afade=t=in:st=0:d=1.0,"
                f"afade=t=out:st={max(0, duration-2)}:d=2.0,"
                "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                "volume=0.8[aout]"
            )
        else:
            # Silent audio (YouTube needs audio track)
            input_args.extend(["-f", "lavfi", "-i",
                               "anoisesrc=color=brown:sample_rate=44100:amplitude=0.02"])
            audio_filter = (
                f"[1:a]atrim=duration={duration},"
                "asetpts=PTS-STARTPTS,"
                "aformat=sample_fmts=fltp:channel_layouts=stereo[aout]"
            )

        # Video filter: crop to 9:16, color grade for aesthetic
        video_filter = (
            f"[0:v]fps=30,setsar=1,"
            f"scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "eq=brightness=0.02:contrast=1.08:saturation=1.15,"
            "vignette=angle=0.2,"
            f"trim=duration={duration},"
            "setpts=PTS-STARTPTS,"
            "format=yuv420p[vout]"
        )

        filter_complex = f"{video_filter};{audio_filter}"

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info(f"Rendering ASMR short ({duration:.0f}s)...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Render failed: {result.stderr[:300]}")
                return False
            file_size = os.path.getsize(output_path) / 1_000_000
            logger.info(f"Render complete: {output_path} ({file_size:.1f}MB)")
            return True
        except Exception as e:
            logger.error(f"Render crashed: {e}")
            return False

    def _build_description(self, category: Dict) -> str:
        """Build SEO-optimized description for the ASMR short."""
        tag_str = " ".join([f"#{t.replace(' ', '')}" for t in category["tags"][:8]])
        return (
            f"Relaxing ASMR for sleep, stress relief, and relaxation. No talking.\n\n"
            f"🔔 Subscribe for daily satisfying ASMR content!\n"
            f"👍 Like if this video relaxed you!\n\n"
            f"{tag_str}\n\n"
            f"#Shorts #ASMR #Satisfying #Relaxing #NoTalking #Sleep #StressRelief"
        )

    def _upload_to_youtube(self, result: Dict) -> Optional[str]:
        """Upload the rendered short to YouTube."""
        try:
            youtube = YouTubeService()
            if not youtube.youtube:
                logger.error("YouTube service not authenticated.")
                return None

            video_id = youtube.upload_video(
                file_path=result["file_path"],
                title=result["title"],
                description=result["description"],
                tags=result["tags"],
                video_type="shorts",
            )
            return video_id
        except Exception as e:
            logger.error(f"YouTube upload error: {e}")
            return None

    def _load_history(self) -> List[Dict]:
        """Load ASMR production history."""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _log_history(self, category_id: str, youtube_id: str):
        """Log a successful production to history."""
        history = self._load_history()
        history.append({
            "category": category_id,
            "youtube_id": youtube_id,
            "produced_at": datetime.now().isoformat(),
        })
        # Keep last 100 entries
        history = history[-100:]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
