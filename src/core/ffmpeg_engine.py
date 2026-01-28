import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoEngine:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="en", bg_music_path=None):
        """
        Stream Global Ultra-Flow Engine v8.0 (Audio-Vivid Update):
        - Multi-layer audio mixing (Narrative + Music + SFX).
        - Cinematic Color Grading (Contrast, Saturation, Vignette).
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
        
        valid_scenes_count = 0
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path):
                logging.warning(f"⚠️ Skipping Scene {i+1}: Missing audio file.")
                continue
            
            # Subtitle styling: FontSize 18 for high-end look.
            style = (
                f"FontName={font_name},FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=1.0,Shadow=0.5,Alignment=2,MarginV=90,Bold=1"
            )
            
            subs_path = os.path.abspath(scene.subs_path)
            if os.name == 'nt':
                subs_path = subs_path.replace("\\", "/").replace(":", "\\:")
            else:
                subs_path = subs_path.replace("'", "'\\\\\\''")
            
            duration = scene.duration 

            # Scene Inputs: Video (LOOPED), Narrative Audio, SFX (Optional)
            v_in = None
            if scene.video_path and os.path.exists(scene.video_path):
                input_args.extend(["-stream_loop", "-1", "-i", scene.video_path])
                v_in = current_input_idx
                current_input_idx += 1
            
            input_args.extend(["-i", scene.audio_path])
            a_narrative_in = current_input_idx
            current_input_idx += 1

            sfx_in = None
            if hasattr(scene, 'sfx_path') and scene.sfx_path and os.path.exists(scene.sfx_path):
                input_args.extend(["-i", scene.sfx_path])
                sfx_in = current_input_idx
                current_input_idx += 1
            
            # --- VIDEO FILTERING ---
            # Cinematic Color Grade: Subtle contrast/saturation boost + vignette for focus
            v_filters = [
                "fps=30",
                "scale=w=1080:h=1920:force_original_aspect_ratio=increase",
                "crop=1080:1920",
                "setsar=1",
                "eq=brightness=0.02:contrast=1.1:saturation=1.1",
                "vignette=angle=0.5:x0=w/2:y0=h/2",
                f"trim=duration={duration}",
                "setpts=PTS-STARTPTS",
                f"subtitles='{subs_path}':force_style='{style}'",
                "format=yuv420p"
            ]
            
            if v_in is not None:
                v_filter = f"[{v_in}:v]{','.join(v_filters)}[v_sc{valid_scenes_count}];"
            else:
                v_filter = (
                    f"color=c=black:s=1080x1920:d={duration},fps=30[v_black{valid_scenes_count}];"
                    f"[v_black{valid_scenes_count}]{','.join(v_filters)}[v_sc{valid_scenes_count}];"
                )
            
            # --- AUDIO FILTERING (Narrative + SFX Mix) ---
            a_narr_label = f"a_narr{valid_scenes_count}"
            filter_complex_parts.append(
                f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[{a_narr_label}];"
            )

            if sfx_in is not None:
                a_sfx_label = f"a_sfx{valid_scenes_count}"
                filter_complex_parts.append(
                    f"[{sfx_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.40[{a_sfx_label}];"
                )
                # Mix Narrative + SFX
                filter_complex_parts.append(
                    f"[{a_narr_label}][{a_sfx_label}]amix=inputs=2:duration=first[a_sc{valid_scenes_count}];"
                )
            else:
                # No SFX, use narrative only
                filter_complex_parts.append(f"[{a_narr_label}]acopy[a_sc{valid_scenes_count}];")
            
            filter_complex_parts.append(v_filter)
            v_labels.append(f"[v_sc{valid_scenes_count}]")
            a_labels.append(f"[a_sc{valid_scenes_count}]")
            valid_scenes_count += 1

        if not v_labels: 
            logging.error("❌ Render Error: No valid scenes generated.")
            return None

        # Concat Scenes
        interleaved_labels = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
        filter_complex_parts.append(f"{interleaved_labels}concat=n={valid_scenes_count}:v=1:a=1[v_full][a_narrative];")

        # --- BACKGROUND MUSIC MIXING ---
        final_video_label = "[v_full]"
        final_audio_label = "[a_narrative]"
        
        if bg_music_path and os.path.exists(bg_music_path):
            input_args.extend(["-stream_loop", "-1", "-i", bg_music_path])
            bg_in = current_input_idx
            current_input_idx += 1
            
            # Mix: Narrative + (BG Music at 10% volume)
            filter_complex_parts.append(
                f"[{bg_in}:a]volume=0.10[bg_low];"
                f"[a_narrative][bg_low]amix=inputs=2:duration=first:dropout_transition=0[a_final]"
            )
            final_audio_label = "[a_final]"

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", "".join(filter_complex_parts),
            "-map", final_video_label,
            "-map", final_audio_label,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-shortest", 
            final_output
        ]

        logging.info(f"🎬 Factory V7.4 (Cinematic) starting render for {valid_scenes_count} scenes...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"❌ FFmpeg Error: {result.stderr}")
                return None
            return final_output
        except Exception as e:
            logging.error(f"❌ Render Error: {e}")
            return None
