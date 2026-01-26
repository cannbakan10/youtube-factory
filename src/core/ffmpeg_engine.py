import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoEngine:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        self.template_dir = os.path.join(self.project_root, "assets", "templates")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="tr"):
        """
        Stream Global Ultra-Engine v2.1:
        - Safe Zone Fix (MarginV=280)
        - Audio Ducking (Müzik kısma)
        - 1080x1920 Force Crop
        """
        video_id = blueprint.video_id
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        bg_music = os.path.join(self.template_dir, "bg_music.mp3")
        
        input_args = []
        filter_complex_parts = []
        
        # Filtre zinciri için etiket listeleri
        v_labels = []
        a_labels = []

        for i, scene in enumerate(blueprint.scenes):
            if not scene.video_path or not os.path.exists(scene.video_path):
                logging.warning(f"⚠️ Sahne {i+1} video eksik, atlanıyor!")
                continue
                
            # Girdileri ekle
            input_args.extend(["-i", scene.video_path, "-i", scene.audio_path])
            
            v_idx = 2 * i
            a_idx = 2 * i + 1
            
            # Windows/Linux uyumlu path düzeltmesi
            abs_subs = os.path.abspath(scene.subs_path).replace("\\", "/").replace(":", "\\:")
            
            # GÜVENLİ ALAN AYARI (MarginV=280)
            style = (
                "FontName=Arial,FontSize=24,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=280,Bold=1"
            )

            # Video Filtresi: Ölçekle -> Kırp -> Altyazı Ekle
            v_filter = (
                f"[{v_idx}:v]scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,setsar=1,"
                f"subtitles='{abs_subs}':force_style='{style}'[v{i}];"
            )
            
            # Ses Filtresi: Formatı eşitle (44.1kHz Stereo)
            a_filter = f"[{a_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"
            
            filter_complex_parts.append(v_filter)
            filter_complex_parts.append(a_filter)
            v_labels.append(f"[v{i}]")
            a_labels.append(f"[a{i}]")

        if not v_labels:
            logging.error("❌ Hiçbir sahne işlenemedi!")
            return None

        # Concat (Birleştirme)
        num_scenes = len(v_labels)
        concat_str = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
        filter_complex_parts.append(f"{concat_str}concat=n={num_scenes}:v=1:a=1[v_full][a_vocals];")

        # Müzik ve Ducking
        map_audio = "[a_vocals]"
        if os.path.exists(bg_music):
            input_args.extend(["-i", bg_music])
            bg_idx = 2 * num_scenes
            
            # Müzik Döngüsü ve Sidechain Compression (Konuşma varken müziği %10'a düşür)
            filter_complex_parts.append(
                f"[{bg_idx}:a]aloop=loop=-1:size=2e9,volume=0.15,"
                f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[bg_loop];"
                f"[bg_loop][a_vocals]sidechaincompress=threshold=0.1:ratio=10:attack=10:release=300[outa]"
            )
            map_audio = "[outa]"

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", "".join(filter_complex_parts),
            "-map", "[v_full]",
            "-map", map_audio,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            final_output
        ]

        logging.info(f"🚀 Render Başlıyor: {final_output}")
        try:
            subprocess.run(cmd, check=True)
            logging.info("✅ Render Tamamlandı.")
            return final_output
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Render Hatası: {e}")
            return None
