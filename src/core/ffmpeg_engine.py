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
        Stream Global Ultra-Flow Engine v4.1 (Stable Factory):
        - Correct Label Interleaving (Fixes CI Render Failure)
        - Cross-Platform Font Support (sans-serif fallback)
        - Optimized Audio Balance (Lower Background Levels)
        - Discrete Word-Sync Subtitles (Reduced Font Size)
        """
        video_id = getattr(blueprint, 'video_id', 'output')
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        # 1. Background Music Input
        music_in = None
        if hasattr(blueprint, 'music_path') and blueprint.music_path and os.path.exists(blueprint.music_path):
            input_args.extend(["-i", blueprint.music_path])
            music_in = current_input_idx
            current_input_idx += 1

        # Use a generic font for CI compatibility
        font_name = "sans" if os.name != 'nt' else "Arial"
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path): continue
            
            # Subtitle styling: Smaller font size (55) as requested by user
            style = (
                f"FontName={font_name},FontSize=55,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=3,Shadow=0,Alignment=10,MarginV=20,Bold=1"
            )
            
            subs_path = os.path.abspath(scene.subs_path)
            if os.name == 'nt':
                subs_path = subs_path.replace("\\", "/").replace(":", "\\:")
            else:
                # Subtitles filter needs backslash escaping for some characters on Linux
                subs_path = subs_path.replace("'", "'\\\\\\''")
            
            duration = scene.duration 

            # Scene Inputs: Video, Narrative Audio, SFX
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

            # --- VIDEO FILTERING ---
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
            if sfx_in is not None:
                # SFX Volume: 0.25 (as requested to be lower)
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
            logging.error("❌ Render Hatası: Hiçbir sahne için video/ses etiketi oluşmadı.")
            return None

        # 2. Concat Scenes: Labels MUST be interleaved [v0][a0][v1][a1]... for concat=v=1:a=1
        num_scenes = len(v_labels)
        interleaved_labels = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
        filter_complex_parts.append(f"{interleaved_labels}concat=n={num_scenes}:v=1:a=1[v_full][a_no_music];")

        # 3. Global Audio Mix: Narrative/SFX + Background Music
        if music_in is not None:
            # Music Volume: 0.1 (very low to avoid overlap as requested)
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

        logging.info("🎬 Factory V4.1 (Stable Cinema) render başlıyor...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"❌ FFmpeg Hatası: {result.stderr}")
                return None
            return final_output
        except Exception as e:
            logging.error(f"❌ Render Beklenmedik Hata: {e}")
            return None
