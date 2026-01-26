import requests
import os
import uuid

class PexelsService:
    def __init__(self, output_dir=None):
        self.api_key = os.getenv("PEXELS_API_KEY", "").strip()
        self.base_url = "https://api.pexels.com/v1/videos/search"
        if output_dir:
            self.cache_dir = output_dir
        else:
            # Fallback to project-relative path
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_video(self, query):
        # Handle list of keywords if necessary
        if isinstance(query, list):
            query = " ".join(query)

        if not self.api_key:
            print("[!] Pexels API Key not found. Skipping video download.")
            return None

        headers = {"Authorization": self.api_key}
        params = {"query": query, "per_page": 1, "orientation": "portrait"}
        
        try:
            response = requests.get(self.base_url, headers=headers, params=params)
            data = response.json()
            
            if data.get('videos'):
                video_url = data['videos'][0]['video_files'][0]['link']
                filename = f"{uuid.uuid4()}.mp4"
                filepath = os.path.join(self.cache_dir, filename)
                
                print(f"      📥 Downloading clip: {video_url[:50]}...")
                # Download the video
                with requests.get(video_url, stream=True) as r:
                    r.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                print(f"      ✅ Saved to: {filepath}")
                return filepath
            else:
                print(f"      ⚠️ No stock video found for: '{query}'")
        except Exception as e:
            print(f"      ❌ Pexels API Error: {e}")
        
        return None
