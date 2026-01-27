import os
import subprocess

def test_music_mix():
    # Target a recent video to test the overlay
    input_video = "assets/productions/The_Unexplained_Mystery_of_the_1769503827/en/The_Unexplained_Mystery_of_the_1769503827_en.mp4"
    bg_music = "assets/templates/bg_music.mp3"
    output_video = "assets/cache/music_test_output.mp4"

    if not os.path.exists(input_video):
        print(f"❌ Test video not found at {input_video}. Please run a generation first or update the path.")
        return

    print(f"🎬 Mixing {bg_music} into {input_video}...")

    # FFmpeg command to:
    # 1. Take video as input 0
    # 2. Take background music as input 1 (looped)
    # 3. Lower music volume to 10%
    # 4. Mix them together, keeping the video's original duration
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-stream_loop", "-1", "-i", bg_music,
        "-filter_complex", 
        "[1:a]volume=0.10[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a_final]",
        "-map", "0:v",
        "-map", "[a_final]",
        "-c:v", "copy", # Copy video codec for speed
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_video
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ TEST COMPLETE: {output_video}")
            print("🔊 Music added at 10% volume. Please check the file.")
        else:
            print(f"❌ FFmpeg Error: {result.stderr}")
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_music_mix()
