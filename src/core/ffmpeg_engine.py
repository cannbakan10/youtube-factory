import os
import subprocess

class VideoEngine:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = os.path.join(self.project_root, "assets", "cache")
        os.makedirs(self.output_dir, exist_ok=True)

    def render(self, blueprint, language="en"):
        """
        FFmpeg-First Render Engine (Shorts Edition):
        Renders vertical 1080x1920 video with burned-in dynamic subtitles and BG music.
        """
        id = blueprint.video_id
        final_output = os.path.join(self.output_dir, f"{id}_{language}_short.mp4")
        bg_music = os.path.join(self.project_root, "assets", "templates", "bg_music.mp3")
        
        # 1. Create temporary merged video/audio clips
        input_args = []
        
        for i, scene in enumerate(blueprint.scenes):
            if not scene.video_path or not os.path.exists(scene.video_path):
                print(f"      ⚠️ Missing video for scene {i+1}")
                continue
            
            scene_output = os.path.join(self.output_dir, f"{id}_{language}_scene_{i}.mp4")
            rel_subs_path = os.path.relpath(scene.subs_path, start=os.getcwd())
            
            # Stream Global Ultra-Safe Style:
            # Alignment 2 = Bottom Center, MarginV=900 moves it to the middle of 1920h
            # FontSize 24 is safe for 1080x1920 frame when displaying 1-2 words
            style = "FontName=Verdana,Alignment=2,FontSize=24,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=1,Shadow=1,MarginV=900"
            
            # Garanti 9:16 Cover Logic (No Black Bars)
            video_filter = (
                "scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                "setsar=1,"
                f"subtitles='{rel_subs_path}':force_style='{style}'"
            )

            cmd_scene = [
                "ffmpeg", "-y", "-v", "error",
                "-i", scene.video_path,
                "-i", scene.audio_path,
                "-filter_complex", f"[0:v]{video_filter}[v]",
                "-map", "[v]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-r", "30",
                "-t", str(scene.duration),
                "-pix_fmt", "yuv420p",
                "-aspect", "9:16",
                scene_output
            ]
            
            print(f"      🎬 Rendering scene {i+1}...")
            subprocess.run(cmd_scene, check=True)
            input_args.extend(["-i", scene_output])

        # 2. Concat all scenes + Mix Background Music
        num_scenes = len(input_args) // 2
        concat_filter = "".join([f"[{i}:v][{i}:a]" for i in range(num_scenes)])
        concat_filter += f"concat=n={num_scenes}:v=1:a=1[v][a];"
        
        # Add background music if exists
        if os.path.exists(bg_music):
            input_args.extend(["-i", bg_music])
            bg_input_idx = num_scenes # Since scenes are 0 to num_scenes-1
            
            # amix with ducking and forcing stereo layout for stability
            # aloop to repeat music, aformat to force stereo
            concat_filter += f"[{bg_input_idx}:a]aformat=channel_layouts=stereo,volume=0.07,aloop=loop=-1:size=2e9[bg];"
            concat_filter += f"[a]aformat=channel_layouts=stereo[a_stereo];"
            concat_filter += f"[a_stereo][bg]amix=inputs=2:duration=first:dropout_transition=2[outa]"
            map_audio = "[outa]"
        else:
            map_audio = "[a]"

        cmd_final = [
            "ffmpeg", "-y", "-v", "error",
            *input_args,
            "-filter_complex", concat_filter,
            "-map", "[v]", "-map", map_audio,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-aspect", "9:16",
            final_output
        ]

        print(f"[*] Mixing audio and finalizing {language}...")
        try:
            subprocess.run(cmd_final, check=True)
            return final_output
        except subprocess.CalledProcessError as e:
            print(f"[!] Final Render Error: {e.stderr}")
            return None
