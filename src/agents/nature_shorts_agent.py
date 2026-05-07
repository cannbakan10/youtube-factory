"""
Nature Shorts Agent — Pixabay → YouTube Shorts Pipeline

Fetches high-quality nature / rain / ASMR clips from the Pixabay Video API,
converts them to 9:16 vertical Shorts (≤60 s), keeps the original audio
(no voiceover, no text overlay, no music), generates SEO-rich metadata
with Gemini, and uploads to YouTube.

Reference style: https://www.youtube.com/shorts/ROA_w7MDPcs
  → Pure rain footage, lightning, natural sounds only, 1.5M+ views
"""

import json
import os
import random
import subprocess
import time
import uuid
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

from src.services.pixabay_service import PixabayService
from src.services.youtube_service import YouTubeService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────
# SHORTS CATEGORIES — Pixabay search terms proven to have results
# ─────────────────────────────────────────────────────────────
NATURE_SHORTS_CATEGORIES: Dict[str, Dict] = {
    # ── Rain & Storm ──────────────────────────────────────
    "rain": {
        "search_queries": [
            "heavy rain", "rain drops", "rain window night",
            "rain on water", "pouring rain", "rain puddle",
            "rain street", "rain forest", "rain leaves",
        ],
        "audio_queries": ["rain", "heavy rain", "rain ambience", "rain sounds"],
        "title_templates": [
            "Fall Asleep in {n} Minutes with Heavy Rain Sounds 🌧️",
            "Experience Deep Sleep: Rain Sounds for Relaxation 🌧️",
            "Heavy Rain at Night — Instant Sleep Aid 🌧️💤",
            "Soothing Rain Sounds for Deep Sleep & Focus 🌧️",
            "Rain Sounds to Calm Your Mind & Fall Asleep Fast 🌧️",
            "Pure Heavy Rain — No Music, No Talking 🌧️",
        ],
        "tags": [
            "rain sounds", "rain for sleeping", "heavy rain",
            "rain asmr", "rain sounds for sleep", "sleep sounds",
            "rain no music", "deep sleep rain", "rain ambience",
            "relaxing rain", "nature sounds", "white noise rain",
            "insomnia relief", "calming rain", "storm sounds",
        ],
    },
    "thunderstorm": {
        "search_queries": [
            "thunderstorm", "lightning storm", "thunder rain",
            "storm clouds", "lightning night", "thunder",
        ],
        "audio_queries": ["thunderstorm", "thunder", "storm rain", "thunder rain"],
        "title_templates": [
            "Powerful Thunderstorm for Deep Sleep ⛈️⚡",
            "Thunder & Lightning — Fall Asleep Instantly ⛈️",
            "Epic Thunderstorm Sounds — No Music ⚡💤",
            "Heavy Thunder & Rain for Sleep & Relaxation ⛈️",
            "Thunderstorm at Night — Stress Relief ⛈️🌧️",
        ],
        "tags": [
            "thunderstorm", "thunder sounds", "lightning",
            "storm sounds sleep", "heavy thunder", "thunder rain",
            "thunderstorm asmr", "storm at night", "deep sleep storm",
            "nature sounds", "thunder no music", "relaxing storm",
        ],
    },
    # ── Water ────────────────────────────────────────────
    "ocean": {
        "search_queries": [
            "ocean waves", "sea waves beach", "calm ocean",
            "waves crashing", "ocean sunset", "beach waves",
            "sea shore", "ocean night",
        ],
        "audio_queries": ["ocean waves", "sea waves", "ocean", "beach waves"],
        "title_templates": [
            "Ocean Waves for Deep Sleep & Meditation 🌊💤",
            "Calming Ocean Sounds — Fall Asleep in Minutes 🌊",
            "Beach Waves at Sunset — Pure Relaxation 🌊🌅",
            "Peaceful Ocean Ambience — No Music 🌊",
            "Sea Waves ASMR — Stress Relief & Sleep 🌊",
        ],
        "tags": [
            "ocean waves", "sea sounds", "beach waves",
            "ocean sleep", "wave sounds", "ocean asmr",
            "beach ambience", "calming waves", "sea waves sleep",
            "nature sounds", "ocean meditation", "water sounds",
        ],
    },
    "waterfall": {
        "search_queries": [
            "waterfall", "waterfall forest", "waterfall tropical",
            "waterfall rocks", "cascade water", "jungle waterfall",
        ],
        "audio_queries": ["waterfall", "water stream", "flowing water", "waterfall nature"],
        "title_templates": [
            "Hidden Waterfall — Pure Nature Sounds 🏞️💧",
            "Relaxing Waterfall for Deep Sleep & Focus 🏞️",
            "Waterfall White Noise — Instant Calm 💧",
            "Jungle Waterfall Sounds — No Music 🌿💧",
        ],
        "tags": [
            "waterfall sounds", "waterfall asmr", "waterfall sleep",
            "nature waterfall", "water sounds", "jungle waterfall",
            "relaxing waterfall", "white noise waterfall", "cascade",
            "nature sounds", "deep sleep waterfall",
        ],
    },
    "river": {
        "search_queries": [
            "river stream", "river forest", "creek water",
            "flowing water", "mountain stream", "babbling brook",
        ],
        "audio_queries": ["river", "stream water", "creek", "flowing water"],
        "title_templates": [
            "Gentle River Sounds for Sleep & Study 🏞️📚",
            "Forest Stream — Pure Nature Relaxation 🌲💧",
            "Babbling Brook — Fall Asleep Naturally 💧💤",
            "Mountain Stream Sounds — No Music 🏔️💧",
        ],
        "tags": [
            "river sounds", "stream sounds", "flowing water",
            "creek sounds", "brook sounds", "river sleep",
            "nature river", "water stream asmr", "forest river",
            "relaxing water", "mountain stream",
        ],
    },
    # ── Fire ──────────────────────────────────────────────
    "fireplace": {
        "search_queries": [
            "fireplace", "fire burning", "campfire",
            "bonfire night", "fire flames", "cozy fireplace",
        ],
        "audio_queries": ["fireplace", "crackling fire", "campfire", "fire burning"],
        "title_templates": [
            "Cozy Fireplace Crackling — Instant Relaxation 🔥",
            "Campfire Sounds for Deep Sleep 🔥💤",
            "Fireplace ASMR — No Music, Pure Warmth 🔥",
            "Crackling Fire — Fall Asleep in Minutes 🔥",
        ],
        "tags": [
            "fireplace", "fire sounds", "crackling fire",
            "campfire sounds", "fireplace asmr", "cozy fire",
            "fire sleep", "bonfire sounds", "fireplace ambience",
            "relaxing fire", "fire no music",
        ],
    },
    # ── Forest & Nature ──────────────────────────────────
    "forest": {
        "search_queries": [
            "forest nature", "forest walk", "forest moss",
            "forest trees", "forest path", "green forest",
            "forest morning", "forest fog",
        ],
        "audio_queries": ["forest", "forest birds", "forest ambience", "nature forest"],
        "title_templates": [
            "Peaceful Forest Walk — Nature Sounds 🌲🌿",
            "Forest Birds & Wind — Pure Relaxation 🌲🐦",
            "Deep Forest Ambience — No Music 🌿",
            "Enchanted Forest — Fall Asleep Naturally 🌲💤",
            "Forest Morning Sounds — Stress Relief 🌲☀️",
        ],
        "tags": [
            "forest sounds", "forest ambience", "forest walk",
            "nature sounds forest", "forest birds", "forest asmr",
            "forest sleep", "green forest", "forest meditation",
            "peaceful forest", "nature relaxation",
        ],
    },
    # ── Snow & Winter ────────────────────────────────────
    "snow": {
        "search_queries": [
            "snowfall", "snow falling", "winter snow",
            "snowy forest", "blizzard", "snow landscape",
        ],
        "audio_queries": ["blizzard", "wind snow", "winter wind", "snowstorm"],
        "title_templates": [
            "Gentle Snowfall — Winter Calm & Peace ❄️💤",
            "Snowy Forest — Deep Sleep Sounds ❄️🌲",
            "Blizzard Wind Sounds — Instant Relaxation ❄️",
            "Peaceful Snowfall — No Music ❄️",
        ],
        "tags": [
            "snowfall", "snow sounds", "winter ambience",
            "blizzard sounds", "snowy forest", "snow asmr",
            "winter sleep", "snow falling", "cold wind sounds",
            "winter relaxation", "snow meditation",
        ],
    },
    # ── Sky & Space ──────────────────────────────────────
    "aurora": {
        "search_queries": [
            "aurora borealis", "northern lights",
            "night sky stars", "milky way timelapse",
            "starry sky", "galaxy night",
        ],
        "audio_queries": ["night ambience", "wind calm", "space ambient", "night sounds"],
        "title_templates": [
            "Aurora Borealis — Mesmerizing Night Sky ✨🌌",
            "Northern Lights & Calm Music 🌌💤",
            "Starry Night Sky — Deep Relaxation 🌌✨",
            "Milky Way Timelapse — Pure Wonder 🌌",
        ],
        "tags": [
            "aurora borealis", "northern lights", "night sky",
            "starry sky", "milky way", "galaxy", "space ambience",
            "aurora sleep", "night sky asmr", "stars timelapse",
            "nature sky", "relaxing sky",
        ],
    },
    "sunset": {
        "search_queries": [
            "sunset timelapse", "sunrise", "golden hour",
            "sunset clouds", "sunset ocean", "sunset mountains",
        ],
        "audio_queries": ["sunset", "calm nature", "peaceful", "evening ambience"],
        "title_templates": [
            "Breathtaking Sunset — Pure Calm 🌅",
            "Golden Hour Timelapse — Nature Beauty 🌅✨",
            "Sunset & Waves — Instant Peace 🌅🌊",
            "Sunrise Meditation — Start Your Day 🌅🧘",
        ],
        "tags": [
            "sunset", "sunrise", "golden hour", "sunset timelapse",
            "sunset ocean", "sunset relaxation", "nature sunset",
            "beautiful sunset", "sunset meditation", "sky timelapse",
        ],
    },
    # ── Underwater ───────────────────────────────────────
    "underwater": {
        "search_queries": [
            "underwater", "coral reef", "ocean floor",
            "fish underwater", "deep sea", "underwater bubbles",
        ],
        "audio_queries": ["underwater", "bubbles", "deep ocean", "underwater ambience"],
        "title_templates": [
            "Underwater World — Deep Ocean Calm 🐠🌊",
            "Coral Reef — Mesmerizing Ocean Life 🐠",
            "Deep Sea Sounds — Instant Relaxation 🌊💤",
            "Underwater ASMR — Pure Tranquility 🐠",
        ],
        "tags": [
            "underwater", "coral reef", "ocean floor",
            "deep sea", "underwater sounds", "ocean life",
            "underwater asmr", "fish", "marine life",
            "underwater relaxation", "ocean meditation",
        ],
    },
}

