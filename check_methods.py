import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    # Try alternate name if common
    api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key)
print("Methods in client.models:")
for method in dir(client.models):
    if not method.startswith("_"):
        print(f" - {method}")
