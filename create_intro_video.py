import os
import subprocess
import logging

def create_intro():
    project_root = os.path.dirname(os.path.abspath(__file__))
    branding_dir = os.path.join(project_root, "assets", "branding")
    bg_img = os.path.join(branding_dir, "intro_bg.png")
    logo = os.path.join(branding_dir, "logo.png")
    output_intro = os.path.join(branding_dir, "fixed_intro.mp4")

    if not os.path.exists(bg_img) or not os.path.exists(logo):
        print("❌ [Intro]: Background or Logo missing.")
        return

    print("🎬 [Intro]: Creating fixed cinematic intro video...")

    # FFmpeg command to create a 3-second video
    # Overlay logo on bg, with some scaling and centered.
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg_img,
        "-i", logo,
        "-filter_complex", (
            "[1:v]scale=500:-1[logo];" # Scale logo to 500px width
            "[0:v]scale=1920:1080,setsar=1[bg];" # Scale bg to 1080p
            "[bg][logo]overlay=(W-w)/2:(H-h)/2:format=auto,fade=in:st=0:d=1,fade=out:st=2:d=1[v]"
        ),
        "-map", "[v]",
        "-t", "3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_intro
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ [Intro]: Fixed intro created at {output_intro}")
    except Exception as e:
        print(f"❌ [Intro]: Failed to create intro: {e}")

if __name__ == "__main__":
    create_intro()
