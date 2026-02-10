"""
ASMR Shorts Content Agent
Produces daily no-voice, no-text, satisfying/relaxing ASMR Shorts.
Sources video clips from Mixkit, Coverr, Pexels, and Pixabay.
Adds category-specific audio, uploads to YouTube.
"""
import os
import json
import random
import subprocess
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict

from src.services.mixkit_service import MixkitService
from src.services.pixabay_service import PixabayService
from src.services.youtube_service import YouTubeService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Target duration range for Shorts (seconds)
MIN_DURATION = 50
MAX_DURATION = 59  # Must stay under 60 for Shorts

# ─── ASMR CATEGORIES ────────────────────────────────────────────
# Each category has multiple video keywords (for clip variety),
# specific audio keywords (matching the visual), and SEO metadata
ASMR_CATEGORIES = [
    {
        "id": "sand_satisfying",
        "video_keywords": [
            "kinetic sand cutting satisfying",
            "kinetic sand ASMR",
            "colored sand slicing",
            "sand cutting close up",
            "sand mold satisfying",
        ],
        "mixkit_keywords": ["sand", "sand-castle", "beach-sand", "colored-sand"],
        "audio_keywords": [
            "sand crunching ASMR",
            "sand cutting sound",
            "crunchy satisfying ASMR",
            "crispy cutting ASMR",
        ],
        "title_templates": [
            "Satisfying Kinetic Sand Cutting ASMR 🤤 #shorts #asmr",
            "Sand Cutting ASMR for Sleep & Relaxation 😴 #shorts",
            "Oddly Satisfying Sand ASMR ✨ #satisfying #shorts",
            "Crunchy Sand ASMR | No Talking 🤤 #shorts #asmr",
        ],
        "tags": ["asmr", "satisfying", "kinetic sand", "sand cutting", "oddly satisfying",
                 "relaxing", "sleep", "no talking", "asmr no talking", "crunchy", "shorts"],
    },
    {
        "id": "soap_cutting",
        "video_keywords": [
            "soap cutting ASMR satisfying",
            "soap carving close up",
            "dry soap cutting",
            "colorful soap slicing",
            "soap shaving satisfying",
        ],
        "mixkit_keywords": ["soap", "soap-making", "hand-washing", "soap-bubbles"],
        "audio_keywords": [
            "soap cutting crunchy sound",
            "ASMR cutting crispy",
            "satisfying crunch sounds",
            "soap carving ASMR",
        ],
        "title_templates": [
            "Soap Cutting ASMR So Satisfying 🧼✨ #shorts #asmr",
            "Relaxing Soap Carving ASMR | No Talking 😌 #shorts",
            "Crunchy Soap ASMR for Stress Relief 🧼 #shorts",
            "Oddly Satisfying Soap Cutting 🧼🤤 #shorts #asmr",
        ],
        "tags": ["asmr", "soap cutting", "satisfying", "soap carving", "oddly satisfying",
                 "relaxing", "no talking", "stress relief", "crunchy", "shorts"],
    },
    {
        "id": "water_drops",
        "video_keywords": [
            "water drops slow motion macro",
            "rain drops close up glass",
            "water ripple calm surface",
            "water splash slow motion",
            "droplet falling water",
        ],
        "mixkit_keywords": ["water-drops", "rain", "water-splash", "dripping"],
        "audio_keywords": [
            "water drops ASMR relaxing",
            "rain drops gentle sound",
            "water dripping calming",
            "gentle water flow ASMR",
        ],
        "title_templates": [
            "Water Drops ASMR 💧 So Calming & Relaxing #shorts",
            "Mesmerizing Water Drops for Sleep 💧😴 #shorts",
            "Gentle Water ASMR | No Talking 💧 #shorts #asmr",
            "Relaxing Water Drop Sounds 💧✨ #shorts",
        ],
        "tags": ["asmr", "water drops", "relaxing", "calming", "rain drops",
                 "sleep", "no talking", "water asmr", "satisfying", "shorts"],
    },
    {
        "id": "fire_closeup",
        "video_keywords": [
            "fire close up slow motion",
            "campfire burning close",
            "candle flame macro",
            "fireplace burning log",
            "fire embers glowing",
        ],
        "mixkit_keywords": ["fire", "campfire", "candle", "flames", "fireplace"],
        "audio_keywords": [
            "fire crackling ASMR",
            "campfire crackling wood",
            "fireplace cozy sounds",
            "fire burning ambience",
        ],
        "title_templates": [
            "Fire ASMR 🔥 Cozy Crackling Sounds #shorts #asmr",
            "Relaxing Fire Close-Up ASMR for Sleep 🔥 #shorts",
            "Mesmerizing Flames ASMR | No Talking 🔥 #shorts",
            "Crackling Fire ASMR 🔥 Instant Relaxation #shorts",
        ],
        "tags": ["asmr", "fire", "crackling", "cozy", "fireplace",
                 "relaxing", "sleep", "no talking", "campfire", "shorts"],
    },
    {
        "id": "nature_macro",
        "video_keywords": [
            "flower blooming timelapse close up",
            "morning dew drops macro",
            "nature macro close up",
            "butterfly wings close up",
            "plant growing timelapse",
        ],
        "mixkit_keywords": ["flowers", "nature-close-up", "plants", "butterfly", "dew"],
        "audio_keywords": [
            "nature sounds birds chirping",
            "gentle wind leaves rustling",
            "forest ambience birds",
            "morning nature ASMR",
        ],
        "title_templates": [
            "Nature Close-Up ASMR 🌿 So Beautiful & Relaxing #shorts",
            "Stunning Nature Macro ASMR | No Talking 🌸 #shorts",
            "Relaxing Nature ASMR 🌿✨ #shorts #asmr",
            "Beautiful Nature Moments 🌿 ASMR #shorts",
        ],
        "tags": ["asmr", "nature", "macro", "satisfying", "beautiful",
                 "relaxing", "no talking", "flowers", "nature asmr", "shorts"],
    },
    {
        "id": "ocean_waves",
        "video_keywords": [
            "ocean waves close up slow motion",
            "sea foam beach close",
            "underwater bubbles rising",
            "waves crashing rocks close",
            "crystal clear ocean water",
        ],
        "mixkit_keywords": ["ocean-waves", "sea", "beach-waves", "waves-crashing"],
        "audio_keywords": [
            "ocean waves ASMR relaxing",
            "beach waves gentle rolling",
            "sea waves calming sleep",
            "ocean shore ambience",
        ],
        "title_templates": [
            "Ocean Waves ASMR 🌊 Instant Relaxation #shorts",
            "Calming Sea Waves ASMR for Deep Sleep 🌊😴 #shorts",
            "Mesmerizing Ocean ASMR | No Talking 🌊 #shorts",
            "Relaxing Wave Sounds 🌊✨ #shorts #asmr",
        ],
        "tags": ["asmr", "ocean", "waves", "sea", "beach",
                 "relaxing", "sleep", "no talking", "water sounds", "shorts"],
    },
    {
        "id": "rain_window",
        "video_keywords": [
            "rain on window close up night",
            "rain drops glass window",
            "rainy window cozy night",
            "heavy rain window pane",
            "rain streaks on glass",
        ],
        "mixkit_keywords": ["rain", "rainy", "rain-drops", "storm", "rainy-window"],
        "audio_keywords": [
            "rain on window ASMR",
            "heavy rain sounds sleep",
            "rain drops glass ASMR",
            "cozy rain ambience",
        ],
        "title_templates": [
            "Rain on Window ASMR 🌧️ Perfect for Sleep #shorts",
            "Cozy Rain ASMR | No Talking 🌧️😴 #shorts",
            "Relaxing Rain Sounds ASMR 🌧️ #shorts #asmr",
            "Rain Drops on Glass ASMR 🌧️✨ #shorts",
        ],
        "tags": ["asmr", "rain", "rain on window", "cozy", "relaxing",
                 "sleep", "no talking", "rain sounds", "rainy night", "shorts"],
    },
    {
        "id": "slime_satisfying",
        "video_keywords": [
            "slime stretching satisfying close up",
            "fluffy slime mixing",
            "slime mixing colors satisfying",
            "clear slime bubbles",
            "glitter slime satisfying",
        ],
        "mixkit_keywords": ["slime", "gooey", "jelly", "sticky", "gel"],
        "audio_keywords": [
            "slime ASMR squishing",
            "slime sounds satisfying",
            "slime stretching ASMR",
            "fluffy slime ASMR",
        ],
        "title_templates": [
            "Slime ASMR So Satisfying 🤩 #shorts #slime #asmr",
            "Satisfying Slime Mixing ASMR | No Talking 🫧 #shorts",
            "Oddly Satisfying Slime ASMR 🫧✨ #shorts",
            "Fluffy Slime ASMR 🫧 So Relaxing #shorts",
        ],
        "tags": ["asmr", "slime", "satisfying", "slime asmr", "oddly satisfying",
                 "fluffy slime", "relaxing", "no talking", "shorts"],
    },
    {
        "id": "paint_mixing",
        "video_keywords": [
            "paint mixing satisfying close up",
            "acrylic pour art colors",
            "color mixing paint swirl",
            "paint pouring satisfying",
            "ink in water close up",
        ],
        "mixkit_keywords": ["paint", "painting", "art-supplies", "ink", "acrylic", "color-mixing"],
        "audio_keywords": [
            "paint mixing ASMR",
            "liquid pouring ASMR",
            "paint swirling sounds",
            "satisfying liquid ASMR",
        ],
        "title_templates": [
            "Paint Mixing ASMR 🎨 So Satisfying! #shorts #asmr",
            "Mesmerizing Color Mixing ASMR | No Talking 🎨 #shorts",
            "Satisfying Acrylic Pour ASMR 🎨✨ #shorts",
            "Oddly Satisfying Paint Mixing 🎨 #shorts",
        ],
        "tags": ["asmr", "paint mixing", "satisfying", "acrylic pour", "art",
                 "color mixing", "relaxing", "no talking", "oddly satisfying", "shorts"],
    },
    {
        "id": "clouds_sky",
        "video_keywords": [
            "clouds timelapse dramatic",
            "sunset sky timelapse golden",
            "storm clouds moving fast",
            "sunrise clouds colorful",
            "aerial clouds flying above",
        ],
        "mixkit_keywords": ["clouds", "sky", "sunset", "sunrise", "timelapse-clouds"],
        "audio_keywords": [
            "wind ambience calm soft",
            "atmospheric drone ambient",
            "soft ambient pad",
            "peaceful sky ambience",
        ],
        "title_templates": [
            "Cloud Timelapse ASMR ☁️ So Peaceful #shorts",
            "Mesmerizing Sky ASMR 🌅 #shorts #asmr",
            "Beautiful Cloud Movement ☁️✨ #shorts",
            "Relaxing Sky Timelapse ☁️ No Talking #shorts",
        ],
        "tags": ["asmr", "clouds", "timelapse", "sky", "sunset",
                 "peaceful", "relaxing", "no talking", "nature", "shorts"],
    },
    {
        "id": "underwater",
        "video_keywords": [
            "underwater coral reef fish",
            "tropical fish swimming clear",
            "deep sea jellyfish glowing",
            "underwater bubbles rising close",
            "scuba diving reef colorful",
        ],
        "mixkit_keywords": ["underwater", "fish", "coral-reef", "ocean-floor", "diving"],
        "audio_keywords": [
            "underwater ambience bubbles",
            "deep ocean sounds ASMR",
            "underwater ASMR calming",
            "ocean depths ambient",
        ],
        "title_templates": [
            "Underwater ASMR 🐠 So Mesmerizing #shorts",
            "Deep Sea ASMR for Relaxation 🌊 #shorts",
            "Calming Underwater World ASMR 🐠 #shorts #asmr",
            "Beautiful Ocean Life 🐠✨ #shorts",
        ],
        "tags": ["asmr", "underwater", "ocean", "coral reef", "fish",
                 "deep sea", "relaxing", "sleep", "no talking", "shorts"],
    },
    {
        "id": "snow_falling",
        "video_keywords": [
            "snow falling slow motion close",
            "snowflakes close up macro",
            "heavy snowfall night peaceful",
            "winter snowfall forest calm",
            "snow covered trees peaceful",
        ],
        "mixkit_keywords": ["snow", "snowfall", "winter-snow", "blizzard", "snowflakes"],
        "audio_keywords": [
            "winter wind soft gentle",
            "snow falling silence calm",
            "blizzard wind soft ASMR",
            "winter ambience peaceful",
        ],
        "title_templates": [
            "Snow Falling ASMR ❄️ Winter Relaxation #shorts",
            "Peaceful Snowfall for Sleep ❄️😴 #shorts",
            "Mesmerizing Snow ASMR | No Talking ❄️ #shorts",
            "Beautiful Snowfall ❄️✨ #shorts #asmr",
        ],
        "tags": ["asmr", "snow", "snowfall", "winter", "peaceful",
                 "relaxing", "sleep", "no talking", "cozy", "shorts"],
    },
    {
        "id": "food_satisfying",
        "video_keywords": [
            "food cutting satisfying close up",
            "chocolate cutting close up",
            "fruit slicing satisfying",
            "ice cream scooping close",
            "cooking satisfying close up",
        ],
        "mixkit_keywords": ["cooking", "food-preparation", "baking", "cutting-food", "chocolate"],
        "audio_keywords": [
            "food cutting ASMR crunchy",
            "satisfying crunch food ASMR",
            "crispy food sounds ASMR",
            "cooking ASMR sounds",
        ],
        "title_templates": [
            "Food ASMR So Satisfying 🍫🤤 #shorts #satisfying",
            "Satisfying Food Cutting ASMR 🍓 #shorts",
            "Crunchy Food ASMR ✨ #shorts #asmr",
            "Oddly Satisfying Food 🍫 #shorts",
        ],
        "tags": ["asmr", "food", "satisfying", "food cutting", "crunchy",
                 "oddly satisfying", "relaxing", "no talking", "shorts"],
    },
    {
        "id": "lava_flow",
        "video_keywords": [
            "lava flow close up glowing",
            "molten lava slow motion",
            "volcano lava eruption close",
            "lava meeting ocean steam",
            "magma flowing close up",
        ],
        "mixkit_keywords": ["lava", "volcano", "molten", "eruption"],
        "audio_keywords": [
            "lava bubbling rumble sound",
            "volcanic deep rumble ambience",
            "deep bass rumble ambient",
            "lava flow ambient sound",
        ],
        "title_templates": [
            "Lava Flow ASMR 🌋 Mesmerizing & Satisfying #shorts",
            "Molten Lava ASMR 🌋🔥 #shorts #asmr",
            "Volcanic Lava Close-Up 🌋 #shorts",
            "Satisfying Lava Flow 🌋✨ #shorts",
        ],
        "tags": ["asmr", "lava", "volcano", "satisfying", "mesmerizing",
                 "relaxing", "no talking", "nature", "oddly satisfying", "shorts"],
    },
    {
        "id": "galaxy_space",
        "video_keywords": [
            "milky way stars timelapse",
            "aurora borealis night sky",
            "stars night sky moving",
            "galaxy nebula space",
            "night sky stars rotating",
        ],
        "mixkit_keywords": ["stars", "night-sky", "milky-way", "aurora", "galaxy"],
        "audio_keywords": [
            "space ambient drone calm",
            "cosmic ambient music",
            "deep space sounds",
            "atmospheric ambient pad",
        ],
        "title_templates": [
            "Space ASMR ✨ Stars & Galaxy #shorts #asmr",
            "Milky Way ASMR for Deep Sleep 🌌😴 #shorts",
            "Mesmerizing Galaxy ✨ #shorts",
            "Night Sky Stars ASMR 🌌 #shorts",
        ],
        "tags": ["asmr", "space", "galaxy", "stars", "milky way",
                 "aurora", "relaxing", "sleep", "no talking", "shorts"],
    },
]


