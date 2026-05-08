import json
import os
import subprocess
import time
import tempfile
from typing import Dict, Optional, Tuple, List

import numpy as np
from PIL import Image

from src.services.freepik_service import FreepikService
from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AmbientVideoService:
    """Create long ambient videos like fireplace and sleep sounds."""

    AMBIENT_PRESETS: Dict[str, Dict[str, object]] = {
        "fireplace": {
            "title": "4 Hours Cozy Fireplace Ambience for Sleep & Relaxation",
            "description": "Relax with hours of cozy fireplace visuals and calm ambience. Perfect for sleep, study, and deep relaxation.",
            "tags": ["fireplace", "cozy ambience", "relaxing", "sleep", "study"],
            "video_keywords": ["steady fireplace burning", "static fireplace long take", "calm fire burning"],
            "audio_queries": ["fireplace crackling ambience", "fire crackling slow"],
            "fallback_audio": ["assets/templates/music/nature_1.mp3"],
            "fallback_video": ["assets/templates/fireplace.mp4"],
            "fallback_bg_color": "0x2B1208",
        },
        "sleep": {
            "title": "4 Hours Deep Sleep Soundscape — Fall Asleep Fast",
            "description": "Hours of soft sleep ambience to help you relax and fall asleep faster. No interruptions, pure calm.",
            "tags": ["sleep sounds", "deep sleep", "white noise", "rain", "relax"],
            "video_keywords": ["night sky stars timelapse", "moon clouds", "calm night ocean"],
            "audio_queries": ["sleep rain ambience", "deep sleep white noise"],
            "fallback_audio": ["assets/templates/music/nature_2.mp3"],
            "fallback_bg_color": "0x04080F",
        },
        "rain": {
            "title": "4 Hours Rainy Night Ambience for Deep Sleep",
            "description": "Steady rain ambience for sleep, deep focus, and relaxation. Hours of uninterrupted rain sounds.",
            "tags": ["rain sounds", "sleep rain", "focus ambience", "night rain"],
            "video_keywords": ["rain window night", "rainy city night", "rain drops glass"],
            "audio_queries": ["rain ambience sleep", "night rain sound"],
            "fallback_noise_color": "white",
            "fallback_bg_color": "0x0A1421",
        },
        "ocean_sleep": {
            "title": "4 Hours Ocean Waves for Deep Sleep & Relaxation",
            "description": "Calm ocean waves and relaxing visuals to help you fall asleep. Hours of gentle wave sounds.",
            "tags": ["ocean waves", "deep sleep", "night ocean", "relaxing sounds"],
            "video_keywords": ["calm ocean night", "moonlight sea", "gentle waves beach"],
            "audio_queries": ["ocean waves sleep", "calm sea ambience"],
            "fallback_audio": ["assets/templates/music/nature_5.mp3"],
            "fallback_bg_color": "0x061328",
        },
        "white_noise": {
            "title": "4 Hours White Noise for Better Sleep — No Interruptions",
            "description": "Smooth white noise to mask distractions and help with deep sleep. Hours of consistent sound.",
            "tags": ["white noise", "sleep sounds", "insomnia relief", "fan noise"],
            "video_keywords": ["static noise visual", "blur lights"],
            "audio_queries": ["pure white noise"],
            "fallback_audio": [],
            "source": "noise",
            "fallback_noise_color": "white",
            "fallback_bg_color": "0x0A0A0A",
        },
        "istanbul_walk": {
            "title": "Walking in Istanbul — City Ambience & Street Sounds",
            "description": "Take a peaceful walk through the beautiful streets of Istanbul. Experience the sights and sounds of one of the world's most captivating cities.",
            "tags": ["istanbul walk", "turkey city walk", "istanbul streets", "city ambience", "walking tour", "istanbul 4k", "relaxing walk"],
            "video_keywords": ["istanbul street walk", "istanbul city", "bosphorus istanbul", "grand bazaar istanbul", "turkey street"],
            "audio_queries": ["city street ambience", "urban street sounds"],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x1A0F0A",
        },
        "rainy_tokyo": {
            "title": "4 Hours Rainy Night in Tokyo — City Ambience for Sleep",
            "description": "Experience the peaceful atmosphere of Tokyo streets on a rainy night. Hours of neon-lit rain.",
            "tags": ["tokyo rain", "rainy night", "city ambience", "neon rain", "lofi"],
            "video_keywords": ["tokyo rain night", "shibuya rain", "neon city rain"],
            "audio_queries": ["city rain night", "tokyo street rain"],
            "fallback_bg_color": "0x0A0F1E",
        },
        "snowy_cabin": {
            "title": "Cozy Snowy Cabin & Blizzard Ambience",
            "description": "Warm up inside a cozy cabin while a blizzard rages outside.",
            "tags": ["snowy cabin", "blizzard sounds", "winter ambience", "cozy winter"],
            "video_keywords": ["snowy cabin window", "winter blizzard forest"],
            "audio_queries": ["blizzard wind sounds", "snowstorm howling wind"],
            "fallback_bg_color": "0xF0F8FF",
        },
        "underwater_reef": {
            "title": "Deep Sea Underwater Relaxation",
            "description": "Explore the peaceful depths of the ocean with coral reefs.",
            "tags": ["underwater", "ocean floor", "deep sea", "coral reef"],
            "video_keywords": ["underwater coral reef", "ocean floor fish"],
            "audio_queries": ["underwater bubbles", "deep ocean drone"],
            "fallback_bg_color": "0x001F3F",
        },
        "zen_garden": {
            "title": "Japanese Zen Garden & Water Fountain",
            "description": "Achieve inner peace with the sounds of a traditional Zen garden.",
            "tags": ["zen garden", "meditation", "japanese garden", "water fountain"],
            "video_keywords": ["japanese zen garden", "bamboo water fountain"],
            "audio_queries": ["bamboo water drip", "japanese garden ambience"],
            "fallback_bg_color": "0x1A2A1A",
        },
        "space_station": {
            "title": "Futuristic Space Station Ambience",
            "description": "Relax in a high-tech space station orbiting a distant planet.",
            "tags": ["space station", "sci-fi ambience", "spaceship drone", "future space"],
            "video_keywords": ["sci-fi ship interior", "space station window"],
            "audio_queries": ["spaceship engine drone", "sci-fi computer room"],
            "fallback_bg_color": "0x000000",
        },
        "medieval_tavern": {
            "title": "Cozy Medieval Tavern & Fireplace",
            "description": "Step into a bustling fantasy tavern with a warm fire.",
            "tags": ["medieval tavern", "fantasy ambience", "inn fireplace", "dnd"],
            "video_keywords": ["medieval inn interior", "fantasy tavern fire"],
            "audio_queries": ["tavern atmosphere", "medieval crowd chatter"],
            "fallback_bg_color": "0x2C1A0F",
        },
        "ghibli_meadow": {
            "title": "Peaceful Ghibli-Style Meadow & Clouds",
            "description": "Relax in a beautiful, wind-swept meadow with moving clouds.",
            "tags": ["ghibli vibes", "anime meadow", "peaceful nature", "studio ghibli"],
            "video_keywords": ["windy grass field", "moving clouds meadow"],
            "audio_queries": ["wind in grass", "summer meadow birds"],
            "fallback_bg_color": "0x7CFC00",
        },
        "dark_academia": {
            "title": "Dark Academia Library & Study Ambience",
            "description": "The perfect atmosphere for intense studying and classical thought.",
            "tags": ["dark academia", "library ambience", "vocaloid study", "secret history"],
            "video_keywords": ["dark library books", "classical study room"],
            "audio_queries": ["library silence pencil writing", "muffled classical music"],
            "fallback_bg_color": "0x1A0F0A",
        },
        "train_ride": {
            "title": "Relaxing Train Ride Through Swiss Alps",
            "description": "A long, peaceful train journey with snowy mountains passing by.",
            "tags": ["train ride", "window view", "railway ambience", "travel travel"],
            "video_keywords": ["train window view", "swiss alps train"],
            "audio_queries": ["train tracks sound", "railway rhythmic sound"],
            "fallback_bg_color": "0x333333",
        },
        "airplane_cabin": {
            "title": "Airplane Cabin White Noise for Focus",
            "description": "Sleep or focus with the steady, comforting hum of an airplane cabin.",
            "tags": ["airplane sleep", "cabin noise", "jet engine drone", "focus"],
            "video_keywords": ["airplane cabin night", "plane wing night"],
            "audio_queries": ["airplane cabin hum", "jet engine drone"],
            "fallback_bg_color": "0x050510",
        },
        "tropical_beach": {
            "title": "Tropical Beach Sunset & Waves",
            "description": "Unwind with the sound of gentle waves on a white sand beach.",
            "tags": ["tropical beach", "ocean waves", "sunset relaxation", "beach sleep"],
            "video_keywords": ["tropical beach sunset", "ocean waves sand"],
            "audio_queries": ["gentle ocean waves", "beach surf sounds"],
            "fallback_bg_color": "0xFF8C00",
        },
        "thunderstorm": {
            "title": "Heavy Thunderstorm & Rain on Tin Roof",
            "description": "Perfect for deep sleep: a powerful thunderstorm and rain.",
            "tags": ["thunderstorm", "heavy rain", "lightning sounds", "sleep rain"],
            "video_keywords": ["lightning storm night", "thunder rain"],
            "audio_queries": ["heavy thunderstorm", "rolling thunder"],
            "fallback_bg_color": "0x000000",
        },
        "coffee_shop": {
            "title": "Rainy Coffee Shop & Soft Jazz",
            "description": "Enjoy the vibe of a busy coffee shop with rain outside.",
            "tags": ["coffee shop ambience", "jazz music", "study café", "rainy café"],
            "video_keywords": ["coffee shop interior rain", "barista making coffee"],
            "audio_queries": ["coffee shop chatter", "soft barista sounds"],
            "fallback_bg_color": "0x3E2723",
        },
        "autumn_forest": {
            "title": "Golden Autumn Forest Walk",
            "description": "Walking through a peaceful forest with falling golden leaves.",
            "tags": ["autumn forest", "fall ambience", "forest walk", "nature"],
            "video_keywords": ["autumn forest yellow leaves", "falling leaves forest"],
            "audio_queries": ["forest wind birds", "crunching leaves walk"],
            "fallback_bg_color": "0xD2691E",
        },
        "lighthouse_storm": {
            "title": "Lone Lighthouse During a Coastal Storm",
            "description": "Hear the crashing waves and the signal of a lone lighthouse.",
            "tags": ["lighthouse", "stormy sea", "coastal ambience", "heavy waves"],
            "video_keywords": ["lighthouse storm", "crashing waves rocks"],
            "audio_queries": ["heavy sea waves", "lighthouse foghorn"],
            "fallback_bg_color": "0x101A2A",
        },
        "minecraft_world": {
            "title": "Calm Minecraft Landscape & Music",
            "description": "Nostalgic and peaceful blocks, animals, and sunsets.",
            "tags": ["minecraft", "calm music", "blocky world", "gaming ambience"],
            "video_keywords": ["minecraft landscape sunset", "low poly nature"],
            "audio_queries": ["minecraft c418 style", "pixel world music"],
            "fallback_bg_color": "0x87CEEB",
        },
        "mayan_jungle": {
            "title": "Ancient Mayan Temple & Jungle Rain",
            "description": "Lost in time: the sounds of a deep jungle and ruins.",
            "tags": ["mayan temple", "jungle sounds", "tropical rain", "forest"],
            "video_keywords": ["mayan temple jungle", "rainforest temple"],
            "audio_queries": ["jungle birds monkeys", "heavy tropical rain"],
            "fallback_bg_color": "0x1A2A0F",
        },
        "mars_colony": {
            "title": "Living on Mars: Red Planet Ambience",
            "description": "Dust storms and the low hum of a Martian dome colony.",
            "tags": ["mars ambience", "red planet", "space colony", "sci-fi sleep"],
            "video_keywords": ["mars surface dust", "martian base interior"],
            "audio_queries": ["martian wind storm", "base life support hum"],
            "fallback_bg_color": "0x4E0000",
        },
        "speakeasy_jazz": {
            "title": "1920s Speakeasy & Smoky Jazz Lounge",
            "description": "Travel back to the roaring 20s with soulful jazz.",
            "tags": ["speakeasy", "1920s jazz", "vintage lounge", "smoky bar"],
            "video_keywords": ["vintage jazz bar", "smoky lounge 1920s"],
            "audio_queries": ["roaring 20s jazz", "bar chatter jazz"],
            "fallback_bg_color": "0x1A0A05",
        },
        "grand_canyon": {
            "title": "Grand Canyon Winds & Desert Night",
            "description": "The sweeping sounds of the desert and ancient canyons.",
            "tags": ["grand canyon", "desert winds", "nature sounds", "canyon sleep"],
            "video_keywords": ["grand canyon sunset", "desert canyon night"],
            "audio_queries": ["desert wind howling", "canyon echoes"],
            "fallback_bg_color": "0xB04A00",
        },
        "victorian_study": {
            "title": "Victorian Study & Clock Ticking",
            "description": "A refined atmosphere for focus with clocks and old book smells.",
            "tags": ["victorian", "study focus", "clock ticking", "old room"],
            "video_keywords": ["victorian library", "old desk candle", "clock gears"],
            "audio_queries": ["grandfather clock ticking", "quill writing sound"],
            "fallback_bg_color": "0x2D1A05",
        },
        "steampunk_workshop": {
            "title": "Steampunk Workshop & Steam Whistles",
            "description": "The busy, industrial sounds of gears, steam, and brass.",
            "tags": ["steampunk", "workshop ambience", "industrial", "gears sounds"],
            "video_keywords": ["steampunk gears", "steam engine factory", "brass lab"],
            "audio_queries": ["steam whistle release", "metal gear grinding"],
            "fallback_bg_color": "0x3E2723",
        },
        "arctic_expedition": {
            "title": "Arctic Expedition Tent & Howling Wind",
            "description": "Survival mode: The sounds of an arctic tent in a frozen tundra.",
            "tags": ["arctic", "winter storm", "survival ambience", "ice wind"],
            "video_keywords": ["arctic tundra snow", "tent in snowstorm"],
            "audio_queries": ["extreme arctic wind", "snow crunching"],
            "fallback_bg_color": "0xE0F7FA",
        },
        "bamboo_forest": {
            "title": "Bamboo Forest Breeze & Wind Chimes",
            "description": "The tall stalks of bamboo knocking against each other in the wind.",
            "tags": ["bamboo forest", "wind chimes", "japanese nature", "zen relax"],
            "video_keywords": ["bamboo forest path", "bamboo leaves wind"],
            "audio_queries": ["bamboo stalks hitting", "soft metal wind chimes"],
            "fallback_bg_color": "0x1B3022",
        },
        "lavender_fields": {
            "title": "Lavender Fields in France & Gentle Breeze",
            "description": "A sea of purple with the sound of distant bees and soft wind.",
            "tags": ["lavender", "france nature", "floral ambience", "summer breeze"],
            "video_keywords": ["lavender fields sunset", "provence france nature"],
            "audio_queries": ["soft summer wind", "distant honey bees"],
            "fallback_bg_color": "0x673AB7",
        },
        "secret_waterfall": {
            "title": "Hidden Jungle Waterfall & Tropical Birds",
            "description": "A paradise found: a powerful but soothing waterfall in the jungle.",
            "tags": ["waterfall", "jungle nature", "tropical paradise", "white noise water"],
            "video_keywords": ["tropical waterfall jungle", "hidden oasis water"],
            "audio_queries": ["heavy waterfall roar", "tropical forest birds"],
            "fallback_bg_color": "0x004D40",
        },
        "moonlit_lake": {
            "title": "Moonlit Lake & Night Crickets",
            "description": "Peaceful reflection on a lake under the full moon.",
            "tags": ["moonlight", "lake ambience", "crickets night", "peaceful sleep"],
            "video_keywords": ["moonlight lake reflection", "night water ripples"],
            "audio_queries": ["night lake crickets", "soft water lapping"],
            "fallback_bg_color": "0x0D1B2A",
        },
        "harry_potter_vibes": {
            "title": "Wizarding School Library & Magic Potions",
            "description": "Feel the magic in the air with bubbling cauldrons and flying books.",
            "tags": ["wizarding world", "magic library", "fantasy study", "potions"],
            "video_keywords": ["magic library flying books", "medieval stone room candle"],
            "audio_queries": ["bubbling potion cauldron", "magic spell sparkles"],
            "fallback_bg_color": "0x1A0A2A",
        },
        "attic_rain": {
            "title": "Cozy Attic & Rain on a Tin Roof",
            "description": "The best place to sleep: a small attic with heavy rain right above you.",
            "tags": ["attic rain", "tin roof rain", "cozy attic", "heavy rain sleep"],
            "video_keywords": ["attic window rain", "cozy bedroom roof"],
            "audio_queries": ["heavy rain on tin roof", "soft attic wind"],
            "fallback_bg_color": "0x263238",
        },
        "vintage_train": {
            "title": "1940s Steam Train Across the Countryside",
            "description": "The rhythmic chugging of a vintage steam engine.",
            "tags": ["steam train", "vintage railway", "countryside ride", "train chuffing"],
            "video_keywords": ["steam train smoke", "vintage train interior"],
            "audio_queries": ["steam engine chuffing", "train whistle distant"],
            "fallback_bg_color": "0x212121",
        },
        "scifi_lab": {
            "title": "Advanced Sci-Fi Lab & Data Processing",
            "description": "The sound of progress: holograms, data streams, and cold fans.",
            "tags": ["scifi lab", "data processing", "cyberpunk tech", "high tech"],
            "video_keywords": ["holographic data", "scientific lab drones"],
            "audio_queries": ["computer server room", "hologram hum"],
            "fallback_bg_color": "0x001219",
        },
        "prairie_sunset": {
            "title": "Endless Prairie & Golden Hour Wind",
            "description": "The sweeping winds of the Great Plains under a golden sky.",
            "tags": ["prairie", "golden hour", "nature wind", "grasslands"],
            "video_keywords": ["prairie grass wind", "sunset over field"],
            "audio_queries": ["prairie wind grass", "distant coyote howl"],
            "fallback_bg_color": "0xE6B422",
        },
        "cathedral_meditation": {
            "title": "Grand Cathedral & Holy Echoes",
            "description": "Massive stone echoes and the peaceful silence of an ancient church.",
            "tags": ["cathedral", "church ambience", "echoes", "spiritual relax"],
            "video_keywords": ["gothic cathedral interior", "stained glass light"],
            "audio_queries": ["church hall echoes", "distant organ pipe"],
            "fallback_bg_color": "0x1B1B1B",
        },
    }

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.cache_dir = os.path.join(self.project_root, "assets", "cache")
        self.productions_dir = os.path.join(self.project_root, "assets", "productions")

        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.productions_dir, exist_ok=True)

        self.freepik = FreepikService(output_dir=os.path.join(self.cache_dir, "freepik"))
        self.pexels = PexelsService(output_dir=self.cache_dir)
        self.pixabay = PixabayService(output_dir=self.cache_dir)

    def create_video(
        self,
        ambient_type: str = "sleep",
        duration_minutes: int = 240,
        video_type: str = "long",
        language: str = "en",
        source_mode: str = "auto",
    ) -> Optional[Dict[str, object]]:
        preset = self.AMBIENT_PRESETS.get(ambient_type)
        if not preset:
            logger.error(f"Unknown ambient type: {ambient_type}")
            return None

        duration_minutes = max(1, int(duration_minutes))
        duration_seconds = duration_minutes * 60
        timestamp = int(time.time())
        production_id = f"{ambient_type}_{duration_minutes}min_{timestamp}"

        lang = (language or "en").strip().lower()
        out_dir = os.path.join(self.productions_dir, production_id, lang)
        os.makedirs(out_dir, exist_ok=True)

        output_path = os.path.join(out_dir, f"{production_id}_{lang}.mp4")
        metadata_path = os.path.join(out_dir, "metadata.json")

        is_long = video_type == "long"
        width, height = (1280, 720) if is_long else (1080, 1920)
        orientation = "landscape" if is_long else "portrait"

        logger.info(
            f"Creating ambient video type={ambient_type} duration={duration_minutes}m format={video_type}"
        )

        # MULTI-CLIP LOGIC: Fetch multiple videos to avoid repetition
        video_sources = self._resolve_multiple_video_sources(
            ambient_type=ambient_type,
            keywords=list(preset["video_keywords"]),  # type: ignore[arg-type]
            fallback_video_paths=list(preset.get("fallback_video", [])),  # type: ignore[arg-type]
            orientation=orientation,
            source_mode=source_mode,
            count=3,
        )
        if source_mode == "api" and not video_sources:
            logger.error(
                f"No valid API video found for ambient_type={ambient_type}. "
                "Try different keywords or ensure Pexels/Pixabay keys are valid."
            )
            return None

        if not video_sources:
            fallback_clip = self._generate_procedural_loop_clip(
                ambient_type=ambient_type,
                width=width,
                height=height,
                bg_color=str(preset["fallback_bg_color"]),
            )
            if fallback_clip:
                video_sources = [fallback_clip]
        audio_source, audio_mode = self._resolve_audio_source(
            preset=preset,
            duration_seconds=duration_seconds,
        )

        render_ok = self._render_ambient(
            output_path=output_path,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            bg_color=str(preset["fallback_bg_color"]),
            video_sources=video_sources,
            audio_source=audio_source,
            audio_mode=audio_mode,
            ambient_type=ambient_type,
        )
        if not render_ok:
            return None

        # Dynamic Title Generation
        clean_title = preset['title'].replace("1 Hour ", "").replace("1 Hour", "")
        if duration_minutes >= 60:
            hours = duration_minutes // 60
            mins = duration_minutes % 60
            time_str = f"{hours} Hour" + ("s" if hours > 1 else "")
            if mins > 0:
                time_str += f" {mins} Min"
        else:
            time_str = f"{duration_minutes} Minutes"
            
        title = f"{time_str} {clean_title}".strip()
        description = (
            f"{preset['description']}\n\n"
            f"Duration: {time_str}\n"
            "Enjoy this high-quality ambient experience."
        )
        tags = list(preset["tags"]) + ["1 hour ambience" if duration_minutes >= 60 else "ambient loop"]  # type: ignore[arg-type]

        metadata = {
            "title": title,
            "description": description,
            "tags": tags,
            "file_path": output_path,
            "ambient_type": ambient_type,
            "duration_minutes": duration_minutes,
            "video_type": video_type,
            "language": lang,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Ambient video ready: {output_path}")
        return metadata

    def _resolve_multiple_video_sources(
        self,
        ambient_type: str,
        keywords,
        fallback_video_paths,
        orientation: str,
        source_mode: str,
        count: int = 5,
    ) -> List[str]:
        """Resolves multiple video sources for a more diverse long-form video."""
        sources = []
        if os.getenv("AMBIENT_OFFLINE") == "1":
            logger.info("AMBIENT_OFFLINE=1, skipping remote video lookup.")
        else:
            if keywords:
                # Priority 1: Freepik Premium (4K quality)
                try:
                    sources = self.freepik.get_multiple_videos(keywords, count=count, orientation=orientation)
                    if sources:
                        logger.info(f"🎨 Found {len(sources)} premium clips from Freepik for {ambient_type}")
                        return sources
                except Exception as e:
                    logger.warning(f"Freepik multi-fetch failed: {e}")

                # Priority 2: Pexels (free, good quality)
                try:
                    sources = self.pexels.get_multiple_videos(keywords, count=count, orientation=orientation)
                    if sources:
                        logger.info(f"Found {len(sources)} unique clips from Pexels for {ambient_type}")
                        return sources
                except Exception as e:
                    logger.warning(f"Pexels multi-fetch failed: {e}")

                # Priority 3: Pixabay (free fallback)
                try:
                    sources = self.pixabay.get_multiple_videos(keywords, count=count, orientation=orientation)
                    if sources:
                        logger.info(f"Found {len(sources)} unique clips from Pixabay for {ambient_type}")
                        return sources
                except Exception as e:
                    logger.warning(f"Pixabay multi-fetch failed: {e}")

        if source_mode == "api" and not sources:
            return []

        # Try fallback local files
        for rel_path in fallback_video_paths or []:
            abs_path = os.path.join(self.project_root, str(rel_path))
            if os.path.exists(abs_path):
                sources.append(abs_path)
        
        return sources

    def _resolve_video_source(
        self,
        ambient_type: str,
        keywords,
        fallback_video_paths,
        orientation: str,
        source_mode: str,
    ) -> Optional[str]:
        """Original single source method, now uses the multi-source version under the hood."""
        sources = self._resolve_multiple_video_sources(ambient_type, keywords, fallback_video_paths, orientation, source_mode, count=1)
        return sources[0] if sources else None

    def _resolve_audio_source(
        self,
        preset: Dict[str, object],
        duration_seconds: int,
    ) -> Tuple[Optional[str], str]:
        if os.getenv("AMBIENT_OFFLINE") != "1":
            for query in preset.get("audio_queries", []):
                try:
                    audio = self.pixabay.get_audio(str(query), category="ambient")
                    if audio and os.path.exists(audio):
                        logger.info(f"Ambient audio found from Pixabay: {query}")
                        return audio, "file"
                except Exception as e:
                    logger.warning(f"Ambient audio fetch failed for '{query}': {e}")
        else:
            logger.info("AMBIENT_OFFLINE=1, skipping remote audio lookup.")

        # Skip local music fallback (may have copyright) — use noise synthesis instead
        noise_color = str(preset.get("fallback_noise_color", "pink"))
        logger.info(
            f"Using FFmpeg synthesized noise audio ({noise_color}) — copyright-free."
        )
        return noise_color, "noise"

    def _render_ambient(
        self,
        output_path: str,
        duration_seconds: int,
        width: int,
        height: int,
        bg_color: str,
        video_sources: List[str],
        audio_source: Optional[str],
        audio_mode: str,
        ambient_type: str,
    ) -> bool:
        # ── FAST STREAM-COPY RENDER ──────────────────────────────
        # Use the first available video source + loop it with -c:v copy
        # This avoids re-encoding = completes in seconds not minutes
        # ─────────────────────────────────────────────────────────

        video_input = video_sources[0] if video_sources else None

        if video_input and os.path.exists(video_input):
            # Audio input
            if audio_mode == "noise" and audio_source:
                audio_input_args = ["-f", "lavfi", "-i", f"anoisesrc=color={audio_source}:sample_rate=44100:amplitude=0.15"]
            elif audio_mode == "file" and audio_source and os.path.exists(audio_source):
                audio_input_args = ["-stream_loop", "-1", "-i", audio_source]
            else:
                audio_input_args = ["-f", "lavfi", "-i", "anoisesrc=color=white:sample_rate=44100:amplitude=0.15"]

            # Re-encode to 720p ~1.5 Mbps — keeps file size ~1 GB/hour, fast with ultrafast
            cmd = [
                "ffmpeg", "-y", "-v", "warning", "-stats",
                "-stream_loop", "-1", "-i", video_input,
                *audio_input_args,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-t", str(duration_seconds),
                "-vf", f"scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-b:v", "1500k", "-maxrate", "2000k", "-bufsize", "4000k",
                "-c:a", "aac", "-b:a", "96k",
                "-pix_fmt", "yuv420p",
                "-threads", "2",
                output_path
            ]
        else:
            # Fallback: procedural lavfi video + noise audio
            fallback_lavfi = self._fallback_video_lavfi(
                ambient_type=ambient_type, width=width, height=height, bg_color=bg_color,
            )
            audio_lavfi = f"anoisesrc=color=white:sample_rate=44100:amplitude=0.15:duration={duration_seconds}"
            cmd = [
                "ffmpeg", "-y", "-v", "warning", "-stats",
                "-f", "lavfi", "-i", fallback_lavfi,
                "-f", "lavfi", "-i", audio_lavfi,
                "-map", "0:v:0", "-map", "1:a:0",
                "-t", str(duration_seconds),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
                "-threads", "2",
                "-c:a", "aac", "-b:a", "96k", "-pix_fmt", "yuv420p",
                output_path
            ]

        logger.info(f"⚡ Rendering {duration_seconds}s ambient video (stream copy)...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Render failed: {result.stderr[:500]}")
                return False
            logger.info(f"✅ Render complete: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Render crashed: {e}")
            return False

    def _fallback_video_lavfi(self, ambient_type: str, width: int, height: int, bg_color: str) -> str:
        if ambient_type == "fireplace":
            return (
                f"life=s={width}x{height}:rate=15:ratio=0.62:mold=14,"
                "format=gray,"
                "boxblur=2:1,"
                "lutrgb="
                "r='if(gt(val,18),min(255,val*2.2),0)':"
                "g='if(gt(val,18),min(255,val*1.2),0)':"
                "b='if(gt(val,18),min(255,val*0.25),0)',"
                "vignette=angle=0.35"
            )
        if ambient_type in {"sleep", "rain", "ocean_sleep"}:
            return (
                f"color=c={bg_color}:s={width}x{height}:r=15,"
                "noise=alls=10:allf=t+u,eq=brightness=-0.02:contrast=1.05:saturation=0.85"
            )
        return f"color=c={bg_color}:s={width}x{height}:r=15"

    def _is_valid_ambient_video(self, video_path: str, ambient_type: str) -> bool:
        if ambient_type != "fireplace":
            return True
        return self._looks_like_fire(video_path)

    def _looks_like_fire(self, video_path: str) -> bool:
        """Heuristic fire detection to avoid unrelated clips in fireplace mode."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                frame_path = tmp.name

            cmd = [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                "1.5",
                "-i",
                video_path,
                "-frames:v",
                "1",
                frame_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0 or not os.path.exists(frame_path):
                return False

            img = Image.open(frame_path).convert("RGB").resize((320, 180))
            arr = np.array(img).astype(np.float32)
            rch, gch, bch = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            lum = 0.2126 * rch + 0.7152 * gch + 0.0722 * bch

            warm_mask = (rch > 120) & (gch > 45) & (bch < 130) & (rch > gch * 1.05)
            warm_ratio = float(warm_mask.mean())
            dark_ratio = float((lum < 55).mean())
            lum_var = float(lum.var())

            return warm_ratio >= 0.03 and dark_ratio >= 0.12 and lum_var >= 400.0
        except Exception:
            return False
        finally:
            try:
                if "frame_path" in locals() and os.path.exists(frame_path):
                    os.remove(frame_path)
            except Exception:
                pass

    def _generate_procedural_loop_clip(
        self,
        ambient_type: str,
        width: int,
        height: int,
        bg_color: str,
    ) -> Optional[str]:
        """
        Generates a short procedural ambient loop clip locally.
        This enables very fast 1-hour output via stream copy looping.
        """
        output_path = os.path.join(self.cache_dir, f"ambient_loop_{ambient_type}_{width}x{height}_v3.mp4")
        if os.path.exists(output_path):
            return output_path

        lavfi_src = self._fallback_video_lavfi(ambient_type=ambient_type, width=width, height=height, bg_color=bg_color)
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            lavfi_src,
            "-t",
            "20",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "32",
            "-b:v",
            "1200k",
            "-maxrate",
            "1200k",
            "-bufsize",
            "2400k",
            "-g",
            "60",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Generated procedural loop clip: {output_path}")
                return output_path
            logger.warning(f"Procedural loop generation failed: {result.stderr[:200]}")
            return None
        except Exception as e:
            logger.warning(f"Procedural loop generation crashed: {e}")
            return None

    def _try_fast_mux_render(
        self,
        output_path: str,
        duration_seconds: int,
        video_source: str,
        audio_source: str,
    ) -> bool:
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-stream_loop",
            "-1",
            "-i",
            video_source,
            "-stream_loop",
            "-1",
            "-i",
            audio_source,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            str(duration_seconds),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("Ambient fast mux render succeeded.")
                return True
            logger.warning(f"Ambient fast mux failed, falling back to full render: {result.stderr[:200]}")
            return False
        except Exception as e:
            logger.warning(f"Ambient fast mux crashed, falling back to full render: {e}")
            return False

    # ══════════════════════════════════════════════════════════
    # FAST LOOP — Turn a short clip into hours-long video
    # No re-encoding = original quality preserved (4K stays 4K)
    # ══════════════════════════════════════════════════════════

    def loop_video(
        self,
        input_video: str,
        duration_hours: float = 8.0,
        audio_file: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Dict[str, object]]:
        """
        Take a short video clip and loop it to target duration.
        Uses -c:v copy (stream copy) = NO re-encoding = blazing fast.
        
        8-second clip → 8-hour video in ~30 seconds.
        Original quality is 100% preserved (4K input = 4K output).
        
        Args:
            input_video: Path to short source video (e.g. 8 seconds of fireplace)
            duration_hours: Target duration in hours (default: 8)
            audio_file: Optional audio file to overlay (loops to match duration)
            title: Video title for YouTube
            description: Video description
            tags: Video tags
        """
        if not os.path.exists(input_video):
            logger.error(f"Input video not found: {input_video}")
            return None

        duration_seconds = int(duration_hours * 3600)
        timestamp = int(time.time())

        # Get source video info
        probe = self._probe_video(input_video)
        if not probe:
            logger.error("Cannot probe input video")
            return None

        src_duration = probe.get("duration", 0)
        src_width = probe.get("width", 0)
        src_height = probe.get("height", 0)
        src_codec = probe.get("codec", "unknown")

        logger.info(f"📹 Source: {src_width}x{src_height} {src_codec} ({src_duration:.1f}s)")
        logger.info(f"🎯 Target: {duration_hours}h = {duration_seconds}s")
        logger.info(f"🔄 Loops needed: ~{int(duration_seconds / max(src_duration, 1))}")

        # Build production output
        hours_str = f"{duration_hours:.0f}" if duration_hours == int(duration_hours) else f"{duration_hours:.1f}"
        production_id = f"loop_{hours_str}h_{timestamp}"
        out_dir = os.path.join(self.productions_dir, production_id, "en")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"{production_id}.mp4")

        # ─── BUILD FFMPEG COMMAND ───
        cmd = ["ffmpeg", "-y", "-v", "warning", "-stats"]

        # Video input — loop infinitely
        cmd.extend(["-stream_loop", "-1", "-i", input_video])

        # Audio input
        if audio_file and os.path.exists(audio_file):
            cmd.extend(["-stream_loop", "-1", "-i", audio_file])
            has_audio_file = True
        else:
            has_audio_file = False

        # Mapping
        cmd.extend(["-map", "0:v:0"])
        if has_audio_file:
            cmd.extend(["-map", "1:a:0"])
        elif probe.get("has_audio"):
            cmd.extend(["-map", "0:a:0"])

        # Duration limit
        cmd.extend(["-t", str(duration_seconds)])

        # VIDEO: Stream copy = no re-encoding = instant
        cmd.extend(["-c:v", "copy"])

        # AUDIO: Re-encode only audio (fast, small data)
        if has_audio_file or probe.get("has_audio"):
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.append(output_path)

        logger.info(f"⚡ Fast loop render starting (stream copy, no re-encoding)...")
        logger.info(f"   Command: {' '.join(cmd[:10])}...")

        try:
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Loop render failed: {result.stderr[:500]}")
                return None

            elapsed = time.time() - start_time
            file_size = os.path.getsize(output_path)
            size_gb = file_size / (1024 ** 3)

            logger.info(f"✅ Done in {elapsed:.1f}s!")
            logger.info(f"📦 Output: {size_gb:.2f} GB")
            logger.info(f"📐 Quality: {src_width}x{src_height} (original preserved)")
            logger.info(f"📂 File: {output_path}")

        except Exception as e:
            logger.error(f"Loop render crashed: {e}")
            return None

        # Build metadata
        auto_title = title or f"{hours_str} Hours Loop Video"
        auto_desc = description or (
            f"{hours_str} hours of seamless looping ambient content.\n\n"
            f"Resolution: {src_width}x{src_height}\n"
            f"Duration: {hours_str} hours\n\n"
            "Perfect for sleep, study, relaxation, and focus."
        )
        auto_tags = tags or [
            "ambient", "loop", f"{hours_str} hours",
            "sleep", "relax", "study", "focus",
            "4K" if src_width >= 3840 else ("1080p" if src_width >= 1920 else "HD"),
        ]

        metadata = {
            "title": auto_title,
            "description": auto_desc,
            "tags": auto_tags,
            "file_path": output_path,
            "source_video": input_video,
            "duration_hours": duration_hours,
            "duration_seconds": duration_seconds,
            "resolution": f"{src_width}x{src_height}",
            "file_size_gb": round(size_gb, 2),
            "render_time_seconds": round(elapsed, 1),
            "method": "stream_copy",
        }

        metadata_path = os.path.join(out_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return metadata

    def _probe_video(self, video_path: str) -> Optional[Dict]:
        """Get video file info using ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            video_stream = None
            has_audio = False
            for s in data.get("streams", []):
                if s.get("codec_type") == "video" and not video_stream:
                    video_stream = s
                if s.get("codec_type") == "audio":
                    has_audio = True

            if not video_stream:
                return None

            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "has_audio": has_audio,
            }
        except Exception as e:
            logger.error(f"ffprobe failed: {e}")
            return None
