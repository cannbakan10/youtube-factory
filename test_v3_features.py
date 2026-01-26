import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.tts_service import TTSService

def test_v3_tts():
    load_dotenv()
    tts = TTSService(output_dir="test_cache")
    text = "Kara delikler, uzayın en gizemli ve korkunç canavarlarıdır."
    
    print("🚀 Testing ElevenLabs V3 (Hyper-Sync + SFX)...")
    
    # 1. Test Audio + Word Sync
    audio, subs, dur = tts.generate_audio_with_subtitles(text)
    if audio and os.path.exists(audio):
        print(f"✅ Hyper-Sync Audio: {audio} ({dur}s)")
        print(f"✅ Hyper-Sync Subs: {subs}")
        with open(subs, "r") as f:
            print("--- Subtitle Snippet ---")
            print("".join(f.readlines()[:10]))
    else:
        print("❌ Hyper-Sync Failed.")

    # 2. Test SFX
    sfx_prompt = "deep cinematic impact thud"
    sfx = tts.generate_sfx(sfx_prompt, duration_seconds=2)
    if sfx and os.path.exists(sfx):
        print(f"✅ SFX Generated: {sfx}")
    else:
        print("❌ SFX Failed.")

if __name__ == "__main__":
    test_v3_tts()
