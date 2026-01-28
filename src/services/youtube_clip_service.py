import os
import subprocess
import uuid
import yt_dlp
import logging

class YoutubeClipService:
    def __init__(self, cache_dir=None):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.cache_dir = cache_dir or os.path.join(self.project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_clip(self, query, duration=5):
        """
        Searches YouTube for a query and downloads a short clip.
        Uses yt-dlp to find the most relevant video and extract a segment.
        """
        clip_id = str(uuid.uuid4())
        output_path = os.path.join(self.cache_dir, f"yt_{clip_id}.mp4")
        
        print(f"      🎞️  [YouTube Search]: '{query}'...")
        
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',
            'max_filesize': 50 * 1024 * 1024, # Limit to 50MB
            # We want short clips, so we prefer videos that are already short
            'match_filter': yt_dlp.utils.match_filter_func('duration < 300'), # Max 5 mins
            'download_sections': f'[{{"start_time": 0, "end_time": {duration}}}]',
            'force_keyframes_at_cuts': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([query])
            
            if os.path.exists(output_path):
                # Verify size (sometimes it fails but file exists)
                if os.path.getsize(output_path) > 0:
                    return output_path
        except Exception as e:
            print(f"      ❌ YouTube Clip Error for '{query}': {e}")
            
        return None
