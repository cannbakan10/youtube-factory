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
        required_keys = ["GEMINI_API_KEY", "OPENAI_API_KEY", "PEXELS_API_KEY", "TAVILY_API_KEY", "ELEVENLABS_API_KEY"]
        missing = [k for k in required_keys if not os.getenv(k)]
        if missing:
            print(f"⚠️ UYARI: Şu API anahtarları eksik: {', '.join(missing)}")
            
        self.researcher = ResearchAgent()
        self.scriptwriter = ScriptWriter()
        self.youtube_service = None 

    def run(self, topic, languages=["tr"], auto_upload=False):
        timestamp = int(time.time())
        topic_slug = "".join(c for c in topic if c.isalnum() or c.isspace()).replace(" ", "_")[:30]
        production_id = f"{topic_slug}_{timestamp}"
        
        project_root = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(project_root, "assets", "productions", production_id)
        cache_dir = os.path.join(project_root, "assets", "cache")
        
        # Cache temizliği (Her üretimde sıfırla)
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(base_dir, exist_ok=True)

        print(f"\n🚀 SHORTS FACTORY BAŞLIYOR: {topic}")
        
        # Servisleri başlat
        self.tts = TTSService(output_dir=cache_dir)
        self.pexels = PexelsService(output_dir=cache_dir)
        self.engine = VideoEngine()

        # 1. Araştırma
        print(f"🔍 Konu Araştırılıyor...")
        research_data = self.researcher.research(topic)
        
        for lang in languages:
            lang = lang.strip().lower()
            print(f"\n🌍 DİL İŞLENİYOR: {lang.upper()}")
            
            # 2. Senaryo
            narrative = self.scriptwriter.generate_narrative(research_data, topic)
            blueprint = self.scriptwriter.generate_blueprint(narrative, topic, language=lang)
            blueprint.video_id = production_id # ID eşitleme
            
            # 3. Medya Toplama
            for i, scene in enumerate(blueprint.scenes):
                print(f"   🎥 Sahne {i+1}: Görsel ve Ses hazırlanıyor...")
                
                # Video İndir (Fail-safe: Video yoksa siyah ekran kullanılacak)
                video_path = self.pexels.get_video(scene.keywords)
                if not video_path:
                    print(f"      ⚠️ Video bulunamadı, sesle devam ediliyor.")
                scene.video_path = video_path
                
                # Ses ve Altyazı (SES ZORUNLUDUR)
                audio, subs, dur = self.tts.generate_audio_with_subtitles(scene.text, lang)
                if not audio:
                    print("      ❌ Ses oluşturulamadı! Sahne atlanıyor.")
                    continue
                    
                scene.audio_path = audio
                scene.subs_path = subs
                scene.duration = dur

            # 4. Render
            final_path = self.engine.render(blueprint, language=lang)
            
            if final_path and os.path.exists(final_path):
                # Çıktıyı kaydet
                lang_dir = os.path.join(base_dir, lang)
                os.makedirs(lang_dir, exist_ok=True)
                dest_path = os.path.join(lang_dir, f"{production_id}_{lang}.mp4")
                shutil.move(final_path, dest_path)
                
                # Metadata kaydet
                meta_file = os.path.join(lang_dir, "metadata.json")
                with open(meta_file, "w", encoding="utf-8") as f:
                    meta_data = blueprint.metadata
                    meta_data['file_path'] = dest_path # Upload için kolaylık
                    json.dump(meta_data, f, indent=2, ensure_ascii=False)
                
                print(f"✅ VİDEO HAZIR: {dest_path}")

                # 5. Otomatik Yükleme
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
                print(f"❌ Render başarısız oldu: {lang}")

        print(f"\n🏁 İŞLEM TAMAMLANDI. Dosyalar: {base_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, required=True, help="Video konusu")
    parser.add_argument("--langs", type=str, default="tr", help="Diller (virgülle ayır): tr,en")
    parser.add_argument("--upload", action="store_true", help="Otomatik yükle")
    args = parser.parse_args()

    factory = YoutubeFactory()
    factory.run(args.topic, languages=args.langs.split(","), auto_upload=args.upload)
