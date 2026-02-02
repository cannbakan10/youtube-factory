import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Available Models with Image capabilities:")
for m in client.models.list():
    if any(keyword in m.name.lower() for keyword in ["image", "imagen", "generate"]):
        print(f" - {m.name} | Methods: {m.supported_generation_methods}")
