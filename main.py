import os
import argparse
import shutil
import time
import json
from dotenv import load_dotenv
from src.agents.researcher import ResearchAgent
from src.agents.scriptwriter import ScriptWriter
from src.services.pexels_service import PexelsService
from src.services.tts_service import TTSService
from src.services.youtube_service import YouTubeService
from src.core.ffmpeg_engine import VideoEngine

load_dotenv()

class YoutubeFactory:
    def __init__(self):
        required_keys = ["GEMINI_API_KEY", "PEXELS_API_KEY", "TAVILY_API_KEY", "ELEVENLABS_API_KEY"]
        missing = [k for k in required_keys if not os.getenv(k)]
        if missing:
            print(f"⚠️ WARNING: Missing API keys: {', '.join(missing)}")
            
        self.researcher = ResearchAgent()
        self.scriptwriter = ScriptWriter()
        self.youtube_service = None 

    def run(self, topic, languages=["en"], auto_upload=False, mode="info"):
        timestamp = int(time.time())
        topic_slug = "".join(c for c in topic if c.isalnum() or c.isspace()).replace(" ", "_")[:30]
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
        print(f"\n🚀 SHORTS FACTORY STARTING ({mode_title}): {topic}")
        
        # Initialize services
        self.tts = TTSService(output_dir=cache_dir)
        self.pexels = PexelsService(output_dir=cache_dir)
        self.engine = VideoEngine()

        # 1. Research (Used as inspiration even for horror)
        print(f"🔍 Gathering inspiration and research...")
        research_data = self.researcher.research(topic)
        
        for lang in languages:
            lang = lang.strip().lower()
            print(f"\n🌍 PROCESSING LANGUAGE: {lang.upper()}")
            
            # Update Voice for current language
            self.tts.set_voice(language=lang)
            
            # 2. Script & Blueprint (Pass mode here)
            narrative = self.scriptwriter.generate_narrative(research_data, topic, language=lang, mode=mode)
            blueprint = self.scriptwriter.generate_blueprint(narrative, topic, language=lang, mode=mode)
            blueprint.video_id = production_id
            
            # 3. Media Collection
            for i, scene in enumerate(blueprint.scenes):
                print(f"   🎥 Scene {i+1}: Processing...")
                
                video_path = self.pexels.get_video(scene.keywords)
                scene.video_path = video_path
                
                # Narration & Subtitles
                audio, subs, dur = self.tts.generate_audio_with_subtitles(scene.text, lang)
                if not audio:
                    print(f"      ❌ Narration failed for {lang}! Skipping scene.")
                    continue
                    
                scene.audio_path = audio
                scene.subs_path = subs
                scene.duration = dur

            # 4. Render
            final_path = self.engine.render(blueprint, language=lang)
            
            if final_path and os.path.exists(final_path):
                # Save output
                lang_dir = os.path.join(base_dir, lang)
                os.makedirs(lang_dir, exist_ok=True)
                dest_path = os.path.join(lang_dir, f"{production_id}_{lang}.mp4")
                shutil.move(final_path, dest_path)
                
                # Save Metadata
                meta_file = os.path.join(lang_dir, "metadata.json")
                with open(meta_file, "w", encoding="utf-8") as f:
                    meta_data = blueprint.metadata
                    meta_data['file_path'] = dest_path
                    json.dump(meta_data, f, indent=2, ensure_ascii=False)
                
                print(f"✅ VIDEO READY: {dest_path}")

                # 5. Auto-Upload
                if auto_upload:
                    if not self.youtube_service:
                        self.youtube_service = YouTubeService()
                    
                    self.youtube_service.upload_video(
                        dest_path, 
                        blueprint.metadata.get('title', topic), 
                        blueprint.metadata.get('description', ''), 
                        blueprint.metadata.get('tags', [])
                    )
            else:
                print(f"❌ Render failed: {lang}")

        print(f"\n🏁 OPERATION COMPLETE. Production ID: {production_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, required=True, help="Video topic")
    parser.add_argument("--langs", type=str, default="en", help="Languages (comma-separated): en,tr")
    parser.add_argument("--upload", action="store_true", help="Auto-upload to YouTube")
    parser.add_argument("--mode", type=str, default="info", choices=["info", "horror"], help="Format: info or horror")
    args = parser.parse_args()

    factory = YoutubeFactory()
    factory.run(topic=args.topic, languages=args.langs.split(","), auto_upload=args.upload, mode=args.mode)
