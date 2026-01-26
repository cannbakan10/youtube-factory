import os
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

def list_all_available_voices():
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    client = ElevenLabs(api_key=api_key)

    print("� Hesabınızdaki tüm sesler listeleniyor...\n")
    
    voices = client.voices.get_all()
    for voice in voices.voices:
        print(f"👤 İsim: {voice.name}")
        print(f"🆔 ID: {voice.voice_id}")
        if voice.labels:
            print(f"🏷️ Etiketler: {voice.labels}")
        print("-" * 30)

if __name__ == "__main__":
    list_all_available_voices()
