import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoEngine:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="tr"):
        """
        Stream Global Ultra-Flow Engine v2.5:
        - ZERO Latency Transitions (Auto-trim to audio length)
        - Centered Small Subtitles (Alignment=10, FontSize=16)
        """
        video_id = getattr(blueprint, 'video_id', 'output')
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path):
                continue
            
            # Subtitle styling
            style = (
                "FontName=Verdana,FontSize=16,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=1,Shadow=1,Alignment=10,MarginV=0,Bold=1"
            )
            abs_subs = os.path.abspath(scene.subs_path).replace("\\", "/").replace(":", "\\:")
            
            duration = scene.duration # ElevenLabs'ten gelen gerçek süre

            if scene.video_path and os.path.exists(scene.video_path):
                input_args.extend(["-i", scene.video_path, "-i", scene.audio_path])
                v_in = current_input_idx
                a_in = current_input_idx + 1
                current_input_idx += 2
                
                # VİDEO TRİM ve SCALE (Geçişleri hızlandırmak için tam süreye kırpıyoruz)
                v_filter = (
                    f"[{v_in}:v]scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                    f"crop=1080:1920,setsar=1,trim=duration={duration},setpts=PTS-STARTPTS,"
                    f"subtitles='{abs_subs}':force_style='{style}'[v{i}_out];"
                )
            else:
                input_args.extend(["-i", scene.audio_path])
                a_in = current_input_idx
                current_input_idx += 1
                v_filter = (
                    f"color=c=black:s=1080x1920:d={duration}[v_black{i}];"
                    f"[v_black{i}]subtitles='{abs_subs}':force_style='{style}'[v{i}_out];"
                )
            
            # SES TRİM (Gecikmeleri önlemek için)
            a_filter = f"[{a_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}_out];"
            
            filter_complex_parts.append(v_filter)
            filter_complex_parts.append(a_filter)
            v_labels.append(f"[v{i}_out]")
            a_labels.append(f"[a{i}_out]")

        if not v_labels: return None

        num_scenes = len(v_labels)
        concat_str = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
        filter_complex_parts.append(f"{concat_str}concat=n={num_scenes}:v=1:a=1[v_full][a_full];")

        cmd = [
            "ffmpeg", "-y", "-v", "warning",
            *input_args,
            "-filter_complex", "".join(filter_complex_parts),
            "-map", "[v_full]",
            "-map", "[a_full]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            final_output
        ]

        logging.info(f"🎬 Akış Testi (v2.5) render başlıyor...")
        try:
            subprocess.run(cmd, check=True)
            return final_output
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Render Hatası: {e}")
            return None
