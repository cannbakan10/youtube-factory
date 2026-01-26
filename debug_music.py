from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv

def debug_music():
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    client = ElevenLabs(api_key=api_key)
    
    print("--- ElevenLabs Music Discovery ---")
    if hasattr(client, 'music'):
        music_client = client.music
        print(f"Music Client attributes: {[a for a in dir(music_client) if not a.startswith('_')]}")

if __name__ == "__main__":
    debug_music()
