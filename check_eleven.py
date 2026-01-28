import os
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

print("Client attributes:")
for attr in dir(client):
    if not attr.startswith("_"):
        print(f"- {attr}")
