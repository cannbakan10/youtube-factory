import os
import requests
import uuid
from dotenv import load_dotenv

def download_bg_music():
    load_dotenv()
    api_key = os.getenv("PIXABAY_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not api_key:
        print("❌ PIXABAY_API_KEY not found!")
        return

    music_url = "https://pixabay.com/api/music/"
    output_dir = "/Users/sergenbakan/Youtuber/youtube-factory/assets/templates/music"
    os.makedirs(output_dir, exist_ok=True)

    # Search terms for variety
    queries = [
        "cinematic tension", "mystery documentary", "epic trailer", 
        "educational upbeat", "lofi chill", "dark atmospheric", 
        "techno futuristic", "inspiring background", "suspenseful", "nature peaceful"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    downloaded = 0
    for query in queries:
        params = {
            "key": api_key,
            "q": query,
            "per_page": 10,
            "safesearch": "true"
        }
        
        try:
            print(f"🔍 Searching for: {query}...")
            response = requests.get(music_url, params=params, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Pixabay API Error ({response.status_code}): {response.text[:100]}")
                continue
                
            data = response.json()
            
            if data.get('hits'):
                import random
                hit = random.choice(data['hits'])
                # Some hits use 'audio' field, some use 'download_url'
                audio_url = hit.get('audio') or hit.get('download_url')
                
                if audio_url:
                    filename = f"bgm_{downloaded+1}.mp3"
                    filepath = os.path.join(output_dir, filename)
                    
                    print(f"📥 Downloading: {hit.get('tags', query)[:50]}...")
                    with requests.get(audio_url, stream=True, headers=headers) as r:
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    
                    print(f"✅ Saved to: {filepath}")
                    downloaded += 1
            else:
                print(f"⚠️ No results for: {query}")
        except Exception as e:
            print(f"❌ Error processing {query}: {e}")

    print(f"\n🏁 Finished! Downloaded {downloaded} tracks to {output_dir}")

if __name__ == "__main__":
    download_bg_music()
