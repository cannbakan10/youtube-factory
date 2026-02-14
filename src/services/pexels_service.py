import requests
import os
import uuid
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters

logger = get_logger(__name__)

# Constants
REQUEST_TIMEOUT = 30  # seconds
DOWNLOAD_TIMEOUT = 120  # seconds for video downloads


class PexelsService:
    def __init__(self, output_dir=None):
        # Ultra-Clean Key Loading
        raw_key = os.getenv("PEXELS_API_KEY", "")
        self.api_key = raw_key.strip().replace('"', '').replace("'", "")
        self.base_url = "https://api.pexels.com/v1/videos/search"
        self.image_url = "https://api.pexels.com/v1/search"
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
            logger.warning("Pexels API key not configured")
            return None

        keywords = query if isinstance(query, list) else query.split()
        if not keywords:
            keywords = ["cinematic"]

        # Truncate individual keywords that are too long (AI-generated sentences)
        keywords = [kw[:50] for kw in keywords]

        # Smart Progressive Search: Try specific first, then relax slightly, but NEVER go generic
        search_attempts = [
            " ".join(keywords[:5]),  # First 5 keywords (avoid mega-long queries)
            " ".join(keywords[:3]),  # First 3 keywords (Contextual core)
            keywords[0] + " " + keywords[-1] if len(keywords) > 1 else keywords[0],  # Bookends
            keywords[0]  # Primary subject only
        ]

        # Clean up queries
        cleaned = []
        for a in search_attempts:
            a = a.replace(",", "").replace(".", "").replace("(", "").replace(")", "").strip()[:100]
            if a and a not in cleaned:
                cleaned.append(a)
        search_attempts = cleaned

        for attempt in search_attempts:
            try:
                result = self._search_and_download(attempt, orientation)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Pexels attempt failed ({attempt[:40]}): {e}")

        logger.error(f"All Pexels search attempts failed for: {keywords[:3]}")
        return None

    def get_image(self, query, orientation="landscape"):
        """Fetches an image from Pexels with smart retries."""
        if not self.api_key:
            logger.warning("Pexels API key not configured")
            return None

        keywords = query if isinstance(query, list) else query.split()
        search_query = " ".join(keywords) if keywords else "cinematic"

        try:
            APIRateLimiters.pexels.wait()
            headers = {"Authorization": self.api_key}
            params = {"query": search_query, "per_page": 1, "orientation": orientation}
            response = requests.get(self.image_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if data.get('photos'):
                photo = data['photos'][0]
                image_url = photo['src']['large2x']
                filename = f"pexels_img_{uuid.uuid4()}.jpg"
                filepath = os.path.join(self.cache_dir, filename)
                self._download_file(image_url, filepath)
                return filepath
        except Exception as e:
            logger.warning(f"Pexels image fetch failed: {e}")
        return None

    def get_multiple_videos(self, query, count=5, orientation="portrait"):
        """Fetches multiple videos from Pexels for better variety in long productions."""
        if not self.api_key:
            return []

        keywords = query if isinstance(query, list) else query.split()
        search_query = " ".join(keywords) if keywords else "cinematic"
        
        headers = {"Authorization": self.api_key}
        params = {"query": search_query, "per_page": 20, "orientation": orientation}

        try:
            APIRateLimiters.pexels.wait()
            response = requests.get(self.base_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            videos_list = data.get('videos', [])
            if not videos_list:
                return []

            import random
            random.shuffle(videos_list)
            
            downloaded_paths = []
            for video_data in videos_list[:count]:
                video_files = video_data.get('video_files', [])
                if not video_files: continue
                
                sorted_files = sorted(video_files, key=lambda x: x.get('width', 0) or 0, reverse=True)
                video_url = sorted_files[0]['link']
                
                filename = f"pexels_{uuid.uuid4()}.mp4"
                filepath = os.path.join(self.cache_dir, filename)
                
                try:
                    self._download_file(video_url, filepath)
                    downloaded_paths.append(filepath)
                except Exception as de:
                    logger.warning(f"Failed to download multi-clip from Pexels: {de}")
                    
            return downloaded_paths

        except Exception as e:
            logger.warning(f"Pexels multi-fetch failed: {e}")
            return []

    @retry_with_backoff(max_retries=2, base_delay=2.0, exceptions=(requests.RequestException,))
    def _search_and_download(self, query, orientation):
        """Search and download with retry support."""
        # Rate limiting
        APIRateLimiters.pexels.wait()

        headers = {"Authorization": self.api_key}
        params = {"query": query, "per_page": 15, "orientation": orientation}

        response = requests.get(
            self.base_url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        if data.get('hits') or data.get('videos'):
            import random
            videos_list = data.get('videos') or data.get('hits')
            video_data = random.choice(videos_list)
            video_files = video_data.get('video_files') or [video_data.get('video_files')]

            # Sort by width descending to get best quality
            sorted_files = sorted(video_files, key=lambda x: x.get('width', 0) or 0, reverse=True)
            if not sorted_files:
                return None

            video_url = sorted_files[0]['link']
            quality = f"{sorted_files[0].get('width') or '?'}x{sorted_files[0].get('height') or '?'}"

            filename = f"{uuid.uuid4()}.mp4"
            filepath = os.path.join(self.cache_dir, filename)

            logger.info(f"Downloading clip ({quality}): {video_url[:50]}...")
            self._download_file(video_url, filepath)
            return filepath

        return None

    @retry_with_backoff(max_retries=2, base_delay=1.0, exceptions=(requests.RequestException,))
    def _download_file(self, url, filepath):
        """Download file with retry support."""
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
