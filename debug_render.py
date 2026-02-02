import os
import sys

def test_render():
    project_root = "/Users/sergenbakan/Youtuber/youtube-factory"
    sys.path.append(os.path.join(project_root, "src"))
    
    from core.ffmpeg_engine import VideoEngine
    from agents.scriptwriter import VideoBlueprint, SceneBlueprint
    
    engine = VideoEngine()
    
    dummy_video = os.path.join(project_root, "assets", "debug_video.mp4")
    if not os.path.exists(dummy_video):
        os.system(f"ffmpeg -y -f color -c:v libx264 -s 720x1280 -t 1 {dummy_video}")
    
    dummy_audio = os.path.join(project_root, "assets", "debug_audio.mp3")
    if not os.path.exists(dummy_audio):
        os.system(f"ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 1 -q:a 9 {dummy_audio}")

    dummy_sfx = os.path.join(project_root, "assets", "debug_sfx.mp3")
    if not os.path.exists(dummy_sfx):
        os.system(f"ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 1 -q:a 9 {dummy_sfx}")
    
    # Very short scene to test afade
    scene = SceneBlueprint(
        text="A.",
        keywords=["test"],
        sfx_prompt="test sfx",
        is_trailer=True,
        video_path=dummy_video,
        audio_path=dummy_audio,
        sfx_path=dummy_sfx,
        subs_path=os.path.join(project_root, "assets", "debug_subs.srt"),
        duration=0.4
    )
    
    with open(scene.subs_path, "w") as f:
        f.write("1\n00:00:00,000 --> 00:00:00,400\nTEST")
    
    blueprint = VideoBlueprint(
        video_id="debug_test",
        metadata={"title": "Test", "description": "Test", "tags": []},
        scenes=[scene]
    )
    
    print("🚀 Running short duration test (0.4s)...")
    res = engine.render(blueprint, language="tr", video_type="shorts")
    if res:
        print(f"✅ Render Success: {res}")
    else:
        print("❌ Render Failed!")

if __name__ == "__main__":
    test_render()
