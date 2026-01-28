import requests
import os
import uuid

class PixabayService:
    def __init__(self, output_dir=None):
        self.api_key = os.getenv("PIXABAY_API_KEY", "").strip()
        self.base_url = "https://pixabay.com/api/videos/"
        if output_dir:
            self.cache_dir = output_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_video(self, query):
        if not self.api_key:
            return None

        if isinstance(query, list):
            query = " ".join(query)

        params = {
            "key": self.api_key,
            "q": query,
            "video_type": "film",
            "per_page": 5,
            "safesearch": "true"
        }

        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()

            if data.get('hits'):
                # Pixabay doesn't have a direct 'orientation' filter in API as effective as Pexels
                # So we manually find vertical or high-res videos
                for hit in data['hits']:
                    videos = hit.get('videos', {})
                    # Priority order: large (usually 4K or high-res) -> medium -> small
                    # We prefer videos where height > width for Shorts
                    
                    best_video = videos.get('large') or videos.get('medium')
                    if not best_video or not best_video.get('url'):
                        continue

                    # Download logic
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
                    
                    print(f"      ✅ [Pixabay] Saved to: {filepath}")
                    return filepath
            else:
                print(f"      ⚠️ No Pixabay video found for: '{query}'")
        except Exception as e:
            print(f"      ❌ Pixabay API Error: {e}")
        
        return None
