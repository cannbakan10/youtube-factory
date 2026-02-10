"""
Mixkit Service - Free stock video downloads (no API key needed).
Scrapes mixkit.co search pages, extracts video IDs from 360p previews,
and downloads 720p (HD Ready) versions.
"""
import os
import re
import uuid
import random
import requests
from typing import Optional, List
from src.utils.logger import get_logger

logger = get_logger(__name__)

REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 180
VIDEO_CDN = "https://assets.mixkit.co/videos"


class MixkitService:
    """Downloads free stock videos from Mixkit.co (no API key required)."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.cache_dir = output_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def get_video(self, query: str) -> Optional[str]:
        """Search Mixkit for a free video, download 720p version. Returns local path or None."""
        video_ids = self._search_video_ids(query)
        if not video_ids:
            return None
        vid_id = random.choice(video_ids[:5])
        return self._download_by_id(vid_id)

    def get_multiple_videos(self, queries: List[str], count: int = 5) -> List[str]:
        """Search multiple queries and download unique 720p videos."""
        all_ids = []
        seen = set()

        for query in queries:
            ids = self._search_video_ids(query)
            for vid_id in ids:
                if vid_id not in seen:
                    seen.add(vid_id)
                    all_ids.append(vid_id)

        if not all_ids:
            return []

        random.shuffle(all_ids)
        selected = all_ids[:count]

        downloaded = []
        for vid_id in selected:
            path = self._download_by_id(vid_id)
            if path:
                downloaded.append(path)

        logger.info(f"Mixkit: Downloaded {len(downloaded)}/{count} videos")
        return downloaded

    def _search_video_ids(self, query: str) -> List[str]:
        """
        Search Mixkit and extract video IDs from 360p preview src tags.
        Pattern: src="https://assets.mixkit.co/videos/XXXXX/XXXXX-360.mp4"
        """
        clean_query = query.lower().strip()
        clean_query = re.sub(r'[^a-z0-9\s-]', '', clean_query)
        clean_query = clean_query.replace(' ', '-')

        search_url = f"https://mixkit.co/free-stock-video/{clean_query}/"

        try:
            response = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                logger.warning(f"Mixkit search returned {response.status_code}: {search_url}")
                return []

            html = response.text

            # Extract video IDs from 360p preview sources
            # Pattern: https://assets.mixkit.co/videos/33705/33705-360.mp4
            video_ids = re.findall(r'assets\.mixkit\.co/videos/(\d+)/\d+-360\.mp4', html)

            # Deduplicate while preserving order
            unique_ids = list(dict.fromkeys(video_ids))
            logger.info(f"Mixkit search '{query}': {len(unique_ids)} videos found")
            return unique_ids

        except Exception as e:
            logger.warning(f"Mixkit search error for '{query}': {e}")
            return []

    def _download_by_id(self, vid_id: str) -> Optional[str]:
        """Download a Mixkit video by ID in 720p (falls back to 360p)."""
        # Try 720p first (HD Ready)
        url_720 = f"{VIDEO_CDN}/{vid_id}/{vid_id}-720.mp4"
        path = self._download_file(url_720, vid_id)
        if path:
            return path

        # Fallback to 360p
        url_360 = f"{VIDEO_CDN}/{vid_id}/{vid_id}-360.mp4"
        return self._download_file(url_360, vid_id)

    def _download_file(self, url: str, vid_id: str) -> Optional[str]:
        """Download a file from URL to cache directory."""
        filepath = os.path.join(self.cache_dir, f"mixkit_{vid_id}_{uuid.uuid4().hex[:6]}.mp4")

        try:
            response = self.session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
            if response.status_code != 200:
                return None

            content_length = int(response.headers.get('content-length', 0))
            if content_length < 100_000:  # Less than 100KB = probably not a real video
                return None

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)

            file_size = os.path.getsize(filepath)
            logger.info(f"Mixkit #{vid_id}: {file_size / 1_000_000:.1f}MB → {filepath}")
            return filepath

        except Exception as e:
            logger.warning(f"Mixkit download error for #{vid_id}: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
