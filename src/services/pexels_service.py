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

    def get_video(self, query, orientation="portrait"):
        # Handle list of keywords if necessary
        if isinstance(query, list):
            query = " ".join(query)
            
        # Quality & Context Refinement
        # Appending cinematic/high-quality keywords to push for better stock choice
        refined_query = f"{query} cinematic high quality professional"
        
        # Topic-specific steering (Safety Filter)
        sensitive_keywords = ["dua", "pray", "religious", "mosque", "islam", "church", "god"]
        if any(sk in query.lower() for sk in sensitive_keywords):
            refined_query += " architecture nature peaceful"

        if not self.api_key:
            print("[!] Pexels API Key not found. Skipping video download.")
            return None

        headers = {"Authorization": self.api_key}
        params = {"query": refined_query, "per_page": 1, "orientation": orientation}
        
        try:
            response = requests.get(self.base_url, headers=headers, params=params)
            data = response.json()
            
            if data.get('videos'):
                video_files = data['videos'][0]['video_files']
                
                # Priority: 4K (Ultra HD) -> Full HD -> HD
                # We look for 'width' >= 2160 for 4K
                video_url = None
                
                # Sort by width descending to get best quality
                sorted_files = sorted(video_files, key=lambda x: x.get('width', 0) or 0, reverse=True)
                if sorted_files:
                    video_url = sorted_files[0]['link']
                    quality = f"{sorted_files[0].get('width')}x{sorted_files[0].get('height')}"
                
                if not video_url:
                    return None

                filename = f"{uuid.uuid4()}.mp4"
                filepath = os.path.join(self.cache_dir, filename)
                
                print(f"      📥 Downloading clip ({quality}): {video_url[:50]}...")
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
