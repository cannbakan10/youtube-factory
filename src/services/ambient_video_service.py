import json
import os
import subprocess
import time
import tempfile
from typing import Dict, Optional, Tuple, List

import numpy as np
from PIL import Image

from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AmbientVideoService:
    """Create long ambient videos like fireplace and sleep sounds."""

    AMBIENT_PRESETS: Dict[str, Dict[str, object]] = {
        "fireplace": {
            "title": "1 Hour Cozy Fireplace Ambience",
            "description": "Relax with one hour of cozy fireplace visuals and calm ambience.",
            "tags": ["fireplace", "cozy ambience", "relaxing", "sleep", "study"],
            "video_keywords": ["steady fireplace burning", "static fireplace long take", "calm fire burning"],
            "audio_queries": ["fireplace crackling ambience", "fire crackling slow"],
            "fallback_audio": ["assets/templates/music/nature_1.mp3"],
            "fallback_video": ["assets/templates/fireplace.mp4"],
            "fallback_bg_color": "0x2B1208",
        },
        "sleep": {
            "title": "1 Hour Deep Sleep Soundscape",
            "description": "One hour of soft sleep ambience to help you relax and fall asleep faster.",
            "tags": ["sleep sounds", "deep sleep", "white noise", "rain", "relax"],
            "video_keywords": ["night sky stars timelapse", "moon clouds", "calm night ocean"],
            "audio_queries": ["sleep rain ambience", "deep sleep white noise"],
            "fallback_audio": ["assets/templates/music/nature_2.mp3"],
            "fallback_bg_color": "0x04080F",
        },
        "rain": {
            "title": "1 Hour Rainy Night Ambience",
            "description": "Steady rain ambience for sleep, deep focus, and relaxation.",
            "tags": ["rain sounds", "sleep rain", "focus ambience", "night rain"],
            "video_keywords": ["rain window night", "rainy city night", "rain drops glass"],
            "audio_queries": ["rain ambience sleep", "night rain sound"],
            "fallback_audio": ["assets/templates/music/nature_3.mp3"],
            "fallback_bg_color": "0x0A1421",
        },
        "ocean_sleep": {
            "title": "1 Hour Ocean Waves for Deep Sleep",
            "description": "Calm ocean waves and relaxing visuals to help you fall asleep.",
            "tags": ["ocean waves", "deep sleep", "night ocean", "relaxing sounds"],
            "video_keywords": ["calm ocean night", "moonlight sea", "gentle waves beach"],
            "audio_queries": ["ocean waves sleep", "calm sea ambience"],
            "fallback_audio": ["assets/templates/music/nature_5.mp3"],
            "fallback_bg_color": "0x061328",
        },
        "white_noise": {
            "title": "1 Hour White Noise for Better Sleep",
            "description": "Smooth white noise to mask distractions and help with deep sleep.",
            "tags": ["white noise", "sleep sounds", "insomnia relief", "fan noise"],
            "video_keywords": ["static noise visual", "blur lights"],
            "audio_queries": ["pure white noise"],
            "fallback_audio": [],
            "source": "noise",
            "fallback_noise_color": "white",
            "fallback_bg_color": "0x0A0A0A",
        },
        "rainy_tokyo": {
            "title": "1 Hour Rainy Night in Tokyo",
            "description": "Experience the peaceful atmosphere of Tokyo streets on a rainy night.",
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

        self.pexels = PexelsService(output_dir=self.cache_dir)
        self.pixabay = PixabayService(output_dir=self.cache_dir)

    def create_video(
        self,
        ambient_type: str = "sleep",
        duration_minutes: int = 60,
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
            count=8 if is_long else 3,
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

        title = f"{preset['title']} ({duration_minutes} Minutes)"
        description = (
            f"{preset['description']}\n\n"
            f"Duration: {duration_minutes} minutes\n"
            "Generated by YouTube Factory Ambient Engine"
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
                try:
                    # Try Pexels multi
                    sources = self.pexels.get_multiple_videos(keywords, count=count, orientation=orientation)
                    if sources:
                        logger.info(f"Found {len(sources)} unique clips from Pexels for {ambient_type}")
                        return sources
                except Exception as e:
                    logger.warning(f"Pexels multi-fetch failed: {e}")

                try:
                    # Try Pixabay multi
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

        for rel_path in preset.get("fallback_audio", []):
            abs_path = os.path.join(self.project_root, str(rel_path))
            if os.path.exists(abs_path):
                logger.info(f"Using local fallback ambient audio: {abs_path}")
                return abs_path, "file"

        noise_color = str(preset.get("fallback_noise_color", "pink"))
        logger.warning(
            f"No ambient audio file found. Falling back to ffmpeg noise source ({noise_color})."
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
        input_args = []
        
        # 1. Handle Multiple Video Inputs
        if video_sources:
            # Create a concat file for ffmpeg
            concat_path = os.path.join(os.path.dirname(output_path), "concat_list.txt")
            with open(concat_path, "w", encoding="utf-8") as f:
                for vs in video_sources:
                    if os.path.exists(vs):
                        f.write(f"file '{vs}'\n")
            
            # Use concat demuxer with looping
            input_args.extend(["-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", concat_path])
        else:
            fallback_lavfi = self._fallback_video_lavfi(
                ambient_type=ambient_type,
                width=width,
                height=height,
                bg_color=bg_color,
            )
            input_args.extend(["-f", "lavfi", "-i", fallback_lavfi])

        # 2. Handle Audio
        if audio_mode == "file" and audio_source and os.path.exists(audio_source):
            input_args.extend(["-stream_loop", "-1", "-i", audio_source])
        elif audio_mode == "noise" and audio_source:
            input_args.extend(["-f", "lavfi", "-i", f"anoisesrc=color={audio_source}:sample_rate=44100:amplitude=0.08"])
        else:
            input_args.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        filter_complex = (
            "[0:v]fps=15,setsar=1,"
            f"scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p[vout];"
            f"[1:a]atrim=duration={duration_seconds},"
            "asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.0[aout]"
        )

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-t", str(duration_seconds),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Render failed: {result.stderr}")
                return False
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
