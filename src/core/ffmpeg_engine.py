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
        Stream Global Ultra-Engine v2.2:
        - Dinamik Girdi Indexleme (Garantili Ses)
        - Safe Zone Fix (MarginV=280)
        - Gelişmiş Ses Miksajı
        """
        video_id = blueprint.video_id
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        bg_music = os.path.join(self.template_dir, "bg_music.mp3")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.video_path or not os.path.exists(scene.video_path) or not scene.audio_path:
                logging.warning(f"⚠️ Sahne {i+1} eksik, atlanıyor!")
                continue
                
            # Girişleri ekle: [current_input_idx]=Video, [current_input_idx+1]=Audio
            input_args.extend(["-i", scene.video_path, "-i", scene.audio_path])
            
            v_idx = current_input_idx
            a_idx = current_input_idx + 1
            current_input_idx += 2 # Bir sonraki sahne için 2 ileri
            
            # Altyazı Yolu (Kaçış Karakterleri ile)
            abs_subs = os.path.abspath(scene.subs_path).replace("\\", "/").replace(":", "\\:")
            style = (
                "FontName=Verdana,FontSize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=280,Bold=1"
            )

            # Video Filtresi
            v_filter = (
                f"[{v_idx}:v]scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,setsar=1,"
                f"subtitles='{abs_subs}':force_style='{style}'[v{i}];"
            )
            
            # Ses Filtresi (Normalize ve Eşitle)
            a_filter = f"[{a_idx}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];"
            
            filter_complex_parts.append(v_filter)
            filter_complex_parts.append(a_filter)
            v_labels.append(f"[v{i}]")
            a_labels.append(f"[a{i}]")

        if not v_labels: return None

        # Concat Interleaved
        num_scenes = len(v_labels)
        concat_str = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
        filter_complex_parts.append(f"{concat_str}concat=n={num_scenes}:v=1:a=1[v_full][a_vocals];")

        # Audio Mixing
        map_audio = "[a_vocals]"
        if os.path.exists(bg_music):
            input_args.extend(["-i", bg_music])
            bg_idx = current_input_idx
            # Müzik ducking threshold 0.08 (Daha hassas)
            filter_complex_parts.append(
                f"[{bg_idx}:a]aloop=loop=-1:size=2e9,volume=0.12,"
                f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[bg_loop];"
                f"[bg_loop][a_vocals]sidechaincompress=threshold=0.08:ratio=12:attack=20:release=300[outa]"
            )
            map_audio = "[outa]"

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", "".join(filter_complex_parts),
            "-map", "[v_full]",
            "-map", map_audio,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-profile:v", "high", "-level", "4.2",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            final_output
        ]

        logging.info(f"🚀 Render Başlıyor (Fix v2.2): {final_output}")
        try:
            subprocess.run(cmd, check=True)
            return final_output
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Render Hatası: {e}")
            return None
