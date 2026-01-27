import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoEngine:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="en"):
        """
        Stream Global Ultra-Flow Engine v5.1 (Professional Global Edition):
        - Subtitle Alignment=2 (Bottom Center) for standard readability.
        - Text scale optimization for English chunks.
        - Video Looping (Fixes cut-off issues).
        - Pure Narration Audio.
        """
        video_id = getattr(blueprint, 'video_id', 'output')
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        # Professional font selection (Arial/Sans)
        font_name = "sans" if os.name != 'nt' else "Arial"
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path): continue
            
            # Subtitle styling: FontSize=30 with wrapping support via grouping 
            # Alignment=2 is Bottom-Center (Standard for professional videos)
            style = (
                f"FontName={font_name},FontSize=30,PrimaryColour=&H00FFFFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=1.5,Shadow=0.5,Alignment=2,MarginV=60,Bold=1"
            )
            
            subs_path = os.path.abspath(scene.subs_path)
            if os.name == 'nt':
                subs_path = subs_path.replace("\\", "/").replace(":", "\\:")
            else:
                subs_path = subs_path.replace("'", "'\\\\\\''")
            
            duration = scene.duration 

            # Scene Inputs: Video (LOOPED to prevent cut-off), Narrative Audio
            v_in = None
            if scene.video_path and os.path.exists(scene.video_path):
                # We use stream_loop -1 to ensure video covers the audio duration
                input_args.extend(["-stream_loop", "-1", "-i", scene.video_path])
                v_in = current_input_idx
                current_input_idx += 1
            
            input_args.extend(["-i", scene.audio_path])
            a_narrative_in = current_input_idx
            current_input_idx += 1
            
            # --- VIDEO FILTERING ---
            # Added fps=30 and force_divisible_by=2 for encoding stability
            v_filters = [
                "scale=w=1080:h=1920:force_original_aspect_ratio=increase",
                "crop=1080:1920",
                "setsar=1",
                f"trim=duration={duration}",
                "setpts=PTS-STARTPTS",
                f"subtitles='{subs_path}':force_style='{style}'"
            ]
            
            if v_in is not None:
                v_filter = f"[{v_in}:v]{','.join(v_filters)}[v{i}_out];"
            else:
                v_filter = (
                    f"color=c=black:s=1080x1920:d={duration}[v_black{i}];"
                    f"[v_black{i}]{','.join(v_filters)}[v{i}_out];"
                )
            
            # --- AUDIO FILTERING ---
            a_filter = f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}_out];"
            
            filter_complex_parts.append(v_filter)
            filter_complex_parts.append(a_filter)
            v_labels.append(f"[v{i}_out]")
            a_labels.append(f"[a{i}_out]")

        if not v_labels: return None

        # Concat Scenes
        num_scenes = len(v_labels)
        interleaved_labels = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
        filter_complex_parts.append(f"{interleaved_labels}concat=n={num_scenes}:v=1:a=1[v_full][a_full];")

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", "".join(filter_complex_parts),
            "-map", "[v_full]",
            "-map", "[a_full]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-shortest", 
            final_output
        ]

        logging.info("🎬 Factory V5.1 (Professional English) render starting...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"❌ FFmpeg Error: {result.stderr}")
                return None
            return final_output
        except Exception as e:
            logging.error(f"❌ Render Error: {e}")
            return None
