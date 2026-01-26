from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv

def debug_sfx():
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    client = ElevenLabs(api_key=api_key)
    
    print("--- ElevenLabs SFX Discovery ---")
    if hasattr(client, 'text_to_sound_effects'):
        sfx_client = client.text_to_sound_effects
        print(f"SFX Client attributes: {[a for a in dir(sfx_client) if not a.startswith('_')]}")

if __name__ == "__main__":
    debug_sfx()
