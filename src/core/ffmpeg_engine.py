import os
import subprocess
import logging

# Loglama ayarları (Hataları takip etmek için)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoEngine:
    def __init__(self):
        # Proje kök dizinini ve önbellek klasörünü ayarla
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        self.template_dir = os.path.join(self.project_root, "assets", "templates")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="tr"):
        """
        Stream Global Ultra-Engine: 
        9:16 Otomatik Ölçekleme, Akıllı Altyazı ve Sidechain Audio Ducking.
        """
        video_id = blueprint.video_id
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        bg_music = os.path.join(self.template_dir, "bg_music.mp3")
        
        input_args = []
        v_filter_chains = []
        a_filter_chains = []
        
        # 1. Giriş Dosyalarını ve Sahne Filtrelerini Hazırla
        for i, scene in enumerate(blueprint.scenes):
            if not os.path.exists(scene.video_path) or not os.path.exists(scene.audio_path):
                logging.warning(f"⚠️ Sahne {i} eksik: Video veya Audio bulunamadı!")
                continue

            # Her sahne için iki input ekle: [2i]=Video, [2i+1]=Audio
            input_args.extend(["-i", scene.video_path, "-i", scene.audio_path])
            
            v_idx = 2 * i
            a_idx = 2 * i + 1
            
            # Altyazı Yolu Düzenleme (FFmpeg Kaçış Karakterleri)
            # FFmpeg'in altyazı dosyası yollarında hata almaması için mutlak yol ve kaçış kullanıyoruz
            abs_subs = os.path.abspath(scene.subs_path).replace("\\", "/").replace(":", "\\:")
            
            # MODERN ALTYAZI STİLİ:
            # - Sarı metin (&H00FFFF), Siyah çerçeve, Kalın font.
            # - MarginV=280: YouTube butonlarının hemen üzerinde, güvenli alanda.
            style = (
                "FontName=Verdana,FontSize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=280,Bold=1"
            )

            # VİDEO İŞLEME: 1080x1920 Kesin Çözünürlük
            v_filter = (
                f"[{v_idx}:v]scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,setsar=1,"
                f"subtitles='{abs_subs}':force_style='{style}'[v{i}];"
            )
            
            # SES İŞLEME: Tüm sesleri aynı formata (Stereo, 44.1kHz) getiriyoruz ki concat hata vermesin.
            a_filter = f"[{a_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"
            
            v_filter_chains.append(v_filter)
            a_filter_chains.append(a_filter)

        # 2. Concat (Birleştirme) Etiketlerini Oluştur
        num_scenes = len(v_filter_chains) # Use actual count of processed scenes
        concat_labels = "".join([f"[v{i}][a{i}]" for i in range(num_scenes)])
        concat_filter = f"{concat_labels}concat=n={num_scenes}:v=1:a=1[v_full][a_full];"

        # 3. Arka Plan Müziği ve Sidechain Compression (Profesyonel Dokunuş)
        if os.path.exists(bg_music):
            input_args.extend(["-i", bg_music])
            bg_idx = 2 * num_scenes
            
            # Konuşma sesi (a_full) varken müziği otomatik kısan (ducking) filtre
            # threshold=0.05: Konuşma başladığında müziği anında kısar.
            audio_mixing_filter = (
                f"[{bg_idx}:a]aloop=loop=-1:size=2e9,volume=0.10,"
                f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[bg_ready];"
                f"[bg_ready][a_full]sidechaincompress=threshold=0.05:ratio=16:attack=20:release=300[outa]"
            )
            map_audio = "[outa]"
        else:
            audio_mixing_filter = ""
            map_audio = "[a_full]"

        # Tüm filtreleri birleştir
        full_filter_complex = "".join(v_filter_chains) + "".join(a_filter_chains) + concat_filter + audio_mixing_filter

        # 4. Final FFmpeg Komutu
        cmd = [
            "ffmpeg", "-y", "-v", "warning", # Sadece uyarıları göster, konsolu temiz tut
            *input_args,
            "-filter_complex", full_filter_complex,
            "-map", "[v_full]",
            "-map", map_audio,
            "-c:v", "libx264", 
            "-preset", "slow", # Daha iyi sıkıştırma ve kalite
            "-crf", "18",      # Gözle görülür kayıp olmayan yüksek kalite (0-51 arası, düşük=iyi)
            "-c:a", "aac", 
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", # Video inerken oynamaya başlasın (YT dostu)
            final_output
        ]

        logging.info(f"🎬 '{video_id}' için final render başlıyor...")
        
        try:
            subprocess.run(cmd, check=True)
            logging.info(f"✅ Render başarıyla tamamlandı: {final_output}")
            return final_output
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ FFmpeg Hatası: {e}")
            return None
