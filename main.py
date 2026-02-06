import os
import argparse
import shutil
import time
import json
import sys
import importlib.metadata
import unicodedata

# Python 3.9 Compatibility Fix for google-genai
if sys.version_info < (3, 10):
    try:
        import importlib_metadata
        if not hasattr(importlib.metadata, 'packages_distributions'):
            importlib.metadata.packages_distributions = importlib_metadata.packages_distributions
    except ImportError:
        pass

# Silence common SSL/NotOpenSSLWarning that confuses users on Mac
import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

from dotenv import load_dotenv

# Setup global logging BEFORE importing other modules
from src.utils.logger import setup_global_logging, get_logger
setup_global_logging()
logger = get_logger("main")

from src.agents.researcher import ResearchAgent
from src.agents.scriptwriter import ScriptWriter
from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.services.tts_service import TTSService
from src.services.youtube_service import YouTubeService
from src.services.branding_service import BrandingService
from src.services.ambient_video_service import AmbientVideoService
from src.core.ffmpeg_engine import VideoEngine
from src.agents.trend_agent import TrendAgent
from src.agents.viral_analyzer import ViralAnalyzer

load_dotenv()

# Constants
BULK_MODE_COOLDOWN = 30  # seconds between bulk video productions

# Available viral categories for --viral command
VIRAL_CATEGORIES = ["facts", "science", "history", "psychology", "nature", "tech", "mystery", "lifestyle"]
AMBIENT_TYPES = list(AmbientVideoService.AMBIENT_PRESETS.keys())


