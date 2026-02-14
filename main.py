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
from src.agents.x_content_agent import XContentAgent
from src.agents.youtube_content_agent import YouTubeContentAgent
from src.agents.country_content_agent import LongFormContentAgent
from src.agents.nature_shorts_agent import NatureShortsAgent, NATURE_SHORTS_CATEGORIES
from src.services.tiktok_service import TikTokService
from src.agents.tiktok_agent import TikTokAgent
from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
from src.agents.nightly_brain_agent import NightlyBrainAgent
from src.services.livestream_service import LivestreamService, LIVESTREAM_PRESETS


load_dotenv()

# Constants
BULK_MODE_COOLDOWN = 30  # seconds between bulk video productions

# Available viral categories for --viral command
VIRAL_CATEGORIES = ["facts", "science", "history", "psychology", "nature", "tech", "mystery", "lifestyle"]
AMBIENT_TYPES = list(AmbientVideoService.AMBIENT_PRESETS.keys())
LIVESTREAM_TYPES = list(LIVESTREAM_PRESETS.keys())
NATURE_SHORTS_TYPES = list(NATURE_SHORTS_CATEGORIES.keys())


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
        self.x_agent = self._safe_init(XContentAgent, "XContentAgent", factory_instance=self)
        self.youtube_agent = self._safe_init(YouTubeContentAgent, "YouTubeContentAgent", factory_instance=self)
        self.longform_agent = self._safe_init(LongFormContentAgent, "LongFormContentAgent", factory_instance=self)
        self.nature_shorts_agent = self._safe_init(NatureShortsAgent, "NatureShortsAgent", factory_instance=self)
        self.tiktok_service = self._safe_init(TikTokService, "TikTokService")
        self.tiktok_agent = self._safe_init(TikTokAgent, "TikTokAgent", tiktok_service=self.tiktok_service)
        self.analytics_agent = None  # Lazy init (needs YouTube service)
        self.youtube_service = None


    def _safe_init(self, cls, name, **kwargs):
        try:
            return cls(**kwargs)
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

        mode_titles = {"horror": "HORROR STORY MODE", "quiz": "QUIZ MODE", "reddit": "REDDIT STORIES MODE"}
        mode_title = mode_titles.get(mode, "INFO MODE")
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

            # Update Voice for current language + content-aware selection
            self.tts.set_voice_for_content(topic=topic, mode=mode, language=lang)

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

                # Stock Video Collection — 3-tier fallback: Pixabay ↔ Pexels → Freepik
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

                # Freepik fallback (last resort before giving up on keywords)
                if not video_path:
                    logger.info(f"Scene {i + 1}: Pexels+Pixabay failed, trying Freepik...")
                    try:
                        from src.services.freepik_service import FreepikService
                        if not hasattr(self, '_freepik'):
                            self._freepik = FreepikService()
                        video_path = self._freepik.get_video(scene.keywords, orientation=orientation)
                    except Exception as fe:
                        logger.warning(f"Scene {i + 1}: Freepik fallback failed: {fe}")

                # Global Topic Fallback (all 3 services)
                if not video_path:
                    logger.warning(f"Scene {i + 1}: All keywords failed. Recovering with global topic: '{topic}'...")
                    video_path = self.pexels.get_video([topic], orientation=orientation)
                    if not video_path:
                        video_path = self.pixabay.get_video([topic], orientation=orientation)

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
                    elif mode == "quiz":
                        theme_keywords = ["upbeat", "game", "fun", "quiz", "energetic"]
                    elif mode == "reddit":
                        theme_keywords = ["emotional", "lofi", "chill", "story"]
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

                # Ensure minimum 5 tags
                if len(tags) < 5:
                    topic_words = [w.strip() for w in topic.split() if len(w.strip()) > 2]
                    fallback_tags = topic_words + [topic, lang]
                    for ft in fallback_tags:
                        if ft and ft not in tags:
                            tags.append(ft)
                        if len(tags) >= 5:
                            break

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

                # 5. Auto-Upload (with thumbnail)
                if auto_upload:
                    if not self.youtube_service:
                        self.youtube_service = YouTubeService()

                    # Generate thumbnail BEFORE upload
                    thumb_path = None
                    try:
                        branding = BrandingService()
                        thumb_path = branding.generate_thumbnail(
                            topic=topic,
                            title=title,
                            video_type=video_type,
                            output_path=os.path.join(lang_dir, "thumbnail.jpg"),
                        )
                        logger.info(f"🎨 Thumbnail generated: {thumb_path}")
                    except Exception as te:
                        logger.warning(f"Thumbnail generation failed: {te}")

                    upload_id = self.youtube_service.upload_video(
                        dest_path,
                        title,
                        desc,
                        tags,
                        video_type=video_type,
                    )

                    # Set custom thumbnail after upload
                    if upload_id and thumb_path and os.path.exists(thumb_path):
                        try:
                            self.youtube_service.set_thumbnail(upload_id, thumb_path)
                            logger.info(f"🎨 Custom thumbnail set for {upload_id}")
                        except Exception as te:
                            logger.warning(f"Thumbnail set failed: {te}")

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
    print("\nDoğa Shorts Kategorileri:")
    for cat in NATURE_SHORTS_TYPES:
        print(f"  • {cat}")
    print("\nÖrnekler:")
    print("  python main.py --viral facts              # Fact videoları analiz et")
    print("  python main.py --viral science --langs tr # Türkçe bilim fikirleri")
    print("  python main.py --viral history --region TR # Türkiye'de popüler tarih")
    print("  python main.py --viral --produce 1        # 1. fikri direkt üret")
    print("  python main.py --viral-remix facts --region US --produce-remix 2")
    print("  python main.py --ambient sleep --ambient-duration 60 --type long")
    print("  python main.py --nature-shorts rain       # Yağmur Shorts üret")
    print("  python main.py --nature-shorts-auto --upload  # 3 doğa shorts üret & yükle")
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
    parser.add_argument("--mode", type=str, default="info", choices=["info", "horror", "quiz", "reddit"], help="Content mode")
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
    parser.add_argument("--x-auto", action="store_true", help="Run daily X (Twitter) automation")
    parser.add_argument("--x-force", action="store_true", help="Force X automation even if it's not the scheduled time")
    parser.add_argument("--x-plan", action="store_true", help="Force generate a new daily plan for X")
    parser.add_argument("--x-topic", type=str, help="Custom topic for X post generation")
    parser.add_argument("--youtube-auto", action="store_true", help="Run daily trending YouTube Shorts automation")
    parser.add_argument("--longform-auto", action="store_true", help="Run daily trending long-form documentary automation")

    # Nature Shorts options
    parser.add_argument("--nature-shorts", type=str, nargs="?", const="random",
                        choices=["random"] + NATURE_SHORTS_TYPES,
                        help=f"Create nature/ambient YouTube Shorts. Categories: {', '.join(NATURE_SHORTS_TYPES)}")
    parser.add_argument("--nature-shorts-count", type=int, default=3,
                        help="Number of nature shorts to create in daily mode (default: 3)")
    parser.add_argument("--nature-shorts-auto", action="store_true",
                        help="Run daily nature shorts automation (creates multiple shorts)")

    # TikTok options
    parser.add_argument("--tiktok-auth", action="store_true",
                        help="Start TikTok OAuth2 authentication flow")
    parser.add_argument("--tiktok-post", type=str, metavar="VIDEO_PATH",
                        help="Post a specific video to TikTok")
    parser.add_argument("--tiktok-auto", action="store_true",
                        help="Run daily TikTok automation (cross-post shorts)")
    parser.add_argument("--tiktok-count", type=int, default=3,
                        help="Number of TikTok posts in daily automation (default: 3)")

    # YouTube Analytics options
    parser.add_argument("--analytics", action="store_true",
                        help="Run full YouTube channel analytics & strategy analysis")
    parser.add_argument("--analytics-delete", action="store_true",
                        help="Show which underperforming videos would be deleted (dry run)")
    parser.add_argument("--analytics-delete-confirm", action="store_true",
                        help="Actually delete underperforming videos (DESTRUCTIVE!)")

    # Nightly Brain options
    parser.add_argument("--nightly", action="store_true",
                        help="Run nightly brain: cleanup + trends + plan (LIVE mode)")
    parser.add_argument("--nightly-dry", action="store_true",
                        help="Run nightly brain in dry-run mode (no deletions)")
    parser.add_argument("--execute-plan", action="store_true",
                        help="Execute today's content plan (produce & upload)")
    parser.add_argument("--plan-shorts", type=int, default=2,
                        help="Number of shorts to produce from plan (default: 2)")
    parser.add_argument("--plan-longform", type=int, default=0,
                        help="Number of longform to produce from plan (default: 0)")

    # Fast Loop options (turn short clip into hours-long video)
    parser.add_argument("--loop-video", type=str,
                        help="Input video file to loop (e.g. 8 second 4K clip)")
    parser.add_argument("--loop-hours", type=float, default=8.0,
                        help="Target duration in hours (default: 8)")
    parser.add_argument("--loop-audio", type=str, default=None,
                        help="Optional audio file to overlay on looped video")
    parser.add_argument("--loop-title", type=str, default=None,
                        help="Video title for upload")
    parser.add_argument("--loop-tags", type=str, default=None,
                        help="Comma-separated tags for the video")

    # Livestream options
    parser.add_argument("--livestream", type=str, choices=LIVESTREAM_TYPES, help="Start a 24/7 YouTube Live Stream")
    parser.add_argument("--livestream-list", action="store_true", help="List available livestream presets")
    parser.add_argument("--livestream-info", type=str, choices=LIVESTREAM_TYPES, help="Show stream metadata for copy-paste")
    parser.add_argument("--livestream-prepare", type=str, choices=LIVESTREAM_TYPES, help="Only prepare loop video, don't stream")
    parser.add_argument("--loop-duration", type=int, default=30, help="Duration of the loop video in minutes (default: 30)")


    args = parser.parse_args()

    # Viral Help
    if args.viral_help:
        print_viral_help()
        sys.exit(0)

    factory = YoutubeFactory()

    # Livestream List
    if args.livestream_list:
        LivestreamService.print_presets()
        sys.exit(0)

    # Livestream Info (show metadata for copy-paste into YouTube Studio)
    if args.livestream_info:
        service = LivestreamService(project_root=os.path.dirname(os.path.abspath(__file__)))
        info = service.get_stream_info(args.livestream_info)
        if info:
            print("\n" + "=" * 60)
            print(f"📡 STREAM INFO: {args.livestream_info}")
            print("=" * 60)
            print(f"\n📌 TITLE:\n{info['title']}")
            print(f"\n📝 DESCRIPTION:\n{info['description']}")
            print(f"\n🏷️  TAGS:\n{', '.join(info['tags'])}")
            print("\n" + "=" * 60)
        sys.exit(0)

    # Livestream Prepare Only
    if args.livestream_prepare:
        service = LivestreamService(project_root=os.path.dirname(os.path.abspath(__file__)))
        loop_path = service.prepare_loop_video(args.livestream_prepare, duration_minutes=args.loop_duration)
        if loop_path:
            logger.info(f"Loop video ready: {loop_path}")
        else:
            logger.error("Failed to prepare loop video.")
            sys.exit(1)
        sys.exit(0)

    # Livestream Start
    if args.livestream:
        service = LivestreamService(project_root=os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"🔴 LIVESTREAM MODE: {args.livestream}")

        # Show stream info
        info = service.get_stream_info(args.livestream)
        if info:
            print("\n" + "=" * 60)
            print("📋 Copy this info to YouTube Studio → Go Live:")
            print(f"   Title: {info['title']}")
            print("=" * 60 + "\n")

        service.stream_with_auto_restart(args.livestream)
        sys.exit(0)

    # YouTube Analytics Mode
    if args.analytics or args.analytics_delete or args.analytics_delete_confirm:
        logger.info("📊 YouTube Analytics & Strategy Tool")

        # Initialize YouTube service for analytics
        try:
            yt_service = YouTubeService()
            if not yt_service.youtube:
                logger.error("YouTube service not available. Check credentials (token.pickle + client_secrets.json).")
                sys.exit(1)
            analytics = YouTubeAnalyticsAgent(youtube_service=yt_service)
        except Exception as e:
            logger.error(f"Failed to initialize YouTube Analytics: {e}")
            sys.exit(1)

        auto_delete = args.analytics_delete_confirm
        result = analytics.run_full_analysis(auto_delete=auto_delete)

        if result.get("error"):
            logger.error(f"Analytics failed: {result['error']}")
            sys.exit(1)

        # Dry-run delete preview
        if args.analytics_delete and not args.analytics_delete_confirm:
            analysis = result.get("analysis", {})
            underperformers = analysis.get("underperformers", [])
            if underperformers:
                print("\n🗑️ UNDERPERFORMERS (Dry Run - would be deleted):")
                print("-" * 60)
                for v in underperformers:
                    if v.get("recommendation") == "DELETE":
                        print(f"  ❌ {v['title'][:50]}")
                        print(f"     Views: {v['views']} | Severity: {v['severity_score']}")
                        print(f"     Reasons: {', '.join(v.get('reasons', []))}")
                        print()
                print(f"Total: {len([v for v in underperformers if v.get('recommendation') == 'DELETE'])} videos")
                print("\n⚠️ To actually delete, run: python main.py --analytics-delete-confirm")
            else:
                print("\n✅ No videos qualify for deletion!")

        sys.exit(0)

    # Fast Loop Mode — Turn short clip into hours-long video
    if args.loop_video:
        logger.info(f"🔄 Fast Loop Mode: {args.loop_video} → {args.loop_hours}h")

        from src.services.ambient_video_service import AmbientVideoService
        project_root = os.path.dirname(os.path.abspath(__file__))
        ambient = AmbientVideoService(project_root=project_root)

        tags = args.loop_tags.split(",") if args.loop_tags else None

        result = ambient.loop_video(
            input_video=args.loop_video,
            duration_hours=args.loop_hours,
            audio_file=args.loop_audio,
            title=args.loop_title,
            tags=tags,
        )

        if not result:
            logger.error("Loop render failed!")
            sys.exit(1)

        logger.info(f"\n✅ Loop video created!")
        logger.info(f"   📹 {result['resolution']} ({result['method']})")
        logger.info(f"   ⏱️ Render time: {result['render_time_seconds']}s")
        logger.info(f"   📦 Size: {result['file_size_gb']} GB")
        logger.info(f"   📂 File: {result['file_path']}")

        # Upload if --upload flag is set
        if args.upload:
            logger.info("📤 Uploading to YouTube...")
            try:
                if not factory.youtube_service:
                    factory.youtube_service = YouTubeService()
                video_id = factory.youtube_service.upload_video(
                    file_path=result["file_path"],
                    title=result["title"],
                    description=result["description"],
                    tags=result["tags"],
                    video_type="long",
                )
                if video_id:
                    logger.info(f"✅ Uploaded: https://youtube.com/watch?v={video_id}")
            except Exception as e:
                logger.error(f"Upload failed: {e}")

        sys.exit(0)

    # Nightly Brain Mode
    if args.nightly or args.nightly_dry:
        logger.info("🧠 Nightly Brain Agent Starting...")

        try:
            yt_service = YouTubeService()
            if not yt_service.youtube:
                logger.error("YouTube service not available. Check credentials.")
                sys.exit(1)
            brain = NightlyBrainAgent(youtube_service=yt_service)
        except Exception as e:
            logger.error(f"Failed to initialize Nightly Brain: {e}")
            sys.exit(1)

        dry_run = args.nightly_dry
        result = brain.run_nightly(dry_run=dry_run)

        if result.get("error"):
            logger.error(f"Nightly brain failed: {result['error']}")
            sys.exit(1)

        sys.exit(0)

    # Execute Daily Plan Mode
    if args.execute_plan:
        logger.info("🎬 Executing Daily Content Plan...")

        # Check if plan exists
        plan_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "daily_plan.json")
        if not os.path.exists(plan_path):
            logger.error("No daily plan found. Run --nightly first.")
            sys.exit(1)

        try:
            yt_service = YouTubeService()
            brain = NightlyBrainAgent(youtube_service=yt_service)
            result = brain.execute_plan(
                factory_instance=factory,
                max_shorts=args.plan_shorts,
                max_longform=args.plan_longform
            )
            if result.get("error"):
                logger.error(f"Plan execution failed: {result['error']}")
                sys.exit(1)
            logger.info(f"✅ Plan executed: {result}")
        except Exception as e:
            logger.error(f"Plan execution error: {e}")
            sys.exit(1)

        sys.exit(0)

    # X Automation Mode
    if args.x_auto:
        if not factory.x_agent:
            logger.error("XContentAgent is unavailable. Check X API keys.")
            sys.exit(1)
        
        # If x_plan is requested OR a topic is provided (ensure it's not just an empty string from GitHub)
        if args.x_plan or (args.x_topic and args.x_topic.strip()):
            factory.x_agent.generate_daily_plan(custom_topic=args.x_topic)
            
        logger.info(f"Running X Daily Automation (Force: {args.x_force})...")
        factory.x_agent.run_scheduled_tasks(force=args.x_force)
        sys.exit(0)

    # YouTube Automation Mode
    if args.youtube_auto:
        if not factory.youtube_agent:
            logger.error("YouTubeContentAgent is unavailable.")
            sys.exit(1)
            
        logger.info(f"Running YouTube Daily Automation (Region: {args.region})...")
        factory.youtube_agent.run_daily_automation(region=args.region)
        sys.exit(0)

    # Long-Form Trending Automation Mode
    if args.longform_auto:
        if not factory.longform_agent:
            logger.error("LongFormContentAgent is unavailable.")
            sys.exit(1)
            
        logger.info(f"Running Long-Form Trending Automation (Region: {args.region})...")
        factory.longform_agent.run_automation(region=args.region)
        sys.exit(0)


    # Nature Shorts Mode
    if args.nature_shorts:
        if not factory.nature_shorts_agent:
            logger.error("NatureShortsAgent is unavailable.")
            sys.exit(1)

        category = args.nature_shorts if args.nature_shorts != "random" else None
        logger.info(f"🌿 NATURE SHORTS MODE: {args.nature_shorts}")
        result = factory.nature_shorts_agent.create_short(
            category=category,
            auto_upload=args.upload,
        )
        if not result:
            logger.error("Nature short creation failed.")
            sys.exit(1)
        sys.exit(0)

    # Nature Shorts Daily Automation
    if args.nature_shorts_auto:
        if not factory.nature_shorts_agent:
            logger.error("NatureShortsAgent is unavailable.")
            sys.exit(1)

        logger.info(f"🌿 NATURE SHORTS DAILY: Creating {args.nature_shorts_count} shorts...")
        results = factory.nature_shorts_agent.run_daily_automation(
            count=args.nature_shorts_count,
            auto_upload=args.upload,
        )
        if not results:
            logger.error("Nature shorts daily automation produced no results.")
            sys.exit(1)
        logger.info(f"✅ Created {len(results)} nature shorts!")
        sys.exit(0)

    # TikTok Authentication
    if args.tiktok_auth:
        if not factory.tiktok_service:
            logger.error("TikTokService is unavailable. Check TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET.")
            sys.exit(1)
        factory.tiktok_service.start_auth_flow()
        sys.exit(0)

    # TikTok Single Post
    if args.tiktok_post:
        if not factory.tiktok_agent:
            logger.error("TikTokAgent is unavailable.")
            sys.exit(1)
        result = factory.tiktok_agent.post_video(
            video_path=args.tiktok_post,
            title="",  # Will be auto-generated
            category="nature",
        )
        if result:
            logger.info(f"✅ TikTok post successful: {result}")
        else:
            logger.error("❌ TikTok post failed")
            sys.exit(1)
        sys.exit(0)

    # TikTok Daily Automation
    if args.tiktok_auto:
        if not factory.tiktok_agent:
            logger.error("TikTokAgent is unavailable.")
            sys.exit(1)
        logger.info(f"📱 TIKTOK DAILY: Cross-posting {args.tiktok_count} shorts...")
        posted = factory.tiktok_agent.run_daily_automation(count=args.tiktok_count)
        if posted == 0:
            logger.warning("No TikTok posts were made.")
        logger.info(f"✅ TikTok: {posted}/{args.tiktok_count} posted!")
        sys.exit(0)

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
