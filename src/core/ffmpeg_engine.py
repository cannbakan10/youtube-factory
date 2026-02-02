import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoEngine:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="en", bg_music_path=None, video_type="shorts"):
        """
        Stream Global Ultra-Flow Engine v8.5 (Pro-Mix + Long Form):
        - Multi-layer audio mixing (Narrative + Music + SFX).
        - Supports Shorts (9:16) and Long Form (16:9).
        - Dynamic Typography & Safe Zones.
        """
        is_long = video_type == "long"
        width, height = (1920, 1080) if is_long else (1080, 1920)
        margin_v = 50 if is_long else 60
        font_size = 20 if is_long else 12
        
        video_id = getattr(blueprint, 'video_id', 'output')
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        # Professional font selection (Standard fonts for Linux/GitHub Runners)
        font_name = "DejaVu Sans" if os.name != 'nt' else "Arial"
        
        valid_scenes_count = 0
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path):
                logging.warning(f"⚠️ Skipping Scene {i+1}: Missing audio file.")
                continue
            
            if scene.duration <= 0.1:
                logging.warning(f"⚠️ Skipping Scene {i+1}: Duration too short ({scene.duration}s).")
                continue

            # Subtitle styling
            style = (
                f"FontName={font_name},FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H000000,"
                f"BorderStyle=1,Outline=1.0,Shadow=0.5,Alignment=2,MarginV={margin_v},Bold=1"
            )
            
            # Robust path escaping for subtitles filter (Critical for Linux/Ubuntu)
            subs_path = os.path.abspath(scene.subs_path)
            if os.name == 'nt':
                safe_subs_path = subs_path.replace("\\", "/").replace(":", "\\:")
            else:
                # On Linux, colons in filter paths must be escaped, though rare in absolute paths
                # But single quotes are the real killer.
                safe_subs_path = subs_path.replace("'", "'\\\\\\''")
            
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
            v_filters = [
                "fps=30",
                f"scale=w={width}:h={height}:force_original_aspect_ratio=increase",
                f"crop={width}:{height}",
                "setsar=1",
                "eq=brightness=0.04:contrast=1.15:saturation=1.10", 
                "vignette=angle=0.25:x0=w/2:y0=h/2", 
                f"trim=duration={duration}",
                "setpts=PTS-STARTPTS",
                f"subtitles=f='{safe_subs_path}':force_style='{style}'",
                "format=yuv420p"
            ]
            
            if v_in is not None:
                v_filter = f"[{v_in}:v]{','.join(v_filters)}[v_sc{valid_scenes_count}];"
            else:
                v_filter = (
                    f"color=c=black:s={width}x{height}:d={duration},fps=30[v_black{valid_scenes_count}];"
                    f"[v_black{valid_scenes_count}]{','.join(v_filters)}[v_sc{valid_scenes_count}];"
                )
            
            # --- AUDIO FILTERING (Narrative + SFX Mix) ---
            fade_dur = min(0.5, duration / 2)
            fade_out_st = max(0, duration - fade_dur)
            
            if sfx_in is not None:
                filter_complex_parts.append(
                    f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.30[a_voc{valid_scenes_count}];"
                    f"[{sfx_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.4[a_sfx_raw{valid_scenes_count}];"
                    f"[a_sfx_raw{valid_scenes_count}]afade=t=in:st=0:d={fade_dur},afade=t=out:st={fade_out_st}:d={fade_dur}[a_sfx{valid_scenes_count}];"
                    f"[a_voc{valid_scenes_count}][a_sfx{valid_scenes_count}]amix=inputs=2:duration=first:dropout_transition=0[a_sc{valid_scenes_count}];"
                )
            else:
                filter_complex_parts.append(
                    f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.30[a_sc{valid_scenes_count}];"
                )
            
            filter_complex_parts.append(v_filter)
            v_labels.append(f"[v_sc{valid_scenes_count}]")
            a_labels.append(f"[a_sc{valid_scenes_count}]")
            valid_scenes_count += 1

        if not v_labels: 
            logging.error("❌ Render Error: No valid scenes generated.")
            return None

        # --- INTRO SUPPORT ---
        intro_filename = "fixed_intro2.mp4" if not is_long else "fixed_intro.mp4"
        intro_path = os.path.join(self.project_root, "assets", "branding", intro_filename)
        has_intro = os.path.exists(intro_path)
        
        if has_intro:
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", intro_path]
                intro_duration = float(subprocess.check_output(cmd).decode().strip())
                cmd_audio = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", intro_path]
                has_audio = len(subprocess.check_output(cmd_audio).decode().strip()) > 0
            except Exception:
                intro_duration = 3.0
                has_audio = False

            input_args.extend(["-i", intro_path])
            intro_in = current_input_idx
            current_input_idx += 1
            
            v_intro_filter = f"[{intro_in}:v]fps=30,scale=w={width}:h={height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,setpts=PTS-STARTPTS,format=yuv420p[v_intro];"
            if has_audio:
                a_intro_filter = f"[{intro_in}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS,volume=0.8[a_intro];"
            else:
                a_intro_filter = f"anullsrc=channel_layout=stereo:sample_rate=44100[a_intro_raw];[a_intro_raw]atrim=duration={intro_duration},asetpts=PTS-STARTPTS[a_intro];"
            filter_complex_parts.append(v_intro_filter + a_intro_filter)

        # Concat Scenes
        used_scenes = [s for s in blueprint.scenes if s.audio_path and os.path.exists(s.audio_path) and s.duration > 0.1]
        
        v_parts = [v_labels[i] for i, s in enumerate(used_scenes) if getattr(s, 'is_trailer', False)]
        a_parts = [a_labels[i] for i, s in enumerate(used_scenes) if getattr(s, 'is_trailer', False)]
        
        main_v = [v_labels[i] for i, s in enumerate(used_scenes) if not getattr(s, 'is_trailer', False)]
        main_a = [a_labels[i] for i, s in enumerate(used_scenes) if not getattr(s, 'is_trailer', False)]
        
        v_seq = v_parts + (["[v_intro]"] if has_intro else []) + main_v
        a_seq = a_parts + (["[a_intro]"] if has_intro else []) + main_a
        
        if not v_seq:
            logging.error("❌ Render Error: No scenes to concatenate.")
            return None

        interleaved = "".join([f"{v}{a}" for v, a in zip(v_seq, a_seq)])
        filter_complex_parts.append(f"{interleaved}concat=n={len(v_seq)}:v=1:a=1[v_full][a_narrative];")

        # --- BACKGROUND MUSIC ---
        final_video_label = "[v_full]"
        final_audio_label = "[a_narrative]"
        
        if bg_music_path and os.path.exists(bg_music_path):
            input_args.extend(["-stream_loop", "-1", "-i", bg_music_path])
            bg_in = current_input_idx
            bg_vol = 0.03 if is_long else 0.08
            filter_complex_parts.append(
                f"[{bg_in}:a]volume={bg_vol}[bg_low];"
                f"[a_narrative][bg_low]amix=inputs=2:duration=first:dropout_transition=0[a_final]"
            )
            final_audio_label = "[a_final]"

        filter_script_path = os.path.join(self.output_dir, f"filter_{video_id}.txt")
        with open(filter_script_path, "w", encoding="utf-8") as f:
            f.write("".join(filter_complex_parts))

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex_script", filter_script_path,
            "-map", final_video_label, "-map", final_audio_label,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-shortest", final_output
        ]

        logging.info(f"🎬 Factory V8.5 starting render: {final_output}")
        try:
            # Using run with check=True to raise exception on failure
            # Added more diagnostic info by NOT capturing output, so it streams to console
            result = subprocess.run(cmd, capture_output=False)
            if result.returncode != 0:
                return None
            return final_output
        except Exception as e:
            logging.error(f"❌ Render Error: {e}")
            return None
