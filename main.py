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

REQUIRED_KEYS = ["GEMINI_API_KEY", "OPENAI_API_KEY", "PEXELS_API_KEY", "TAVILY_API_KEY"]

class YoutubeFactory:
    def __init__(self):
        # Verify keys
        missing_keys = [key for key in REQUIRED_KEYS if not os.getenv(key)]
        if missing_keys:
            print(f"[!] Error: Missing environment variables: {', '.join(missing_keys)}")
            exit(1)
            
        self.researcher = ResearchAgent()
        self.scriptwriter = ScriptWriter()
        self.pexels = PexelsService()
        self.youtube_service = None # Lazy init to avoid OAuth on every run

    def run(self, topic, languages=["tr"]):
        # Force only TR during development/prototype
        languages = ["tr"]
        
        # 0. Setup Folder Structure
        timestamp = int(time.time())
        # Create a clean folder name from topic
        topic_slug = "".join(c for c in topic if c.isalnum() or c.isspace()).replace(" ", "_")[:30]
        production_id = f"{topic_slug}_{timestamp}"
        
        # USE ABSOLUTE PATHS RELATIVE TO PROJECT ROOT
        project_root = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(project_root, "assets", "productions", production_id)
        cache_dir = os.path.join(project_root, "assets", "cache")
        
        # Cleanup general cache to save space
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(base_dir, exist_ok=True)

        print(f"\n🚀 {'='*20} SHORTS FACTORY: {production_id} {'='*20}")
        print(f"📌 [TOPIC]: {topic}")
        print(f"📁 [OUTPUT]: {base_dir}")

        # Re-initialize services with the specific production dir if needed
        # (Though we keep cache for temp files and move final to base_dir)
        self.tts = TTSService(output_dir=cache_dir)
        self.pexels = PexelsService(output_dir=cache_dir)
        self.engine = VideoEngine()

        # 1. Research (Global Context)
        print(f"\n🔍 [STEP 1]: Global Research Intelligence...")
        research_data = self.researcher.research(topic)
        
        for lang in languages:
            lang = lang.strip().lower()
            lang_dir = os.path.join(base_dir, lang)
            os.makedirs(lang_dir, exist_ok=True)
            
            print(f"\n🌍 {'-'*10} CULTURAL ADAPTATION: {lang.upper()} {'-'*10}")
            
            # 2. Advanced Scripting (Two-Stage)
            print(f"✍️ [STEP 2.1]: Drafting high-quality narrative...")
            master_narrative = self.scriptwriter.generate_narrative(research_data, topic)
            print(f"      📝 Narrative Drafted ({len(master_narrative)} chars)")
            
            print(f"✍️ [STEP 2.2]: Building scene blueprint...")
            script_blueprint = self.scriptwriter.generate_blueprint(master_narrative, topic, language=lang)
            
            # 3. Asset Gathering
            print(f"🎨 [STEP 3]: Collecting visuals and voice-overs...")
            for i, scene in enumerate(script_blueprint.scenes):
                print(f"   🎥 Scene {i+1}/{len(script_blueprint.scenes)}: Visual search...")
                video_path = self.pexels.get_video(scene.keywords)
                scene.video_path = video_path
                
                print(f"   🎙️ Scene {i+1}: TTS & Subtitle sync...")
                print(f"      📝 Input Text: {scene.text}")
                audio_path, subs_path, actual_duration = self.tts.generate_audio_with_subtitles(scene.text, lang)
                scene.audio_path = audio_path
                scene.subs_path = subs_path
                scene.duration = actual_duration # Use precise duration
            
            # 4. Neural Rendering
            print(f"🎬 [STEP 4]: Rendering {lang.upper()} vertical masterpiece...")
            final_video_path = self.engine.render(script_blueprint, language=lang)
            
            if final_video_path and os.path.exists(final_video_path):
                # Move final video to its specific language folder
                dest_fn = f"{production_id}_{lang}.mp4"
                dest_path = os.path.join(lang_dir, dest_fn)
                
                print(f"[*] Moving: {final_video_path} -> {dest_path}")
                shutil.move(final_video_path, dest_path)
                
                # Save metadata as JSON for future reference
                with open(os.path.join(lang_dir, "metadata.json"), "w", encoding="utf-8") as f:
                    meta = script_blueprint.metadata
                    meta['timestamp'] = timestamp
                    meta['topic'] = topic
                    import json
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                
                print(f"✅ [COMPLETED]: {lang.upper()} version saved in {lang_dir}")

                # Optional AUTO-UPLOAD
                if getattr(args, 'upload', False):
                    if not self.youtube_service:
                        try:
                            self.youtube_service = YouTubeService()
                        except Exception as e:
                            print(f"❌ [YouTube Auth Error]: {e}")
                    
                        if self.youtube_service:
                            title = script_blueprint.metadata.get('title', topic)
                            desc = script_blueprint.metadata.get('description', f"{topic} #shorts")
                            tags = script_blueprint.metadata.get('tags', ["shorts", "viral"])
                            self.youtube_service.upload_video(dest_path, title, desc, tags)
            else:
                print(f"❌ [FAILED]: Render failed for {lang}")
            
            # Sub-step cleanup: Remove temp files for this language to free up space
            if os.path.exists(cache_dir):
                for file in os.listdir(cache_dir):
                    file_path = os.path.join(cache_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f"      ⚠️ Cleanup error: {e}")

        print(f"\n🏆 {'='*20} FULL LAUNCH KIT READY {'='*20}")
        print(f"📍 Final Assets Location: {base_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Multilingual Shorts Factory")
    parser.add_argument("--topic", type=str, required=True, help="Video topic")
    parser.add_argument("--langs", type=str, default="tr,en,es", help="Target languages")
    parser.add_argument("--upload", action="store_true", help="Auto-upload to YouTube")
    args = parser.parse_args()

    factory = YoutubeFactory()
    factory.run(args.topic, languages=args.langs.split(","))
