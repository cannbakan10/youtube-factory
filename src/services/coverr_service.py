"""
Coverr Service - Free stock video downloads via Coverr API.
Requires COVERR_API_KEY environment variable (get free key from team@coverr.co).
Falls back gracefully if key is not set.
"""
import os
import uuid
import random
import requests
from typing import Optional, List
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.coverr.co"
REQUEST_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 120


class CoverrService:
    """Searches and downloads free stock videos from Coverr.co."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.cache_dir = output_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.api_key = os.getenv("COVERR_API_KEY", "")
        if not self.api_key:
            logger.warning("COVERR_API_KEY not set. Coverr service will be disabled.")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
        })

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def get_video(self, query: str) -> Optional[str]:
        """Search and download a single video. Returns local path or None."""
        if not self.available:
            return None

        videos = self._search(query)
        if not videos:
            return None

        video = random.choice(videos[:5])
        return self._download_video(video)

    def get_multiple_videos(self, queries: List[str], count: int = 5) -> List[str]:
        """Search multiple queries and download unique videos."""
        if not self.available:
            return []

        all_videos = []
        seen_ids = set()

        for query in queries:
            results = self._search(query)
            for v in results:
                vid = v.get("id") or v.get("base_filename", "")
                if vid not in seen_ids:
                    seen_ids.add(vid)
                    all_videos.append(v)

        random.shuffle(all_videos)
        downloaded = []
        for video in all_videos[:count]:
            path = self._download_video(video)
            if path:
                downloaded.append(path)

        logger.info(f"Coverr: Downloaded {len(downloaded)}/{count} videos")
        return downloaded

    def _search(self, query: str) -> List[dict]:
        """Search Coverr API for videos."""
        try:
            url = f"{BASE_URL}/videos"
            params = {"query": query}
            resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                logger.warning(f"Coverr search failed ({resp.status_code})")
                return []
            data = resp.json()
            # API returns a list of video objects
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("hits", data.get("videos", []))
            return []
        except Exception as e:
            logger.warning(f"Coverr search error: {e}")
            return []

    def _download_video(self, video: dict) -> Optional[str]:
        """Download a Coverr video using the storage endpoint."""
        base_filename = video.get("base_filename", "")
        if not base_filename:
            return None

        try:
            # Get signed download URL
            url = f"{BASE_URL}/storage/videos/{base_filename}"
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None

            download_url = resp.text.strip().strip('"')
            if not download_url.startswith("http"):
                return None

            # Download the file
            filepath = os.path.join(self.cache_dir, f"coverr_{uuid.uuid4()}.mp4")
            resp = self.session.get(download_url, stream=True, timeout=DOWNLOAD_TIMEOUT)
            if resp.status_code != 200:
                return None

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(filepath)
            if file_size < 50_000:
                os.remove(filepath)
                return None

            logger.info(f"Coverr: Downloaded {file_size / 1_000_000:.1f}MB → {filepath}")
            return filepath

        except Exception as e:
            logger.warning(f"Coverr download error: {e}")
            return None
