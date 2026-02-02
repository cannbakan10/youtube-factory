import os
import argparse
import shutil
import time
import json
import sys
import importlib.metadata

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
from src.agents.researcher import ResearchAgent
from src.agents.scriptwriter import ScriptWriter
from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.services.tts_service import TTSService
from src.services.youtube_service import YouTubeService
from src.services.branding_service import BrandingService
from src.core.ffmpeg_engine import VideoEngine
from src.agents.trend_agent import TrendAgent

load_dotenv()

class YoutubeFactory:
    def __init__(self):
        required_keys = ["GEMINI_API_KEY", "PEXELS_API_KEY", "TAVILY_API_KEY", "ELEVENLABS_API_KEY"]
        missing = [k for k in required_keys if not os.getenv(k)]
        if missing:
            print(f"⚠️ WARNING: Missing API keys: {', '.join(missing)}")
            
        self.researcher = ResearchAgent()
        self.scriptwriter = ScriptWriter()
        self.trend_agent = TrendAgent()
        self.branding = BrandingService() # Flawless Branding + AI Video
        self.youtube_service = None 

    def run(self, topic, languages=["en"], auto_upload=False, mode="info", video_type="shorts"):
        is_long = video_type == "long"
        timestamp = int(time.time())
        import unicodedata
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
        print(f"\n🚀 FACTORY STARTING ({mode_title} - {type_title}): {topic}")
        print("🚀 V8.6 - LIVE-MONITOR & STUB-BRANDING EDITION")
        
        # Initialize services
        self.tts = TTSService(output_dir=cache_dir)
        self.pexels = PexelsService(output_dir=cache_dir)
        self.pixabay = PixabayService(output_dir=cache_dir)
        self.engine = VideoEngine()

        # 0. Global Assets (Branding)
        print("🏛️ [Factory]: Verifying Branding Assets...", flush=True)
        self.branding.generate_logo(channel_name="Stream Global")
        
        # 1. Research
        print(f"🔍 Gathering inspiration and research...", flush=True)
        research_data = self.researcher.research(topic)
        
        for lang in languages:
            lang = lang.strip().lower()
            print(f"\n🌍 PROCESSING LANGUAGE: {lang.upper()}")
            
            # Update Voice for current language
            self.tts.set_voice(language=lang)
            
            # 2. Script & Blueprint
            narrative = self.scriptwriter.generate_narrative(research_data, topic, language=lang, mode=mode, video_type=video_type)
            if not narrative:
                print(f"❌ Failed to generate narrative for {lang}. Skipping.")
                continue

            blueprint = self.scriptwriter.generate_blueprint(narrative, topic, language=lang, mode=mode, video_type=video_type)
            if not blueprint:
                print(f"❌ Failed to generate blueprint for {lang}. Skipping.")
                continue
                
            blueprint.video_id = production_id
            
            # 3. Media Collection
            valid_scenes = []
            import random
            orientation = "landscape" if video_type == "long" else "portrait"
            for i, scene in enumerate(blueprint.scenes):
                print(f"   🎥 Scene {i+1}: Processing...", flush=True)
                
                # Randomize keyword order for variety
                random.shuffle(scene.keywords)
                
                # Stock Video Collection
                video_path = None
                if i % 2 == 0:
                    print(f"      🎞️ Source: Pexels", flush=True)
                    video_path = self.pexels.get_video(scene.keywords, orientation=orientation)
                    if not video_path:
                        print(f"      🔄 Pexels empty, failing over to Pixabay...", flush=True)
                        video_path = self.pixabay.get_video(scene.keywords, orientation=orientation)
                else:
                    print(f"      🎞️ Source: Pixabay", flush=True)
                    video_path = self.pixabay.get_video(scene.keywords, orientation=orientation)
                    if not video_path:
                        print(f"      🔄 Pixabay empty, failing over to Pexels...", flush=True)
                        video_path = self.pexels.get_video(scene.keywords, orientation=orientation)
                
                # Global Topic Fallback
                if not video_path:
                    print(f"      ⚠️ Scene keywords failed. Recovering with global topic: '{topic}'...", flush=True)
                    video_path = self.pexels.get_video([topic], orientation=orientation)
                
                scene.video_path = video_path
                
                # Narration & Subtitles
                audio, subs, dur = self.tts.generate_audio_with_subtitles(scene.text, lang)
                if not audio:
                    print(f"      ❌ Narration failed for {lang}! Skipping scene.", flush=True)
                    continue
                    
                scene.audio_path = audio
                scene.subs_path = subs
                scene.duration = dur
                valid_scenes.append(scene)

            if not valid_scenes:
                print(f"❌ No valid scenes generated for {lang}. Skipping.", flush=True)
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
                    print(f"   🎵 [Main]: Intelligent Theme Mapping -> {selected_file} (Mode: {mode}, Themes: {theme_keywords})")
                else:
                    # Fallback to legacy single file
                    default_bg = os.path.join(project_root, "assets", "templates", "bg_music.mp3")
                    if os.path.exists(default_bg):
                        bg_music = default_bg
                        print("   🎵 [Main]: No themed tracks found, using default bg_music.mp3.")
            
            if not bg_music:
                print("   ⚠️ [Main]: No background music tracks found. Rendering without music.")

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
                    tags = [t for t in tags if t] # Remove empty
                
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
                
                print(f"✅ VIDEO READY: {dest_path}")

                # 5. Auto-Upload
                if auto_upload:
                    if not self.youtube_service:
                        self.youtube_service = YouTubeService()
                    
                    self.youtube_service.upload_video(
                        dest_path, 
                        title, 
                        desc, 
                        tags
                    )
            else:
                print(f"❌ Render failed: {lang}")

        print(f"\n🏁 OPERATION COMPLETE. Production ID: {production_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, required=False, help="Video topic (use 'trend' for auto-discovery)")
    parser.add_argument("--langs", type=str, default="en", help="Languages (comma-separated): en,tr")
    parser.add_argument("--upload", action="store_true", help="Auto-upload to YouTube")
    parser.add_argument("--mode", type=str, default="info", choices=["info", "horror"], help="Format: info or horror")
    parser.add_argument("--list-trends", action="store_true", help="Just list current trending topics and exit")
    parser.add_argument("--bulk", action="store_true", help="Produce videos for ALL discovered trends (works with 'trend' topic)")
    parser.add_argument("--type", type=str, default="shorts", choices=["shorts", "long"], help="Video type: shorts (9:16) or long (16:9)")
    args = parser.parse_args()

    factory = YoutubeFactory()

    if args.list_trends:
        print("\n🔍 Fetching latest viral trends...")
        trends = factory.trend_agent.get_trending_topics()
        for i, t in enumerate(trends):
            print(f"{i+1}. 🔥 {t['topic']}")
            print(f"   💡 {t['reason']}\n")
        exit()

    langs = args.langs.split(",")

    # Handle Trend Selection
    if args.topic and args.topic.lower() == "trend":
        print("\n🌊 Auto-Trend Mode: Selecting viral topics...")
        trends = factory.trend_agent.get_trending_topics(count=5)
        
        if not trends:
            print("❌ No trends found. Please provide a manual topic.")
            exit()

        if args.bulk:
            print(f"🚀 BULK MODE: Producing {len(trends)} trending videos automatically!")
            for i, t in enumerate(trends):
                print(f"\n🎬 [Bulk {i+1}/{len(trends)}] Starting: {t['topic']}")
                try:
                    factory.run(topic=t['topic'], languages=langs, auto_upload=args.upload, mode=args.mode, video_type=args.type)
                except Exception as e:
                    print(f"⚠️ Failed to produce trend video '{t['topic']}': {e}")
            print(f"\n✅ BULK PRODUCTION COMPLETE!")
        else:
            args.topic = trends[0]['topic']
            print(f"✅ Selected Top Trend: {args.topic}")
            factory.run(topic=args.topic, languages=langs, auto_upload=args.upload, mode=args.mode, video_type=args.type)
    elif args.topic:
        # Manual Topic
        factory.run(topic=args.topic, languages=langs, auto_upload=args.upload, mode=args.mode, video_type=args.type)
    else:
        print("❌ Error: Please provide a --topic or use 'trend'.")