class ASMRContentAgent:
    """Produces daily ASMR Shorts: no voice, no text, just satisfying video clips + matching audio."""

    def __init__(self, factory_instance=None):
        self.factory = factory_instance
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.project_root, "data")
        self.cache_dir = os.path.join(self.project_root, "assets", "cache", "asmr")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        self.history_file = os.path.join(self.data_dir, "asmr_history.json")
        # Video: Mixkit only | Audio: Pixabay
        self.mixkit = MixkitService(output_dir=self.cache_dir)
        self.pixabay = PixabayService(output_dir=self.cache_dir)  # Audio only

    def run_daily_automation(self, count: int = 5):
        """Main entry point: Produces and uploads `count` ASMR shorts."""
        logger.info(f"🎬 ASMR Daily Automation: Producing {count} shorts...")

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

            if i < count - 1:
                logger.info("Cooldown 15s before next short...")
                time.sleep(15)

        logger.info(f"\n🎬 ASMR Daily Automation Complete: {success_count}/{count} shorts produced.")
        return success_count

    def _pick_categories(self, count: int) -> List[Dict]:
        """Pick unique categories avoiding recent history."""
        history = self._load_history()
        recent_ids = [h["category"] for h in history[-20:]]

        available = [c for c in ASMR_CATEGORIES if c["id"] not in recent_ids]
        if len(available) < count:
            available = list(ASMR_CATEGORIES)

        random.shuffle(available)
        return available[:count]

    def _produce_single_short(self, category: Dict) -> Optional[Dict]:
        """Produces a single ASMR short: multiple video clips + matching audio → rendered MP4."""

        # 1. Find MULTIPLE video clips (to fill 50-59 seconds)
        video_clips = self._find_multiple_videos(category)
        if not video_clips:
            logger.error(f"No videos found for category: {category['id']}")
            return None

        logger.info(f"Found {len(video_clips)} video clips")

        # 2. Find category-specific audio
        audio_path = self._find_audio(category["audio_keywords"])

        # 3. Calculate total available video duration
        total_video_duration = sum(self._get_duration(v) for v in video_clips)
        target_duration = min(max(total_video_duration, MIN_DURATION), MAX_DURATION)

        # If not enough video, we'll loop the clips
        if total_video_duration < MIN_DURATION:
            target_duration = MIN_DURATION
            logger.info(f"Video clips total {total_video_duration:.1f}s, will loop to reach {target_duration}s")
        else:
            target_duration = min(total_video_duration, MAX_DURATION)

        logger.info(f"Source clips: {total_video_duration:.1f}s total → Target: {target_duration:.1f}s")

        # 4. Render the final short (high quality)
        timestamp = int(time.time())
        output_path = os.path.join(self.cache_dir, f"asmr_{category['id']}_{timestamp}.mp4")

        render_ok = self._render_asmr_short(
            video_clips=video_clips,
            audio_path=audio_path,
            output_path=output_path,
            duration=target_duration,
        )

        if not render_ok:
            return None

        # 5. Build SEO metadata
        title = random.choice(category["title_templates"])
        description = self._build_description(category)
        tags = list(category["tags"])

        return {
            "file_path": output_path,
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": category["id"],
        }

    def _find_multiple_videos(self, category: Dict) -> List[str]:
        """Find multiple video clips from Mixkit."""
        mixkit_keywords = category.get("mixkit_keywords", [])

        if not mixkit_keywords:
            logger.error(f"No mixkit_keywords for category: {category['id']}")
            return []

        try:
            clips = self.mixkit.get_multiple_videos(mixkit_keywords, count=8)
            if clips:
                logger.info(f"Mixkit: {len(clips)} clips found for {category['id']}")
                return clips
        except Exception as e:
            logger.warning(f"Mixkit search failed: {e}")

        return []

    def _find_audio(self, keywords: List[str]) -> Optional[str]:
        """Find category-specific audio from Pixabay."""
        for kw in keywords:
            try:
                path = self.pixabay.get_audio(kw, category="ambient")
                if path and os.path.exists(path):
                    logger.info(f"Audio found: {kw}")
                    return path
            except Exception:
                continue

        # Fallback: local music files
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
            return 15.0

    def _render_asmr_short(self, video_clips: List[str], audio_path: Optional[str],
                           output_path: str, duration: float) -> bool:
        """
        Render high-quality ASMR short:
        - Multiple clips concatenated via concat demuxer
        - 1080x1920 portrait (Full HD Shorts)
        - High quality encoding (CRF 18)
        - Category-specific audio mixed in
        - No text, no subtitles, no narration
        - Smooth crossfade between clips
        """
        width, height = 1080, 1920
        input_args = []

        # Create concat file for multiple clips (looped to fill duration)
        concat_path = os.path.join(self.cache_dir, f"concat_{int(time.time())}.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            # Write clips, repeat if needed to fill duration
            total = 0.0
            safety = 0
            while total < duration + 10 and safety < 30:
                for clip in video_clips:
                    if os.path.exists(clip):
                        f.write(f"file '{clip}'\n")
                        total += self._get_duration(clip)
                        if total >= duration + 10:
                            break
                safety += 1

        # Video input: concat demuxer
        input_args.extend(["-f", "concat", "-safe", "0", "-i", concat_path])

        # Audio input
        if audio_path and os.path.exists(audio_path):
            input_args.extend(["-stream_loop", "-1", "-i", audio_path])
            audio_filter = (
                f"[1:a]atrim=duration={duration},"
                "asetpts=PTS-STARTPTS,"
                "afade=t=in:st=0:d=1.5,"
                f"afade=t=out:st={max(0, duration-3)}:d=3.0,"
                "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                "volume=0.85[aout]"
            )
        else:
            # Very soft brown noise as fallback (YouTube requires audio)
            input_args.extend(["-f", "lavfi", "-i",
                               "anoisesrc=color=brown:sample_rate=44100:amplitude=0.015"])
            audio_filter = (
                f"[1:a]atrim=duration={duration},"
                "asetpts=PTS-STARTPTS,"
                "aformat=sample_fmts=fltp:channel_layouts=stereo[aout]"
            )

        # Video filter: scale to 1080x1920, cinematic color grade
        video_filter = (
            f"[0:v]fps=30,setsar=1,"
            f"scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "eq=brightness=0.02:contrast=1.10:saturation=1.12,"
            "vignette=angle=0.15,"
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
            "-c:v", "libx264",
            "-preset", "medium",     # Better quality than 'fast'
            "-crf", "18",            # High quality
            "-b:v", "8M",            # High bitrate for crisp visuals
            "-maxrate", "10M",
            "-bufsize", "15M",
            "-c:a", "aac",
            "-b:a", "256k",          # High quality audio
            "-ar", "48000",          # 48kHz audio
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info(f"Rendering ASMR short ({duration:.0f}s) at {width}x{height} CRF:18...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Render failed: {result.stderr[:500]}")
                return False
            file_size = os.path.getsize(output_path) / 1_000_000
            logger.info(f"Render complete: {output_path} ({file_size:.1f}MB)")
            return True
        except Exception as e:
            logger.error(f"Render crashed: {e}")
            return False

    def _build_description(self, category: Dict) -> str:
        """Build SEO-optimized description."""
        tag_str = " ".join([f"#{t.replace(' ', '')}" for t in category["tags"][:10]])
        return (
            f"Relaxing ASMR for sleep, stress relief, and relaxation. No talking, just pure satisfying content.\n\n"
            f"🔔 Subscribe for daily satisfying ASMR content!\n"
            f"👍 Like if this video relaxed you!\n"
            f"💬 Comment your favorite ASMR type!\n\n"
            f"{tag_str}\n\n"
            f"#Shorts #ASMR #Satisfying #Relaxing #NoTalking #Sleep #StressRelief #OddlySatisfying"
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
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _log_history(self, category_id: str, youtube_id: str):
        history = self._load_history()
        history.append({
            "category": category_id,
            "youtube_id": youtube_id,
            "produced_at": datetime.now().isoformat(),
        })
        history = history[-100:]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
