import os
import sys
from src.services.youtube_service import YouTubeService
import json

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

def upload_existing():
    production_id = "Dünyanın_en_pahalı_5_çanta_mar_1769344994"
    video_path = f"{project_root}/assets/productions/{production_id}/tr/{production_id}_tr.mp4"
    meta_path = f"{project_root}/assets/productions/{production_id}/tr/metadata.json"
    
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        return

    with open(meta_path, "r") as f:
        meta = json.load(f)
    
    title = meta.get('title', "Lüks Çantalar")
    description = meta.get('description', "Lüks çantalar hakkında harika bilgiler #shorts")
    tags = meta.get('tags', ["shorts", "lüks"])
    
    yt = YouTubeService()
    yt.upload_video(video_path, title, description, tags)

if __name__ == "__main__":
    upload_existing()
