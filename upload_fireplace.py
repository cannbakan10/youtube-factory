"""
Auto-Retry Upload Script — Keeps trying until YouTube quota resets
Quota resets at midnight Pacific Time (08:00 UTC = 11:00 Turkey)
"""
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.youtube_service import YouTubeService

VIDEO_PATH = "assets/productions/loop_8h_1771021489/en/loop_8h_1771021489.mp4"

TITLE = "🔥 8 Hours Cozy Fireplace Ambience | Crackling Fire Sounds for Sleep, Study & Relaxation"

DESCRIPTION = """🔥 8 Hours of Cozy Fireplace Ambience with Crackling Fire Sounds

Enjoy this ultra-relaxing fireplace video with the soothing sound of crackling logs. Perfect for creating a warm, cozy atmosphere in your home.

✨ Perfect for:
🛏️ Deep Sleep & Insomnia Relief
📚 Studying & Homework Focus
🧘 Meditation & Yoga
💻 Work From Home Background
🎄 Cozy Winter Nights
👶 Baby Sleep Aid
🐱 Pet Relaxation

⏱️ Duration: 8 Hours (No interruptions, no ads mid-roll)
🎧 Audio: Natural crackling fire sounds
📺 Video: Seamless looping fireplace

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔔 Subscribe for more ambient content!
👍 Like this video if it helps you relax!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#fireplace #ambience #sleep #relax #study #cozy #crackling #fire #8hours #sleepsounds #relaxation #whitenoise #ASMR #ambient #focus
"""

TAGS = [
    "fireplace", "fireplace ambience", "crackling fire",
    "8 hours fireplace", "fireplace for sleep", "sleep sounds",
    "study music", "relaxation", "cozy fireplace", "fire sounds",
    "ambient sounds", "fireplace ASMR", "cozy ambience",
    "winter fireplace", "relaxing fire", "white noise",
    "deep sleep", "focus music", "meditation",
    "fireplace 8 hours", "crackling fire sounds", "cozy fire",
    "sleep aid", "background noise", "fireplace loop",
]

MAX_RETRIES = 12  # Try every 30 min for 6 hours
RETRY_INTERVAL = 1800  # 30 minutes

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def main():
    log("=" * 60)
    log("📤 AUTO-RETRY UPLOAD — Fireplace 8H")
    log(f"   Will retry every 30 min until quota resets")
    log(f"   Quota resets ~08:00 UTC (11:00 Turkey)")
    log("=" * 60)

    if not os.path.exists(VIDEO_PATH):
        log(f"❌ Video not found: {VIDEO_PATH}")
        sys.exit(1)

    size_gb = os.path.getsize(VIDEO_PATH) / (1024**3)
    log(f"📦 File: {size_gb:.2f} GB")

    for attempt in range(1, MAX_RETRIES + 1):
        log(f"\n🔄 Attempt {attempt}/{MAX_RETRIES}")

        try:
            yt = YouTubeService()
            if not yt.youtube:
                log("❌ YouTube auth failed")
                time.sleep(RETRY_INTERVAL)
                continue

            video_id = yt.upload_video(
                file_path=VIDEO_PATH,
                title=TITLE,
                description=DESCRIPTION,
                tags=TAGS,
                video_type="long",
            )

            if video_id:
                log(f"\n{'='*60}")
                log(f"✅ UPLOAD SUCCESSFUL!")
                log(f"🔗 https://youtube.com/watch?v={video_id}")
                log(f"{'='*60}")
                sys.exit(0)
            else:
                log(f"⚠️ Upload returned None (likely quota). Waiting 30 min...")

        except Exception as e:
            log(f"⚠️ Error: {e}")
            log(f"Waiting 30 min before retry...")

        if attempt < MAX_RETRIES:
            next_try = datetime.now().timestamp() + RETRY_INTERVAL
            next_try_str = datetime.fromtimestamp(next_try).strftime('%H:%M')
            log(f"⏰ Next attempt at {next_try_str}")
            time.sleep(RETRY_INTERVAL)

    log("❌ All retries exhausted. Upload manually tomorrow.")

if __name__ == "__main__":
    main()
