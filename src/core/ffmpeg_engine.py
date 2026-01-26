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
        Stream Global Ultra-Flow Engine v3.0:
        - Precise Word-Sync Subtitles (ElevenLabs Hyper-Sync)
        - Multi-Audio Mixing (Narrative + Ambient SFX)
        - High-Impact Cinematic Look
        """
        video_id = getattr(blueprint, 'video_id', 'output')
        final_output = os.path.join(self.output_dir, f"{video_id}_{language}_final.mp4")
        
        input_args = []
        filter_complex_parts = []
        v_labels = []
        a_labels = []

        current_input_idx = 0
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.audio_path or not os.path.exists(scene.audio_path): continue
            
            # Subtitle styling: High-impact Yellow with Black Outline, Centered
            # Using Arial for better rendering of special chars and bold look
            style = (
                "FontName=Arial,FontSize=80,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=4,Shadow=0,Alignment=10,MarginV=10,Bold=1"
            )
            abs_subs = os.path.abspath(scene.subs_path).replace("\\", "/").replace(":", "\\:")
            duration = scene.duration 

            # Inputs: Video (if exists), Audio, SFX (if exists)
            input_args.extend(["-i", scene.audio_path if not scene.video_path else scene.video_path])
            if scene.video_path: input_args.extend(["-i", scene.audio_path])
            
            v_in = current_input_idx if scene.video_path else None
            a_narrative_in = current_input_idx + 1 if scene.video_path else current_input_idx
            
            # SFX handling
            sfx_in = None
            if scene.sfx_path and os.path.exists(scene.sfx_path):
                input_args.extend(["-i", scene.sfx_path])
                sfx_in = current_input_idx + 2 if scene.video_path else current_input_idx + 1
                current_input_idx += 3 if scene.video_path else 2
            else:
                current_input_idx += 2 if scene.video_path else 1

            # Video Filter (Dynamic scaling and Subtitles)
            if v_in is not None:
                v_filter = (
                    f"[{v_in}:v]scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                    f"crop=1080:1920,setsar=1,trim=duration={duration},setpts=PTS-STARTPTS,"
                    f"subtitles='{abs_subs}':force_style='{style}'[v{i}_out];"
                )
            else:
                v_filter = (
                    f"color=c=black:s=1080x1920:d={duration}[v_black{i}];"
                    f"[v_black{i}]subtitles='{abs_subs}':force_style='{style}'[v{i}_out];"
                )
            
            # Audio Mixing: Narrative + SFX
            if sfx_in is not None:
                # Mix narrative and SFX (SFX volume slightly lower at 0.6)
                a_filter = (
                    f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a{i}_nar];"
                    f"[{sfx_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,volume=0.6[a{i}_sfx];"
                    f"[a{i}_nar][a{i}_sfx]amix=inputs=2:duration=first:dropout_transition=0,"
                    f"aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}_out];"
                )
            else:
                a_filter = f"[{a_narrative_in}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}_out];"
            
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

        logging.info(f"🎬 Factory V3 (Cinematic) render başlıyor...")
        try:
            subprocess.run(cmd, check=True)
            return final_output
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Render Hatası: {e}")
            return None