class YoutubeFactory:
    def __init__(self):
        required_keys = ["GEMINI_API_KEY", "PEXELS_API_KEY", "TAVILY_API_KEY", "ELEVENLABS_API_KEY"]
        missing = [k for k in required_keys if not os.getenv(k)]
        if missing:
            logger.warning(f"Missing API keys: {', '.join(missing)}")

        self.researcher = self._safe_init(ResearchAgent, "ResearchAgent")
        self.scriptwriter = self._safe_init(ScriptWriter, "ScriptWriter")
        self.trend_agent = self._safe_init(TrendAgent, "TrendAgent")
        self.viral_analyzer = self._safe_init(ViralAnalyzer, "ViralAnalyzer")
        self.branding = self._safe_init(BrandingService, "BrandingService")
        self.youtube_service = None

    def _safe_init(self, cls, name):
        try:
            return cls()
        except Exception as e:
            logger.warning(f"{name} disabled: {e}")
            return None

    def run(self, topic, languages=None, auto_upload=False, mode="info", video_type="shorts", style_context=None):
        if languages is None:
            languages = ["en"]

        if not self.scriptwriter:
            logger.error("ScriptWriter is unavailable. Check your GEMINI/OPENAI configuration.")
            return None

        is_long = video_type == "long"
        timestamp = int(time.time())
        topic_ascii = unicodedata.normalize('NFKD', topic).encode('ascii', 'ignore').decode('ascii')
        topic_slug = "".join(c for c in topic_ascii if c.isalnum() or c.isspace()).replace(" ", "_")[:30]
        production_id = f"{topic_slug}_{timestamp}"

        project_root = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(project_root, "assets", "productions", production_id)
        cache_dir = os.path.join(project_root, "assets", "cache")

        # Cleanup cache
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(base_dir, exist_ok=True)

        mode_title = "HORROR STORY MODE" if mode == "horror" else "INFO MODE"
        type_title = "LONG FORM" if video_type == "long" else "SHORTS"
        logger.info(f"FACTORY STARTING ({mode_title} - {type_title}): {topic}")
        logger.info("V8.7 - VIRAL ANALYZER EDITION")

        # Initialize services
        self.tts = TTSService(output_dir=cache_dir)
        self.pexels = PexelsService(output_dir=cache_dir)
        self.pixabay = PixabayService(output_dir=cache_dir)
        self.engine = VideoEngine()

        # 1. Research
        if self.researcher:
            logger.info("Gathering inspiration and research...")
            research_data = self.researcher.research(topic)
        else:
            logger.warning("ResearchAgent unavailable, continuing with topic-only context.")
            research_data = f"Topic context: {topic}"

        for lang in languages:
            lang = lang.strip().lower()
            logger.info(f"PROCESSING LANGUAGE: {lang.upper()}")

            # Update Voice for current language
            self.tts.set_voice(language=lang)

            # 2. Script & Blueprint
            narrative = self.scriptwriter.generate_narrative(research_data, topic, language=lang, mode=mode, video_type=video_type, style_context=style_context)
            if not narrative:
                logger.error(f"Failed to generate narrative for {lang}. Skipping.")
                continue

            blueprint = self.scriptwriter.generate_blueprint(narrative, topic, language=lang, mode=mode, video_type=video_type)
            if not blueprint:
                logger.error(f"Failed to generate blueprint for {lang}. Skipping.")
                continue

            blueprint.video_id = production_id

            # 3. Media Collection
            valid_scenes = []
            import random
            orientation = "landscape" if video_type == "long" else "portrait"
            for i, scene in enumerate(blueprint.scenes):
                logger.info(f"Scene {i + 1}: Processing...")

                # Randomize keyword order for variety
                random.shuffle(scene.keywords)

                # Stock Video Collection
                video_path = None
                if i % 2 == 0:
                    logger.info(f"Scene {i + 1}: Source -> Pexels")
                    video_path = self.pexels.get_video(scene.keywords, orientation=orientation)
                    if not video_path:
                        logger.info(f"Scene {i + 1}: Pexels empty, failing over to Pixabay...")
                        video_path = self.pixabay.get_video(scene.keywords, orientation=orientation)
                else:
                    logger.info(f"Scene {i + 1}: Source -> Pixabay")
                    video_path = self.pixabay.get_video(scene.keywords, orientation=orientation)
                    if not video_path:
                        logger.info(f"Scene {i + 1}: Pixabay empty, failing over to Pexels...")
                        video_path = self.pexels.get_video(scene.keywords, orientation=orientation)

                # Global Topic Fallback
                if not video_path:
                    logger.warning(f"Scene {i + 1}: Keywords failed. Recovering with global topic: '{topic}'...")
                    video_path = self.pexels.get_video([topic], orientation=orientation)

                scene.video_path = video_path

                # Narration & Subtitles
                audio, subs, dur = self.tts.generate_audio_with_subtitles(scene.text, lang)
                if not audio:
                    logger.error(f"Scene {i + 1}: Narration failed for {lang}! Skipping scene.")
                    continue

                scene.audio_path = audio
                scene.subs_path = subs
                scene.duration = dur
                valid_scenes.append(scene)

            if not valid_scenes:
                logger.error(f"No valid scenes generated for {lang}. Skipping.")
                continue

            blueprint.scenes = valid_scenes

            # 4. Render (Intelligent Background Music Selection)
            music_dir = os.path.join(project_root, "assets", "templates", "music")
            bg_music = None

            if os.path.exists(music_dir):
                all_tracks = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
                if all_tracks:
                    # Granular Theme Mapping
                    theme_keywords = []

                    if mode == "horror":
                        theme_keywords = ["horror", "tension", "mystery"]
                    elif mode == "info":
                        # Further specialize based on topic keywords
                        topic_lower = topic.lower()
                        if any(k in topic_lower for k in ["tech", "future", "cyber", "ai", "robot"]):
                            theme_keywords = ["cyberpunk", "retro", "modern"]
                        elif any(k in topic_lower for k in ["history", "war", "battle", "epic", "ancient"]):
                            theme_keywords = ["epic", "cinematic"]
                        elif any(k in topic_lower for k in ["nature", "wild", "animal", "space", "earth", "planet"]):
                            theme_keywords = ["nature", "natgeo", "documentary"]
                        elif any(k in topic_lower for k in ["sad", "emotional", "touching", "story", "life"]):
                            theme_keywords = ["emotional", "inspiring"]
                        elif any(k in topic_lower for k in ["business", "professional", "company", "money", "corporate"]):
                            theme_keywords = ["corporate", "modern", "upbeat"]
                        elif any(k in topic_lower for k in ["chill", "relax", "study", "casual"]):
                            theme_keywords = ["lofi", "jazz"]
                        elif any(k in topic_lower for k in ["80s", "90s", "old", "vintage", "classic"]):
                            theme_keywords = ["retro", "jazz"]
                        else:
                            # Balanced Doc Default
                            theme_keywords = ["documentary", "cinematic", "inspiring"]

                    # Filter tracks matching themes
                    preferred = [t for t in all_tracks if any(k in t for k in theme_keywords)]

                    # Fallback Logic
                    selected_file = random.choice(preferred if preferred else all_tracks)
                    bg_music = os.path.join(music_dir, selected_file)
                    logger.info(f"Intelligent Theme Mapping -> {selected_file} (Mode: {mode}, Themes: {theme_keywords})")
                else:
                    # Fallback to legacy single file
                    default_bg = os.path.join(project_root, "assets", "templates", "bg_music.mp3")
                    if os.path.exists(default_bg):
                        bg_music = default_bg
                        logger.info("No themed tracks found, using default bg_music.mp3.")

            if not bg_music:
                logger.warning("No background music tracks found. Rendering without music.")

            final_path = self.engine.render(blueprint, language=lang, bg_music_path=bg_music, video_type=video_type)

            if final_path and os.path.exists(final_path):
                # Save output
                lang_dir = os.path.join(base_dir, lang)
                os.makedirs(lang_dir, exist_ok=True)
                dest_path = os.path.join(lang_dir, f"{production_id}_{lang}.mp4")
                shutil.move(final_path, dest_path)

                # Metadata Cleanup (Strict 'Shorts' Removal for Long Form)
                title = blueprint.metadata.get('title', topic)
                desc = blueprint.metadata.get('description', '')
                tags = blueprint.metadata.get('tags', [])

                if is_long:
                    import re
                    title = re.sub(r'(?i)shorts?', '', title).strip()
                    desc = re.sub(r'(?i)shorts?', '', desc).strip()
                    tags = [re.sub(r'(?i)shorts?', '', str(t)).strip() for t in tags if t]
                    tags = [t for t in tags if t]  # Remove empty

                # Save Metadata
                meta_file = os.path.join(lang_dir, "metadata.json")

                with open(meta_file, "w", encoding="utf-8") as f:
                    meta_data = {
                        "title": title,
                        "description": desc,
                        "tags": tags,
                        "file_path": dest_path
                    }
                    json.dump(meta_data, f, indent=2, ensure_ascii=False)

                logger.info(f"VIDEO READY: {dest_path}")

                # 5. Auto-Upload
                if auto_upload:
                    if not self.youtube_service:
                        self.youtube_service = YouTubeService()

                    upload_id = self.youtube_service.upload_video(
                        dest_path,
                        title,
                        desc,
                        tags,
                        video_type=video_type,
                    )
                    if not upload_id:
                        logger.error(f"Upload failed for {lang} ({dest_path})")
                        return None
            else:
                logger.error(f"Render failed: {lang}")

        logger.info(f"OPERATION COMPLETE. Production ID: {production_id}")
        return production_id

    def run_ambient(self, ambient_type="sleep", duration_minutes=60, video_type="long", auto_upload=False, language="en"):
        project_root = os.path.dirname(os.path.abspath(__file__))
        ambient = AmbientVideoService(project_root=project_root)
        result = ambient.create_video(
            ambient_type=ambient_type,
            duration_minutes=duration_minutes,
            video_type=video_type,
            language=language,
            source_mode=getattr(self, "ambient_source_mode", "auto"),
        )
        if not result:
            logger.error("Ambient video generation failed.")
            return None

        logger.info(f"AMBIENT VIDEO READY: {result['file_path']}")

        if auto_upload:
            if not self.youtube_service:
                self.youtube_service = YouTubeService()

            upload_id = self.youtube_service.upload_video(
                result["file_path"],
                result["title"],
                result["description"],
                result.get("tags", []),
                video_type=video_type,
            )
            if not upload_id:
                logger.error("Ambient video upload failed.")
                return None

        return result


