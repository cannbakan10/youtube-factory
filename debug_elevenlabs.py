from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv

def debug_elevenlabs():
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    client = ElevenLabs(api_key=api_key)
    
    print("--- ElevenLabs Client Discovery ---")
    print(f"Client attributes: {[a for a in dir(client) if not a.startswith('_')]}")
    
    # Test convert_with_timestamps
    try:
        response = client.text_to_speech.convert_with_timestamps(
            voice_id="IuRRIAcbQK5AQk1XevPj",
            text="Test",
            model_id="eleven_multilingual_v2"
        )
        print(f"\n--- Response Type: {type(response)} ---")
        print(f"Response attributes: {[a for a in dir(response) if not a.startswith('_')]}")
    except Exception as e:
        print(f"Error testing timestamps: {e}")

if __name__ == "__main__":
    debug_elevenlabs()
