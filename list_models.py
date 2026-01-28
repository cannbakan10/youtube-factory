import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Listing available models...")
try:
    models = client.models.list()
    for m in models:
        print(f"Model ID: {m.name}")
except Exception as e:
    print(f"Error: {e}")