def print_viral_help():
    """Print help for viral analysis command."""
    print("\n" + "=" * 60)
    print("🔥 VIRAL ANALYZER - YouTube Shorts Trend Analizi")
    print("=" * 60)
    print("\nKullanım:")
    print("  python main.py --viral [kategori] [--region BÖLGE] [--langs DİL]")
    print("  python main.py --viral-remix [kategori] --region US --save-remix")
    print("\nKategoriler:")
    for cat in VIRAL_CATEGORIES:
        print(f"  • {cat}")
    print("\nAmbient Türleri:")
    print("  • fireplace     - Huzurlu Şömine")
    print("  • sleep         - Derin Uyku Manzaraları")
    print("  • rain          - Gece Yağmuru")
    print("  • ocean_sleep   - Okyanus Dalgaları")
    print("  • cozy_library  - Kitaplık & Yağmur (Popüler!)")
    print("  • space_ambience- Uzay Yolculuğu (Sci-Fi)")
    print("  • cyberpunk_city- Neon Şehir & Yağmur")
    print("  • forest_walk   - Orman Yürüyüşü & Nehir")
    print("  • white_noise   - Beyaz Gürültü")
    print("  • brown_noise   - Kahverengi Gürültü")
    print("\nÖrnekler:")
    print("  python main.py --viral facts              # Fact videoları analiz et")
    print("  python main.py --viral science --langs tr # Türkçe bilim fikirleri")
    print("  python main.py --viral history --region TR # Türkiye'de popüler tarih")
    print("  python main.py --viral --produce 1        # 1. fikri direkt üret")
    print("  python main.py --viral-remix facts --region US --produce-remix 2")
    print("  python main.py --ambient sleep --ambient-duration 60 --type long")
    print("\nBölgeler: US, TR, GB, DE, FR, JP, BR, IN, etc.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YouTube Factory - AI Video Production System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --topic "Amazing facts about Japan"
  python main.py --topic trend --bulk --langs tr
  python main.py --viral facts --langs tr
  python main.py --viral science --produce 1 --langs en,tr
  python main.py --viral-remix facts --region US --save-remix
  python main.py --ambient fireplace --ambient-duration 60 --type long
        """
    )

    # Basic options
    parser.add_argument("--topic", type=str, help="Video topic (use 'trend' for auto-discovery)")
    parser.add_argument("--langs", type=str, default="en", help="Languages (comma-separated): en,tr")
    parser.add_argument("--upload", action="store_true", help="Auto-upload to YouTube")
    parser.add_argument("--mode", type=str, default="info", choices=["info", "horror"], help="Content mode")
    parser.add_argument("--type", type=str, default="shorts", choices=["shorts", "long"], help="Video format")
    parser.add_argument("--ambient", type=str, choices=AMBIENT_TYPES, help="Generate long ambient videos")
    parser.add_argument("--ambient-duration", type=int, default=60, help="Ambient video duration in minutes")
    parser.add_argument("--ambient-source", type=str, default="auto", choices=["auto", "api"],
                        help="Ambient video source mode: auto (fallback allowed) or api (strict API footage)")

    # Trend options
    parser.add_argument("--list-trends", action="store_true", help="List trending topics")
    parser.add_argument("--bulk", action="store_true", help="Produce all trends")

    # Viral analyzer options
    parser.add_argument("--viral", type=str, nargs="?", const="facts", metavar="CATEGORY",
                        help=f"Analyze viral videos. Categories: {', '.join(VIRAL_CATEGORIES)}")
    parser.add_argument("--viral-remix", type=str, nargs="?", const="facts", metavar="CATEGORY",
                        help="Find viral EN shorts and create editable remix topics")
    parser.add_argument("--region", type=str, default="US", help="Region for viral analysis (US, TR, GB, etc.)")
    parser.add_argument("--produce", type=int, metavar="N", help="Produce video from viral idea #N")
    parser.add_argument("--produce-remix", type=int, metavar="N", help="Produce video from remix candidate #N")
    parser.add_argument("--remix-topic", type=str, help="Manual topic override for --produce-remix")
    parser.add_argument("--save-remix", action="store_true", help="Save remix candidates as JSON")
    parser.add_argument("--viral-help", action="store_true", help="Show viral analyzer help")

    args = parser.parse_args()

    # Viral Help
    if args.viral_help:
        print_viral_help()
        sys.exit(0)

    factory = YoutubeFactory()

    # Ambient Mode
    if args.ambient:
        ambient_video_type = args.type
        if "--type" not in sys.argv:
            ambient_video_type = "long"

        factory.ambient_source_mode = args.ambient_source

        logger.info(f"🎧 AMBIENT MODE: {args.ambient} ({args.ambient_duration} min)")
        ambient_result = factory.run_ambient(
            ambient_type=args.ambient,
            duration_minutes=args.ambient_duration,
            video_type=ambient_video_type,
            auto_upload=args.upload,
            language=args.langs.split(",")[0].strip().lower(),
        )
        if not ambient_result:
            sys.exit(1)
        sys.exit(0)

    # Viral Remix Mode
    if args.viral_remix:
        # Strict health check for viral mode
        if not os.getenv("YOUTUBE_API_KEY"):
            logger.error("❌ YOUTUBE_API_KEY is missing from environment secrets. Viral Remix requires this.")
            sys.exit(1)
        if not os.getenv("GEMINI_API_KEY"):
            logger.error("❌ GEMINI_API_KEY is missing. Required for trend analysis.")
            sys.exit(1)

        if not factory.viral_analyzer:
            logger.error("ViralAnalyzer is unavailable. Check API keys.")
            sys.exit(1)

        # Auto-selection if upload is True but no index provided
        should_auto_produce = args.upload and not args.produce_remix

        category = args.viral_remix if args.viral_remix in VIRAL_CATEGORIES else "facts"
        logger.info(f"🧪 VIRAL REMIX: Scanning '{category}' in {args.region}...")

        try:
            remix_candidates = factory.viral_analyzer.get_remix_candidates(
                category=category,
                region=args.region,
                max_results=12
            )
            factory.viral_analyzer.print_remix_candidates(remix_candidates)
        except Exception as e:
            logger.error(f"Failed to fetch remix candidates: {e}")
            remix_candidates = []

        if args.save_remix and remix_candidates:
            project_root = os.path.dirname(os.path.abspath(__file__))
            out_dir = os.path.join(project_root, "assets", "productions")
            os.makedirs(out_dir, exist_ok=True)
            out_file = os.path.join(out_dir, f"viral_remix_{category}_{int(time.time())}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(remix_candidates, f, indent=2, ensure_ascii=False)
            logger.info(f"Remix list saved: {out_file}")

        if (args.produce_remix or should_auto_produce) and remix_candidates:
            remix_index = (args.produce_remix - 1) if args.produce_remix else 0
            if 0 <= remix_index < len(remix_candidates):
                selected = remix_candidates[remix_index]
                topic = args.remix_topic.strip() if args.remix_topic else selected["editable_topic"]
                logger.info(f"Producing remix {'#' + str(args.produce_remix) if args.produce_remix else 'AUTO'}: {topic}")
                production_id = factory.run(
                    topic=topic,
                    languages=args.langs.split(","),
                    auto_upload=args.upload,
                    mode=args.mode,
                    video_type=args.type,
                    style_context=selected.get("style_context", "")
                )
                if not production_id:
                    logger.error("Remix production/upload failed.")
                    sys.exit(1)
            else:
                logger.error(f"Invalid remix number. Choose between 1 and {len(remix_candidates)}")
                sys.exit(1)
        elif args.produce_remix or should_auto_produce:
            logger.error("No remix candidates generated to produce from.")
            sys.exit(1)

        sys.exit(0)

    # Viral Analysis Mode
    if args.viral:
        # Strict health check for viral mode
        if not os.getenv("YOUTUBE_API_KEY"):
            logger.error("❌ YOUTUBE_API_KEY is missing from environment secrets. Viral Analysis requires this.")
            sys.exit(1)

        if not factory.viral_analyzer:
            logger.error("ViralAnalyzer is unavailable. Check API keys.")
            sys.exit(1)

        category = args.viral if args.viral in VIRAL_CATEGORIES else "facts"
        lang = args.langs.split(",")[0].strip().lower()  # Use first language

        logger.info(f"🔥 VIRAL ANALYZER: Analyzing '{category}' category in {args.region}...")

        ideas = factory.viral_analyzer.analyze_trending(
            category=category,
            region=args.region,
            max_results=10,
            language=lang
        )

        # Print ideas
        factory.viral_analyzer.print_ideas(ideas)

        # Auto-produce if requested or if upload is True without N
        should_auto_viral = args.upload and not args.produce
        if (args.produce or should_auto_viral) and ideas:
            idea_index = (args.produce - 1) if args.produce else 0
            if 0 <= idea_index < len(ideas):
                selected_idea = ideas[idea_index]
                topic = factory.viral_analyzer.get_idea_as_topic(selected_idea)

                print(f"\n🎬 Producing video from idea #{args.produce}: {topic}\n")

                factory.run(
                    topic=topic,
                    languages=args.langs.split(","),
                    auto_upload=args.upload,
                    mode=args.mode,
                    video_type=args.type,
                    style_context=selected_idea.style_context
                )
            else:
                logger.error(f"Invalid idea number. Choose between 1 and {len(ideas)}")
        elif args.produce:
            logger.error("No ideas generated to produce from.")

        sys.exit(0)

    # List Trends Mode
    if args.list_trends:
        if not factory.trend_agent:
            logger.error("TrendAgent is unavailable. Check GEMINI_API_KEY.")
            sys.exit(1)
        logger.info("Fetching latest viral trends...")
        trends = factory.trend_agent.get_trending_topics()
        for i, t in enumerate(trends):
            print(f"{i + 1}. {t['topic']}")
            print(f"   {t['reason']}\n")
        sys.exit(0)

    langs = args.langs.split(",")

    # Handle Trend Selection
    if args.topic and args.topic.lower() == "trend":
        if not factory.trend_agent:
            logger.error("TrendAgent is unavailable. Check GEMINI_API_KEY.")
            sys.exit(1)

        logger.info("Auto-Trend Mode: Selecting viral topics...")
        trends = factory.trend_agent.get_trending_topics(count=5)

        if not trends:
            logger.error("No trends found. Please provide a manual topic.")
            sys.exit(1)

        if args.bulk:
            logger.info(f"BULK MODE: Producing {len(trends)} trending videos automatically!")
            for i, t in enumerate(trends):
                logger.info(f"[Bulk {i + 1}/{len(trends)}] Starting: {t['topic']}")
                try:
                    factory.run(topic=t['topic'], languages=langs, auto_upload=args.upload, mode=args.mode, video_type=args.type)

                    # Cooldown between bulk productions to respect API rate limits
                    if i < len(trends) - 1:
                        logger.info(f"Bulk cooldown: waiting {BULK_MODE_COOLDOWN}s before next video...")
                        time.sleep(BULK_MODE_COOLDOWN)

                except Exception as e:
                    logger.error(f"Failed to produce trend video '{t['topic']}': {e}")
            logger.info("BULK PRODUCTION COMPLETE!")
        else:
            args.topic = trends[0]['topic']
            logger.info(f"Selected Top Trend: {args.topic}")
            factory.run(topic=args.topic, languages=langs, auto_upload=args.upload, mode=args.mode, video_type=args.type)
    elif args.topic:
        # Manual Topic
        factory.run(topic=args.topic, languages=langs, auto_upload=args.upload, mode=args.mode, video_type=args.type)
    else:
        # No topic provided - show help
        parser.print_help()
        print("\n" + "=" * 60)
        print("💡 Quick Start:")
        print("   python main.py --viral facts --langs tr  # Viral analiz")
        print("   python main.py --viral-remix facts --region US --save-remix")
        print("   python main.py --ambient sleep --ambient-duration 60 --type long")
        print("   python main.py --topic 'Konu' --langs tr # Video üret")
        print("=" * 60)
