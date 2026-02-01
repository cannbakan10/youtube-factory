import requests
import os
import uuid

class PixabayService:
    def __init__(self, output_dir=None):
        # Ultra-Clean Key Loading
        raw_key = os.getenv("PIXABAY_API_KEY", "")
        self.api_key = raw_key.strip().replace('"', '').replace("'", "")
        self.video_url = "https://pixabay.com/api/videos/"
        self.music_url = "https://pixabay.com/api/music/" # For SFX and Background Music
        
        if output_dir:
            self.cache_dir = output_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_video(self, query, orientation="portrait"):
        """Fetches a video from Pixabay with smart retries and generic fallbacks."""
        if not self.api_key:
            return None

        keywords = query if isinstance(query, list) else query.split()
        search_attempts = [
            " ".join(keywords), # Attempt 1: Full query
            keywords[0] if keywords else "cinematic", # Attempt 2: Primary keyword
            "nature cinematic", # Attempt 3: Genre fallback
            "technology drone" # Attempt 4: Safety fallback
        ]

        for attempt in search_attempts:
            # Refine query based on orientation
            refined_query = attempt
            if orientation == "portrait":
                refined_query += " vertical"
            else:
                refined_query += " landscape"

            params = {
                "key": self.api_key,
                "q": refined_query,
                "video_type": "film",
                "per_page": 10,
                "safesearch": "true"
            }

            try:
                response = requests.get(self.video_url, params=params)
                if response.status_code != 200:
                    print(f"      ⚠️ Pixabay API Error (Status {response.status_code}): {response.text[:100]}")
                    continue
                data = response.json()

                if data.get('hits'):
                    import random
                    hit = random.choice(data['hits'])
                    videos = hit.get('videos', {})
                    best_video = videos.get('large') or videos.get('medium')
                    if not best_video or not best_video.get('url'):
                        continue

                    video_url = best_video['url']
                    quality = f"{best_video.get('width')}x{best_video.get('height')}"
                    
                    filename = f"pixabay_{uuid.uuid4()}.mp4"
                    filepath = os.path.join(self.cache_dir, filename)
                    
                    print(f"      📥 [Pixabay] Downloading clip ({quality}): {video_url[:50]}...")
                    with requests.get(video_url, stream=True) as r:
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    return filepath
            except Exception as e:
                print(f"      ⚠️ Pixabay Attempt Failed ({attempt}): {e}")
        
        return None

    def get_audio(self, query, category="music"):
        """Downloads royalty-free music or SFX from Pixabay API."""
        if not self.api_key:
            return None
            
        params = {
            "key": self.api_key,
            "q": query,
            "per_page": 20,
            "safesearch": "true"
        }
        
        try:
            response = requests.get(self.music_url, params=params)
            data = response.json()
            
            if data.get('hits'):
                import random
                hit = random.choice(data['hits'])
                audio_url = hit.get('download_url') or hit.get('audio')
                
                if audio_url:
                    filename = f"{category}_{uuid.uuid4()}.mp3"
                    filepath = os.path.join(self.cache_dir, filename)
                    
                    with requests.get(audio_url, stream=True) as r:
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    
                    return filepath
        except Exception as e:
            print(f"      ❌ Pixabay Audio Error: {e}")
            
        return None
