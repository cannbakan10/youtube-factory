import requests
import os
import uuid
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters

logger = get_logger(__name__)

# Constants
REQUEST_TIMEOUT = 30  # seconds
DOWNLOAD_TIMEOUT = 120  # seconds for video downloads


class PixabayService:
    def __init__(self, output_dir=None):
        # Ultra-Clean Key Loading
        raw_key = os.getenv("PIXABAY_API_KEY", "")
        self.api_key = raw_key.strip().replace('"', '').replace("'", "")
        self.video_url = "https://pixabay.com/api/videos/"
        self.music_url = "https://pixabay.com/api/music/"  # For SFX and Background Music

        if output_dir:
            self.cache_dir = output_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(project_root, "assets", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_video(self, query, orientation="portrait"):
        """Fetches a video from Pixabay with smart retries and generic fallbacks."""
        if not self.api_key:
            logger.warning("Pixabay API key not configured")
            return None

        keywords = query if isinstance(query, list) else query.split()
        if not keywords:
            keywords = ["cinematic"]

        # Smart Progressive Search: Focus on context, avoid random nature/tech fallbacks
        search_attempts = [
            " ".join(keywords),  # Full specific query
            " ".join(keywords[:3]),  # Contextual core
            keywords[0]  # Subject only
        ]

        # Remove any leading/trailing commas or dots that AI might add
        search_attempts = [a.replace(",", "").replace(".", "").strip() for a in search_attempts]

        for attempt in search_attempts:
            try:
                result = self._search_and_download_video(attempt, orientation)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Pixabay attempt failed ({attempt}): {e}")

        logger.error(f"All Pixabay search attempts failed for: {keywords}")
        return None

    def get_multiple_videos(self, query, count=5, orientation="portrait"):
        """Fetches multiple videos from Pixabay."""
        if not self.api_key:
            return []

        keywords = query if isinstance(query, list) else query.split()
        search_query = " ".join(keywords) if keywords else "cinematic"
        if orientation == "portrait":
            search_query += " vertical"
        else:
            search_query += " landscape"

        params = {
            "key": self.api_key,
            "q": search_query[:95],
            "video_type": "film",
            "per_page": 20,
            "safesearch": "true"
        }

        try:
            APIRateLimiters.pixabay.wait()
            response = requests.get(self.video_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get('hits', [])
            if not hits:
                return []

            import random
            random.shuffle(hits)
            
            downloaded_paths = []
            for hit in hits[:count]:
                videos = hit.get('videos', {})
                best_video = videos.get('large') or videos.get('medium')
                if not best_video or not best_video.get('url'): continue
                
                video_url = best_video['url']
                filename = f"pixabay_{uuid.uuid4()}.mp4"
                filepath = os.path.join(self.cache_dir, filename)
                
                try:
                    self._download_file(video_url, filepath)
                    downloaded_paths.append(filepath)
                except Exception as de:
                    logger.warning(f"Failed to download multi-clip from Pixabay: {de}")
                    
            return downloaded_paths

        except Exception as e:
            logger.warning(f"Pixabay multi-fetch failed: {e}")
            return []

    @retry_with_backoff(max_retries=2, base_delay=2.0, exceptions=(requests.RequestException,))
    def _search_and_download_video(self, query, orientation):
        """Search and download video with retry support."""
        # Rate limiting
        APIRateLimiters.pixabay.wait()

        # Refine query based on orientation
        refined_query = query[:95]  # Pixabay limit is 100 characters
        if orientation == "portrait":
            refined_query += " vertical"
        else:
            refined_query += " landscape"

        params = {
            "key": self.api_key,
            "q": refined_query,
            "video_type": "film",
            "per_page": 10,
            "safesearch": "true"
        }

        response = requests.get(self.video_url, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            logger.warning(f"Pixabay API Error (Status {response.status_code}): {response.text[:100]}")
            return None

        data = response.json()

        if data.get('hits'):
            import random
            hit = random.choice(data['hits'])
            videos = hit.get('videos', {})
            best_video = videos.get('large') or videos.get('medium')
            if not best_video or not best_video.get('url'):
                return None

            video_url = best_video['url']
            quality = f"{best_video.get('width')}x{best_video.get('height')}"

            filename = f"pixabay_{uuid.uuid4()}.mp4"
            filepath = os.path.join(self.cache_dir, filename)

            logger.info(f"[Pixabay] Downloading clip ({quality}): {video_url[:50]}...")
            self._download_file(video_url, filepath)
            return filepath

        return None

    def get_audio(self, query, category="music"):
        """Downloads royalty-free music or SFX from Pixabay API."""
        if not self.api_key:
            logger.warning("Pixabay API key not configured")
            return None

        try:
            return self._search_and_download_audio(query, category)
        except Exception as e:
            logger.error(f"Pixabay Audio Error: {e}")
            return None

    @retry_with_backoff(max_retries=2, base_delay=2.0, exceptions=(requests.RequestException,))
    def _search_and_download_audio(self, query, category):
        """Search and download audio with retry support."""
        APIRateLimiters.pixabay.wait()

        params = {
            "key": self.api_key,
            "q": query,
            "per_page": 20,
            "safesearch": "true"
        }

        response = requests.get(self.music_url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data.get('hits'):
            import random
            hit = random.choice(data['hits'])
            audio_url = hit.get('download_url') or hit.get('audio')

            if audio_url:
                filename = f"{category}_{uuid.uuid4()}.mp3"
                filepath = os.path.join(self.cache_dir, filename)

                self._download_file(audio_url, filepath)
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
