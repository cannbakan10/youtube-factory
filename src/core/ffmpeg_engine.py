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
        Stream Global Ultra-Flow Engine v3.7 (CI Compatible):
        - Adjusted Subtitle Scaling and Font for Linux/Mac compatibility
        - Better Error Logging for FFmpeg
        """
        video_id = getattr(blueprint, 'video_id', 'output')
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        # 1. Background Music Input (If exists)
        music_in = None
        if hasattr(blueprint, 'music_path') and blueprint.music_path and os.path.exists(blueprint.music_path):
            input_args.extend(["-i", blueprint.music_path])
            music_in = current_input_idx
            current_input_idx += 1

        # Use a more generic font name or let FFmpeg fallback
        # On Ubuntu: DejaVu Sans is usually available. On Mac: Arial/Verdana.
        # We can try "Sans" which is a generic alias.
        font_name = "sans" if os.name != 'nt' else "Arial"
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path): continue
            
            style = (
                f"FontName={font_name},FontSize=60,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=3,Shadow=0,Alignment=10,MarginV=15,Bold=1"
            )
            
            # FFmpeg subtitles filter path escaping
            subs_path = os.path.abspath(scene.subs_path)
            if os.name == 'nt':
                subs_path = subs_path.replace("\\", "/").replace(":", "\\:")
            else:
                subs_path = subs_path.replace("'", "'\\\\\\''") # Escape single quotes for many shells
            
            duration = scene.duration 

            # Scene Inputs: Video (if exists), Narrative Audio, SFX (if exists)
            v_in = None
            if scene.video_path and os.path.exists(scene.video_path):
                input_args.extend(["-i", scene.video_path])
                v_in = current_input_idx
                current_input_idx += 1
            
            input_args.extend(["-i", scene.audio_path])
            a_narrative_in = current_input_idx
            current_input_idx += 1
            
            sfx_in = None
            if scene.sfx_path and os.path.exists(scene.sfx_path):
                input_args.extend(["-i", scene.sfx_path])
                sfx_in = current_input_idx
                current_input_idx += 1

            # Video Filter (Dynamic scaling and Subtitles)
            if v_in is not None:
                v_filter = (
                    f"[{v_in}:v]scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                    f"crop=1080:1920,setsar=1,trim=duration={duration},setpts=PTS-STARTPTS,"
                    f"subtitles='{subs_path}':force_style='{style}'[v{i}_out];"
                )
            else:
                v_filter = (
                    f"color=c=black:s=1080x1920:d={duration}[v_black{i}];"
                    f"[v_black{i}]subtitles='{subs_path}':force_style='{style}'[v{i}_out];"
                )
            
            # Audio Mix (Scene level): Narrative + SFX
            if sfx_in is not None:
                a_filter = (
                    f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a{i}_nar];"
                    f"[{sfx_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,volume=0.25[a{i}_sfx];"
                    f"[a{i}_nar][a{i}_sfx]amix=inputs=2:duration=first:dropout_transition=0[a{i}_mixed];"
                    f"[a{i}_mixed]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}_out];"
                )
            else:
                a_filter = f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}_out];"
            
            filter_complex_parts.append(v_filter)
            filter_complex_parts.append(a_filter)
            v_labels.append(f"[v{i}_out]")
            a_labels.append(f"[a{i}_out]")

        if not v_labels: 
            logging.error("❌ Render Hatası: Herhangi bir sahne oluşturulamadı (Ses dosyaları eksik mi?)")
            return None

        # 2. Concat all scenes
        num_scenes = len(v_labels)
        concat_v_labels = "".join(v_labels)
        concat_a_labels = "".join(a_labels)
        filter_complex_parts.append(f"{concat_v_labels}{concat_a_labels}concat=n={num_scenes}:v=1:a=1[v_full][a_no_music];")

        # 3. Global Audio Mix: Concat Audio + Background Music
        if music_in is not None:
            filter_complex_parts.append(
                f"[{music_in}:a]aloop=loop=-1:size=2e9,volume=0.1[bg_music];"
                f"[a_no_music][bg_music]amix=inputs=2:duration=first:dropout_transition=2[a_full];"
            )
        else:
            filter_complex_parts.append(f"[a_no_music]copy[a_full];")

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", "".join(filter_complex_parts),
            "-map", "[v_full]",
            "-map", "[a_full]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            final_output
        ]

        logging.info(f"🎬 Factory V3.7 (CI Ready) render başlıyor...")
        try:
            # Capture output to see what exactly fails
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"❌ FFmpeg Hatası: {result.stderr}")
                return None
            return final_output
        except Exception as e:
            logging.error(f"❌ Beklenmedik Render Hatası: {e}")
            return None