# Target duration for Shorts (YouTube allows up to 3 min, we target 60s)
TARGET_SHORTS_DURATION = 60  # seconds
MAX_SHORTS_DURATION = 180  # YouTube Shorts max (3 minutes)


class NatureShortsAgent:
    """
    Automated agent that creates nature/ambient YouTube Shorts
    from Pixabay stock footage.

    Style: Pure footage + original audio. No text, no voiceover, no music.
    """

    def __init__(self, factory_instance=None):
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.cache_dir = os.path.join(self.project_root, "assets", "cache")
        self.productions_dir = os.path.join(self.project_root, "assets", "productions")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.productions_dir, exist_ok=True)

        self.pixabay = PixabayService(output_dir=self.cache_dir)
        self.youtube_service = None
        self.factory = factory_instance

        # Gemini for metadata generation (optional, falls back to templates)
        self._gemini_model = None

        # Track used videos to avoid repeats
        self.history_path = os.path.join(
            self.project_root, "data", "nature_shorts_history.json"
        )
        self.history = self._load_history()

    # ──────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────

    def create_short(
        self,
        category: Optional[str] = None,
        auto_upload: bool = False,
    ) -> Optional[Dict]:
        """
        Create a single nature YouTube Short.

        Args:
            category: One of NATURE_SHORTS_CATEGORIES keys, or None for random.
            auto_upload: Upload to YouTube automatically.

        Returns:
            Metadata dict with file_path, title, description, tags, etc.
        """
        # Pick category
        if not category or category not in NATURE_SHORTS_CATEGORIES:
            category = random.choice(list(NATURE_SHORTS_CATEGORIES.keys()))
        preset = NATURE_SHORTS_CATEGORIES[category]

        logger.info(f"🌿 Nature Shorts: Creating '{category}' short...")

        # 1. Search & download video from Pixabay
        video_path = self._fetch_video(category, preset)
        if not video_path:
            logger.error(f"No suitable video found for category '{category}'")
            return None

        # 2. Fetch ambient audio if video has no sound
        audio_path = None
        if not self._has_audio_track(video_path):
            logger.info("  🔇 Video has no audio — fetching ambient sound...")
            audio_path = self._fetch_ambient_audio(category, preset)
            if audio_path:
                logger.info(f"  🔊 Ambient audio found!")
            else:
                logger.warning("  ⚠️ No ambient audio found, video will have no sound")
        else:
            logger.info("  🔊 Video has original audio")

        # 3. Convert to 9:16 vertical Shorts format (loop to 60s + add audio)
        timestamp = int(time.time())
        production_id = f"nature_shorts_{category}_{timestamp}"
        out_dir = os.path.join(self.productions_dir, production_id)
        os.makedirs(out_dir, exist_ok=True)

        output_path = os.path.join(out_dir, f"{production_id}.mp4")
        success = self._convert_to_shorts(video_path, output_path, audio_path)
        if not success:
            logger.error("Failed to convert video to Shorts format")
            return None

        # 4. Generate SEO metadata
        metadata = self._generate_metadata(category, preset, output_path, production_id)

        # Save metadata
        meta_path = os.path.join(out_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Nature Short ready: {output_path}")
        logger.info(f"   Title: {metadata['title']}")

        # 5. Upload if requested
        if auto_upload:
            upload_id = self._upload_to_youtube(metadata)
            if upload_id:
                metadata["youtube_id"] = upload_id
                metadata["youtube_url"] = f"https://youtube.com/shorts/{upload_id}"
                # Update metadata file with upload info
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Record in history
        self._record_history(category, metadata)

        return metadata

    def run_daily_automation(
        self,
        count: int = 3,
        auto_upload: bool = True,
    ) -> List[Dict]:
        """
        Run daily automation: create multiple nature shorts from different categories.

        Args:
            count: Number of shorts to create.
            auto_upload: Upload each to YouTube.

        Returns:
            List of metadata dicts.
        """
        logger.info(f"🌿 Nature Shorts Daily Automation: Creating {count} shorts...")

        # Pick diverse categories (no repeats from today)
        today = time.strftime("%Y-%m-%d")
        used_today = set(self.history.get("daily", {}).get(today, []))
        available = [c for c in NATURE_SHORTS_CATEGORIES if c not in used_today]

        if len(available) < count:
            available = list(NATURE_SHORTS_CATEGORIES.keys())
            random.shuffle(available)

        categories = available[:count]
        results = []

        for i, cat in enumerate(categories):
            logger.info(f"\n{'='*50}")
            logger.info(f"📹 Short {i+1}/{count}: Category = {cat}")
            logger.info(f"{'='*50}")

            try:
                result = self.create_short(category=cat, auto_upload=auto_upload)
                if result:
                    results.append(result)
                    # Track daily usage
                    if today not in self.history.setdefault("daily", {}):
                        self.history["daily"][today] = []
                    self.history["daily"][today].append(cat)
                    self._save_history()
            except Exception as e:
                logger.error(f"Failed to create short for '{cat}': {e}")

            # Cooldown between productions
            if i < count - 1:
                logger.info("⏳ Cooldown 15s before next short...")
                time.sleep(15)

        logger.info(f"\n✅ Daily automation complete: {len(results)}/{count} shorts created")
        return results

    # ──────────────────────────────────────────────────────
    # VIDEO FETCHING
    # ──────────────────────────────────────────────────────

    def _fetch_video(self, category: str, preset: Dict) -> Optional[str]:
        """Fetch a suitable video from Pixabay."""
        queries = list(preset["search_queries"])
        random.shuffle(queries)

        # Track what we've already used
        used_ids = set(self.history.get("used_video_ids", []))

        for query in queries:
            logger.info(f"  🔍 Searching Pixabay: '{query}'")
            try:
                video_path = self._search_pixabay_video(query, used_ids)
                if video_path:
                    return video_path
            except Exception as e:
                logger.warning(f"  Search failed for '{query}': {e}")

        return None

    def _search_pixabay_video(self, query: str, used_ids: set) -> Optional[str]:
        """Search Pixabay for a vertical/suitable video and download it."""
        import requests
        from src.utils.retry import APIRateLimiters

        if not self.pixabay.api_key:
            logger.warning("Pixabay API key not configured")
            return None

        APIRateLimiters.pixabay.wait()

        params = {
            "key": self.pixabay.api_key,
            "q": query[:95],
            "video_type": "film",
            "per_page": 20,
            "safesearch": "true",
            "min_width": 720,
            "min_height": 720,
        }

        response = requests.get(
            "https://pixabay.com/api/videos/",
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            logger.warning(f"Pixabay API error: {response.status_code}")
            return None

        data = response.json()
        hits = data.get("hits", [])

        if not hits:
            logger.info(f"  No results for '{query}'")
            return None

        # Filter: prefer videos we haven't used, and those with good duration
        random.shuffle(hits)
        for hit in hits:
            video_id = str(hit.get("id", ""))
            duration = hit.get("duration", 0)

            # Skip already used
            if video_id in used_ids:
                continue

            # Duration filter: want 8-60 seconds (ideal for Shorts)
            if duration < 8 or duration > 120:
                continue

            # Get best quality video
            videos = hit.get("videos", {})
            best = videos.get("large") or videos.get("medium") or videos.get("small")
            if not best or not best.get("url"):
                continue

            video_url = best["url"]
            width = best.get("width", 0)
            height = best.get("height", 0)

            logger.info(
                f"  ✅ Found: id={video_id}, {width}x{height}, "
                f"{duration}s, views={hit.get('views', 0)}"
            )

            # Download
            filename = f"nature_shorts_{uuid.uuid4()}.mp4"
            filepath = os.path.join(self.cache_dir, filename)

            try:
                self.pixabay._download_file(video_url, filepath)
                # Record usage
                used_ids.add(video_id)
                if "used_video_ids" not in self.history:
                    self.history["used_video_ids"] = []
                self.history["used_video_ids"].append(video_id)
                self._save_history()
                return filepath
            except Exception as e:
                logger.warning(f"  Download failed: {e}")

        return None

    # ──────────────────────────────────────────────────────
    # AUDIO FETCHING
    # ──────────────────────────────────────────────────────

    def _has_audio_track(self, video_path: str) -> bool:
        """Check if a video file contains an audio stream."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0", video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _fetch_ambient_audio(self, category: str, preset: Dict) -> Optional[str]:
        """
        Generate ambient audio matching the category using FFmpeg's noise generators.

        Each category gets a tailored noise profile:
        - rain/thunderstorm → brown noise (low rumble, like rain)
        - ocean/waterfall/river → pink noise (balanced, like water)
        - fireplace → brown noise with crackle-like filtering
        - forest/snow/aurora/sunset → pink noise (gentle)
        - underwater → brown noise (deep, muffled)
        """
        # Category → noise profile mapping
        noise_profiles = {
            "rain":         {"color": "brown", "amplitude": "0.6", "bandpass": "200:2000"},
            "thunderstorm": {"color": "brown", "amplitude": "0.7", "bandpass": "80:1500"},
            "ocean":        {"color": "pink",  "amplitude": "0.5", "bandpass": "100:3000"},
            "waterfall":    {"color": "white", "amplitude": "0.4", "bandpass": "300:5000"},
            "river":        {"color": "pink",  "amplitude": "0.4", "bandpass": "200:4000"},
            "fireplace":    {"color": "brown", "amplitude": "0.5", "bandpass": "150:3000"},
            "forest":       {"color": "pink",  "amplitude": "0.3", "bandpass": "200:6000"},
            "snow":         {"color": "pink",  "amplitude": "0.25", "bandpass": "100:2000"},
            "aurora":       {"color": "pink",  "amplitude": "0.2", "bandpass": "80:2000"},
            "sunset":       {"color": "pink",  "amplitude": "0.25", "bandpass": "100:3000"},
            "underwater":   {"color": "brown", "amplitude": "0.5", "bandpass": "50:1000"},
        }

        profile = noise_profiles.get(category, {"color": "brown", "amplitude": "0.4", "bandpass": "100:3000"})

        audio_filename = f"ambient_{category}_{uuid.uuid4()}.wav"
        audio_path = os.path.join(self.cache_dir, audio_filename)

        # Parse bandpass frequencies
        low_freq, high_freq = profile["bandpass"].split(":")

        # Generate ambient noise with FFmpeg
        # anoisesrc generates noise, then bandpass filter shapes it to sound natural
        filter_str = (
            f"anoisesrc=d={TARGET_SHORTS_DURATION + 5}:c={profile['color']}"
            f":r=48000:a={profile['amplitude']},"
            f"bandpass=f={(int(low_freq) + int(high_freq)) // 2}"
            f":width_type=h:w={int(high_freq) - int(low_freq)},"
            f"afade=t=in:d=2,afade=t=out:st={TARGET_SHORTS_DURATION - 2}:d=2"
        )

        cmd = [
            "ffmpeg", "-y", "-v", "warning",
            "-f", "lavfi",
            "-i", filter_str,
            "-t", str(TARGET_SHORTS_DURATION + 2),
            "-c:a", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            audio_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(audio_path):
                logger.info(f"  🎵 Generated {profile['color']} noise ambient for '{category}'")
                return audio_path
            else:
                logger.warning(f"  FFmpeg noise generation failed: {result.stderr}")
        except Exception as e:
            logger.warning(f"  Ambient noise generation failed: {e}")

        return None

    # ──────────────────────────────────────────────────────
    # VIDEO CONVERSION (→ 9:16 Shorts, 60s, with audio)
    # ──────────────────────────────────────────────────────

    def _convert_to_shorts(
        self,
        input_path: str,
        output_path: str,
        external_audio: Optional[str] = None,
    ) -> bool:
        """
        Convert any video to 9:16 vertical Shorts format.

        - Loops short clips to reach ~60 seconds
        - Crops/scales to 1080x1920
        - If video has audio → keeps original audio
        - If video has NO audio → mixes in external ambient audio
        - High quality encoding for YouTube
        """
        # Get source duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", input_path,
        ]
        probe = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe.returncode != 0:
            logger.error(f"FFprobe failed: {probe.stderr}")
            return False

        source_duration = float(probe.stdout.strip() or "30")

        # Target: 60 seconds. If source is shorter, we'll loop it.
        target_duration = TARGET_SHORTS_DURATION  # 60 seconds

        # Calculate loop count needed
        if source_duration < target_duration:
            loop_count = int(target_duration / source_duration) + 1
            logger.info(
                f"  📐 Source: {source_duration:.0f}s → Looping {loop_count}x to reach {target_duration}s"
            )
        else:
            loop_count = 0  # no loop needed, just trim
            logger.info(f"  📐 Source: {source_duration:.0f}s → Trimming to {target_duration}s")

        logger.info(f"  📐 Converting to 9:16 | Target: {target_duration}s")

        # Video filter: scale + crop to 1080x1920
        vf = (
            "scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "setsar=1,"
            "format=yuv420p"
        )

        has_original_audio = self._has_audio_track(input_path)
        has_external_audio = external_audio and os.path.exists(external_audio)

        # Build FFmpeg command — all inputs FIRST, then filters/outputs
        cmd = ["ffmpeg", "-y", "-v", "warning"]

        # INPUT 0: Video (with optional loop)
        if loop_count > 0:
            cmd.extend(["-stream_loop", str(loop_count)])
        cmd.extend(["-i", input_path])

        # INPUT 1: External audio (if needed)
        if has_external_audio:
            cmd.extend(["-stream_loop", "-1", "-i", external_audio])

        # Duration limit
        cmd.extend(["-t", str(target_duration)])

        # Video filter
        cmd.extend(["-vf", vf])

        # Video encoding
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
        ])

        # Audio handling
        if has_external_audio:
            # Use external audio (from second input)
            cmd.extend([
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
            ])
        elif has_original_audio:
            # Keep original audio
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
            ])
        else:
            # No audio available — skip audio stream
            cmd.extend(["-an"])

        cmd.extend([
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            return False

        # Verify output
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            # Verify actual duration
            dur_probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", output_path],
                capture_output=True, text=True,
            )
            actual_dur = float(dur_probe.stdout.strip() or "0")
            has_audio = self._has_audio_track(output_path)
            logger.info(
                f"  ✅ Converted: {size_mb:.1f} MB | "
                f"{actual_dur:.0f}s | Audio: {'✅' if has_audio else '❌'}"
            )
            return True

        return False

    # ──────────────────────────────────────────────────────
    # METADATA GENERATION
    # ──────────────────────────────────────────────────────

    def _generate_metadata(
        self, category: str, preset: Dict, video_path: str, production_id: str
    ) -> Dict:
        """Generate SEO-optimized metadata for the Short."""

        # Try Gemini for a unique title/description
        gemini_meta = self._generate_gemini_metadata(category, preset)

        if gemini_meta:
            title = gemini_meta.get("title", "")
            description = gemini_meta.get("description", "")
        else:
            # Fallback to templates
            title = random.choice(preset["title_templates"])
            # Replace {n} placeholder with a random number
            title = title.replace("{n}", str(random.choice([3, 5, 10])))
            description = self._build_description(category, title)

        tags = list(preset["tags"])
        # Add some generic viral tags
        tags.extend([
            "shorts", "nature", "relaxation", "sleep", "asmr",
            "no music", "ambient", "calming", "peaceful",
        ])
        # Deduplicate
        seen = set()
        unique_tags = []
        for t in tags:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique_tags.append(t)
        tags = unique_tags[:30]  # YouTube max ~30 tags

        return {
            "title": title[:100],  # YouTube title limit
            "description": description,
            "tags": tags,
            "file_path": video_path,
            "category": category,
            "production_id": production_id,
            "video_type": "shorts",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _generate_gemini_metadata(self, category: str, preset: Dict) -> Optional[Dict]:
        """Use Gemini to generate a unique, SEO-optimized title and description."""
        try:
            if not self._gemini_model:
                from google import genai
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                self._gemini_model = client

            sample_titles = preset["title_templates"][:3]

            prompt = f"""You are a YouTube Shorts SEO expert for nature/ambient/sleep content.

Generate a UNIQUE, clickable title and description for a YouTube Short in the "{category}" nature category.

Reference style titles (do NOT copy, create something NEW):
{json.dumps(sample_titles, indent=2)}

RULES:
1. Title must be under 100 characters
2. Title must include 1-2 relevant emojis
3. Title should include HIGH-TRAFFIC keywords: sleep, relax, calm, ASMR, meditation, focus, study
4. Description should be 3-5 lines with relevant keywords naturally embedded
5. Description should mention: deep sleep, relaxation, stress relief, no music
6. Add a call to action (like, subscribe)
7. Output ONLY valid JSON with "title" and "description" keys
8. Write in ENGLISH

Output JSON:"""

            response = self._gemini_model.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

            text = response.text.strip()
            # Clean markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            result = json.loads(text)
            if result.get("title") and result.get("description"):
                logger.info(f"  🤖 Gemini title: {result['title']}")
                return result

        except Exception as e:
            logger.warning(f"Gemini metadata generation failed: {e}")

        return None

    def _build_description(self, category: str, title: str) -> str:
        """Build a template-based description when Gemini is unavailable."""
        category_descriptions = {
            "rain": "Immerse yourself in the soothing sounds of rain.",
            "thunderstorm": "Experience the power of a thunderstorm from the comfort of your bed.",
            "ocean": "Let the rhythmic ocean waves carry you to deep sleep.",
            "waterfall": "The white noise of a waterfall provides instant relaxation.",
            "river": "Gentle river sounds to calm your mind and help you focus.",
            "fireplace": "The cozy crackling of a fireplace for ultimate relaxation.",
            "forest": "Escape to a peaceful forest with birds and rustling leaves.",
            "snow": "The serene silence of snowfall for deep meditation.",
            "aurora": "Watch the mesmerizing dance of the Northern Lights.",
            "sunset": "A breathtaking sunset to end your day in peace.",
            "underwater": "Explore the tranquil depths of the underwater world.",
        }

        desc = category_descriptions.get(category, "Pure nature sounds for relaxation.")

        return f"""{title}

{desc}

✅ Perfect for: Deep Sleep, Study, Meditation, Focus, Stress Relief
✅ No music, no talking — pure natural sounds
✅ Fall asleep faster with nature's white noise

👍 If this helps you relax, please LIKE & SUBSCRIBE for more!

#shorts #nature #sleep #relaxation #asmr #rainsounds #deepsleep #meditation #whitenoise #calm"""

    # ──────────────────────────────────────────────────────
    # YOUTUBE UPLOAD
    # ──────────────────────────────────────────────────────

    def _upload_to_youtube(self, metadata: Dict) -> Optional[str]:
        """Upload the Short to YouTube."""
        if not self.youtube_service:
            self.youtube_service = YouTubeService()

        logger.info(f"  ☁️ Uploading to YouTube: {metadata['title']}")

        upload_id = self.youtube_service.upload_video(
            file_path=metadata["file_path"],
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            video_type="shorts",
        )

        if upload_id:
            logger.info(f"  🎉 Uploaded! https://youtube.com/shorts/{upload_id}")
            return upload_id
        else:
            logger.error("  ❌ Upload failed!")
            return None

    # ──────────────────────────────────────────────────────
    # HISTORY TRACKING
    # ──────────────────────────────────────────────────────

    def _load_history(self) -> Dict:
        """Load usage history to avoid repeats."""
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"used_video_ids": [], "daily": {}}

    def _save_history(self):
        """Save usage history."""
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")

    def _record_history(self, category: str, metadata: Dict):
        """Record a produced short in history."""
        if "productions" not in self.history:
            self.history["productions"] = []

        self.history["productions"].append({
            "category": category,
            "title": metadata["title"],
            "production_id": metadata["production_id"],
            "created_at": metadata["created_at"],
            "youtube_id": metadata.get("youtube_id"),
        })

        # Keep history manageable (last 200)
        if len(self.history["productions"]) > 200:
            self.history["productions"] = self.history["productions"][-200:]
        if len(self.history.get("used_video_ids", [])) > 500:
            self.history["used_video_ids"] = self.history["used_video_ids"][-500:]

        self._save_history()
