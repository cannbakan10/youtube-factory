import os
import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("PIXABAY_API_KEY")
url = "https://pixabay.com/api/"

params = {
    "key": key,
    "q": "yellow flower",
    "per_page": 3
}

print(f"Testing Pixabay Main API for SFX...")
try:
    r = requests.get(url, params=params)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
