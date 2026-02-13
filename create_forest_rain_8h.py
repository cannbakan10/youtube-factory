"""
Forest Rain 8-Hour Loop Creator & YouTube Uploader
Creates a seamless 8-hour loop from a short clip and uploads with perfect SEO.
"""
import os
import sys
import json
import subprocess
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.services.youtube_service import YouTubeService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# CONFIG
# ============================================================
SOURCE_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Realistic_Forest_Rain_Ambience_Video.mp4")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "productions", "forest_rain_1h")
OUTPUT_VIDEO = os.path.join(OUTPUT_DIR, "forest_rain_1hour.mp4")
TARGET_DURATION = 1 * 60 * 60  # 1 hour in seconds = 3600

# ============================================================
# SEO-OPTIMIZED METADATA
# ============================================================
METADATA = {
    "title": "1 Hour Relaxing Forest Rain Sounds for Sleep, Study & Meditation 🌧️🌿 No Music",
    "description": """🌧️ 1 Hour of Realistic Forest Rain Ambience — No Music, No Loop Gaps 🌿

Immerse yourself in the peaceful sounds of gentle rain falling through a lush green forest. This 8-hour ambient video is perfect for:

😴 Deep Sleep & Insomnia Relief
📚 Studying, Reading & Deep Focus  
🧘 Meditation & Mindfulness
👶 Baby Sleep & Calming Anxiety
💻 Work From Home Background Ambience
🎧 ASMR & Sound Therapy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY RAIN SOUNDS HELP YOU SLEEP & FOCUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rain produces a consistent "pink noise" that masks disruptive background sounds. Studies show that natural rain sounds can:
✅ Reduce cortisol (stress hormone) levels
✅ Slow heart rate and lower blood pressure  
✅ Improve sleep quality and duration
✅ Enhance concentration and cognitive performance

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ TIMESTAMPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0:00:00 — Rain Begins
0:15:00 — Deep Relaxation
0:30:00 — Halfway Point
0:45:00 — Final Stretch

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 If this helps you relax, please LIKE 👍 and SUBSCRIBE for more ambient content!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tags: rain sounds, forest rain, sleep sounds, rain for sleeping, rain ambience, nature sounds, white noise, study music, relaxing rain, meditation sounds, ASMR rain, 8 hours rain, rain no music, deep sleep, insomnia, focus sounds, rain forest, calming sounds, anxiety relief, baby sleep sounds

#rainsounds #sleepsounds #forestrain #relaxing #whitenoise #meditation #deepsleep #studysounds #ASMR #nature #ambience #1hour #rainforsleeping #focussounds #calmingrain
""",
    "tags": [
        "rain sounds for sleeping",
        "rain sounds",
        "forest rain",
        "rain ambience",
        "1 hour rain",
        "sleep sounds",
        "relaxing rain",
        "nature sounds",
        "rain no music",
        "deep sleep",
        "white noise",
        "study sounds",
        "rain ASMR",
        "meditation rain",
        "calming rain sounds",
        "rain for focus",
        "insomnia relief",
        "baby sleep sounds",
        "rain forest ambience",
        "anxiety relief sounds",
        "rain on leaves",
        "gentle rain",
        "rain background noise",
        "overnight rain",
        "rain video 1 hour",
        "rain sleep aid",
        "nature ambience",
        "forest sounds",
        "peaceful rain",
        "rain therapy"
    ]
}


def create_seamless_loop():
    """Create an 8-hour seamless loop from the source video using stream copy."""
    
    if os.path.exists(OUTPUT_VIDEO):
        size_gb = os.path.getsize(OUTPUT_VIDEO) / (1024**3)
        if size_gb > 1.0:
            logger.info(f"8-hour video already exists ({size_gb:.1f} GB). Skipping render.")
            return True
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Get source duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", SOURCE_VIDEO],
        capture_output=True, text=True
    )
    source_duration = float(probe.stdout.strip())
    loop_count = int(TARGET_DURATION / source_duration) + 1
    
    logger.info(f"Source: {source_duration}s | Loops needed: {loop_count} | Target: {TARGET_DURATION}s")
    
    # Method: Use stream_loop with stream copy (FASTEST - no re-encoding)
    # This copies the encoded data directly, so it's extremely fast
    logger.info("Creating 8-hour seamless loop (stream copy - fast)...")
    
    cmd = [
        "ffmpeg", "-y", "-v", "warning", "-stats",
        "-stream_loop", str(loop_count - 1),  # -1 because first play counts as 1
        "-i", SOURCE_VIDEO,
        "-t", str(TARGET_DURATION),
        "-c", "copy",  # Stream copy = no re-encoding = very fast
        "-movflags", "+faststart",  # YouTube optimization
        OUTPUT_VIDEO
    ]
    
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"FFmpeg failed: {result.stderr}")
        return False
    
    # Verify output
    if os.path.exists(OUTPUT_VIDEO):
        size_gb = os.path.getsize(OUTPUT_VIDEO) / (1024**3)
        
        # Verify duration
        probe2 = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", OUTPUT_VIDEO],
            capture_output=True, text=True
        )
        actual_duration = float(probe2.stdout.strip())
        actual_hours = actual_duration / 3600
        
        logger.info(f"✅ 8-Hour video created successfully!")
        logger.info(f"   Size: {size_gb:.2f} GB")
        logger.info(f"   Duration: {actual_hours:.2f} hours ({actual_duration:.0f}s)")
        return True
    
    logger.error("Output file not found after render.")
    return False


def upload_to_youtube():
    """Upload the 8-hour video to YouTube with optimized SEO."""
    
    if not os.path.exists(OUTPUT_VIDEO):
        logger.error(f"Video not found: {OUTPUT_VIDEO}")
        return False
    
    logger.info("Uploading to YouTube...")
    
    yt = YouTubeService()
    
    upload_id = yt.upload_video(
        video_path=OUTPUT_VIDEO,
        title=METADATA["title"],
        description=METADATA["description"],
        tags=METADATA["tags"],
        video_type="long",
    )
    
    if upload_id:
        logger.info(f"🎉 Upload successful! Video ID: {upload_id}")
        logger.info(f"   URL: https://www.youtube.com/watch?v={upload_id}")
        
        # Save metadata
        meta_path = os.path.join(OUTPUT_DIR, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({**METADATA, "youtube_id": upload_id, "file_path": OUTPUT_VIDEO}, f, indent=2, ensure_ascii=False)
        
        return True
    else:
        logger.error("Upload failed!")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🌧️  FOREST RAIN 1-HOUR LOOP CREATOR & UPLOADER")
    print("=" * 60)
    
    # Step 1: Create the loop
    print("\n📹 Step 1: Creating 8-hour seamless loop...")
    if not create_seamless_loop():
        print("❌ Failed to create loop video!")
        sys.exit(1)
    
    # Step 2: Upload
    print("\n☁️  Step 2: Uploading to YouTube...")
    if not upload_to_youtube():
        print("❌ Upload failed!")
        sys.exit(1)
    
    print("\n✅ All done! Your 8-hour forest rain video is live on YouTube! 🌧️🌿")
