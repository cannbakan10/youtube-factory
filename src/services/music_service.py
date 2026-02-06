import requests
import os
import random

class MusicService:
    def __init__(self):
        self.api_key = os.getenv("PEXELS_API_KEY")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY") 
        self.base_url = "https://pixabay.com/api/videos/"
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def get_background_music(self, mood="uplifting energetic"):
        print(f"      🎵 Searching for background music ({mood})...")
        music_dir = os.path.join(self.project_root, "assets", "templates", "music")
        if os.path.exists(music_dir):
            tracks = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
            if tracks:
                return os.path.join(music_dir, random.choice(tracks))

        fallback = os.path.join(self.project_root, "assets", "templates", "bg_music.mp3")
        if os.path.exists(fallback):
            return fallback
        return None
