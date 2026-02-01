import requests
import os
import uuid

class PexelsService:
    def __init__(self, output_dir=None):
        # Ultra-Clean Key Loading
        raw_key = os.getenv("PEXELS_API_KEY", "")
        self.api_key = raw_key.strip().replace('"', '').replace("'", "")
        self.base_url = "https://api.pexels.com/v1/videos/search"
        if output_dir:
            self.cache_dir = output_dir
        else:
            # Fallback to project-relative path
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_video(self, query, orientation="portrait"):
        """Fetches a video from Pexels with smart retries and generic fallbacks."""
        if not self.api_key:
            return None

        keywords = query if isinstance(query, list) else query.split()
        search_attempts = [
            " ".join(keywords), # Attempt 1: Full query
            keywords[0] if keywords else "cinematic", # Attempt 2: Primary keyword
            "cinematic background", # Attempt 3: Genre fallback
            "abstract cinematic" # Attempt 4: Ultimate safety fallback
        ]

        for attempt in search_attempts:
            # Quality & Context Refinement
            refined_query = f"{attempt} cinematic high quality"
            
            headers = {"Authorization": self.api_key}
            params = {"query": refined_query, "per_page": 15, "orientation": orientation}
            
            try:
                response = requests.get(self.base_url, headers=headers, params=params)
                data = response.json()
                
                if data.get('hits') or data.get('videos'):
                    import random
                    videos_list = data.get('videos') or data.get('hits')
                    video_data = random.choice(videos_list)
                    video_files = video_data.get('video_files') or [video_data.get('video_files')]
                    
                    # Sort by width descending to get best quality
                    sorted_files = sorted(video_files, key=lambda x: x.get('width', 0) or 0, reverse=True)
                    if not sorted_files: continue
                    
                    video_url = sorted_files[0]['link']
                    quality = f"{sorted_files[0].get('width') or '?' }x{sorted_files[0].get('height') or '?'}"

                    filename = f"{uuid.uuid4()}.mp4"
                    filepath = os.path.join(self.cache_dir, filename)
                    
                    print(f"      📥 Downloading clip ({quality}): {video_url[:50]}...")
                    with requests.get(video_url, stream=True) as r:
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    return filepath
            except Exception as e:
                print(f"      ⚠️ Pexels Attempt Failed ({attempt}): {e}")
        
        return None
