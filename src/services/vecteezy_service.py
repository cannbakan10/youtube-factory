"""
Vecteezy Service - Free stock video downloads.
Scrapes vecteezy.com search results and downloads free videos.
Uses VECTEEZY_API_KEY if available, otherwise falls back to web scraping.
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


class VecteezyService:
    """Downloads free stock videos from Vecteezy.com."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.cache_dir = output_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.api_key = os.getenv("VECTEEZY_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def get_video(self, query: str) -> Optional[str]:
        """Search and download a single free video. Returns local path or None."""
        video_urls = self._search_video_urls(query)
        if not video_urls:
            return None
        url = random.choice(video_urls[:5])
        return self._download_video(url)

    def get_multiple_videos(self, queries: List[str], count: int = 5) -> List[str]:
        """Search multiple queries and download unique videos."""
        all_urls = []
        seen = set()

        for query in queries:
            urls = self._search_video_urls(query)
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    all_urls.append(url)

        if not all_urls:
            return []

        random.shuffle(all_urls)
        selected = all_urls[:count]

        downloaded = []
        for url in selected:
            path = self._download_video(url)
            if path:
                downloaded.append(path)

        logger.info(f"Vecteezy: Downloaded {len(downloaded)}/{count} videos")
        return downloaded

    def _search_video_urls(self, query: str) -> List[str]:
        """
        Search Vecteezy for free videos and extract download/preview URLs.
        """
        clean_query = query.strip().replace(' ', '+')
        search_url = f"https://www.vecteezy.com/free-videos/{clean_query}"

        try:
            response = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                logger.warning(f"Vecteezy search returned {response.status_code}: {search_url}")
                return []

            html = response.text

            # Extract video preview/download URLs from the HTML
            # Vecteezy uses various CDN patterns for video previews
            video_urls = []

            # Pattern 1: Direct video source URLs
            mp4_urls = re.findall(r'(https://(?:static|cdn)[^"]*\.vecteezy\.com/[^"]*\.mp4)', html)
            video_urls.extend(mp4_urls)

            # Pattern 2: Video preview URLs in data attributes
            preview_urls = re.findall(r'data-(?:src|video|preview)="(https://[^"]*\.mp4[^"]*)"', html)
            video_urls.extend(preview_urls)

            # Pattern 3: Any .mp4 links from vecteezy CDN
            all_mp4 = re.findall(r'(https://[a-z]+\.vecteezy\.com/[^"\']*\.mp4)', html)
            video_urls.extend(all_mp4)

            # Deduplicate
            unique_urls = list(dict.fromkeys(video_urls))
            logger.info(f"Vecteezy search '{query}': {len(unique_urls)} video URLs found")
            return unique_urls

        except Exception as e:
            logger.warning(f"Vecteezy search error for '{query}': {e}")
            return []

    def _download_video(self, url: str) -> Optional[str]:
        """Download a video from URL to cache directory."""
        filepath = os.path.join(self.cache_dir, f"vecteezy_{uuid.uuid4().hex[:8]}.mp4")

        try:
            response = self.session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
            if response.status_code != 200:
                logger.warning(f"Vecteezy download failed ({response.status_code}): {url[:60]}")
                return None

            content_length = int(response.headers.get('content-length', 0))
            if content_length < 100_000:  # Less than 100KB = not a video
                return None

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)

            file_size = os.path.getsize(filepath)
            if file_size < 100_000:
                os.remove(filepath)
                return None

            logger.info(f"Vecteezy: {file_size / 1_000_000:.1f}MB → {filepath}")
            return filepath

        except Exception as e:
            logger.warning(f"Vecteezy download error: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
