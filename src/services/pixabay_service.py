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
        self.image_url = "https://pixabay.com/api/"

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

        # Truncate individual keywords that are too long (sentences from AI)
        keywords = [kw[:50] for kw in keywords]

        # Smart Progressive Search: Focus on context, avoid random nature/tech fallbacks
        search_attempts = [
            " ".join(keywords[:5]),  # First 5 keywords (avoid mega-long queries)
            " ".join(keywords[:3]),  # Contextual core
            keywords[0]  # Subject only
        ]

        # Clean up and enforce Pixabay 100-char limit
        cleaned = []
        for a in search_attempts:
            a = a.replace(",", "").replace(".", "").replace("(", "").replace(")", "").strip()
            a = a[:100]  # Pixabay API limit: 100 chars max
            if a and a not in cleaned:
                cleaned.append(a)
        search_attempts = cleaned

        for attempt in search_attempts:
            try:
                result = self._search_and_download_video(attempt, orientation)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Pixabay attempt failed ({attempt[:40]}): {e}")

        logger.error(f"All Pixabay search attempts failed for: {keywords[:3]}")
        return None

    def get_image(self, query):
        """Fetches an image from Pixabay."""
        if not self.api_key:
            logger.warning("Pixabay API key not configured")
            return None

        keywords = query if isinstance(query, list) else query.split()
        search_query = " ".join(keywords) if keywords else "cinematic"

        params = {
            "key": self.api_key,
            "q": search_query[:95],
            "image_type": "photo",
            "per_page": 3,
            "safesearch": "true"
        }

        try:
            APIRateLimiters.pixabay.wait()
            response = requests.get(self.image_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if data.get('hits'):
                import random
                hit = random.choice(data['hits'])
                image_url = hit.get('largeImageURL') or hit.get('webformatURL')
                if image_url:
                    filename = f"pixabay_img_{uuid.uuid4()}.jpg"
                    filepath = os.path.join(self.cache_dir, filename)
                    self._download_file(image_url, filepath)
                    return filepath
        except Exception as e:
            logger.warning(f"Pixabay image fetch failed: {e}")
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

        # Refine query based on orientation (Pixabay limit is 100 characters)
        refined_query = query[:85] 
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
        """Pixabay does not have a public music/audio API. Returns None to trigger local fallback."""
        logger.info("Pixabay: No public audio API available — using local fallback audio")
        return None

    @retry_with_backoff(max_retries=2, base_delay=1.0, exceptions=(requests.RequestException,))
    def _download_file(self, url, filepath):
        """Download file with retry support."""
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
