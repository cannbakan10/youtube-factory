"""
Freepik Premium Video Service

Downloads premium 4K stock videos for ambient/ASMR content.
Searches Freepik's stock library and downloads full quality videos.
"""

import os
import time
import json
import requests
from typing import Optional, List, Dict
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.freepik.com/v1"


class FreepikService:
    """Freepik Premium API — search & download 4K stock videos."""

    def __init__(self, output_dir: Optional[str] = None):
        self.api_key = os.getenv("FREEPIK_API_KEY", "")
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets", "cache", "freepik"
        )
        os.makedirs(self.output_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "x-freepik-api-key": self.api_key,
            "Accept-Encoding": "gzip",
        })

        if self.api_key:
            logger.info("🎨 FreepikService: Premium API ready")
        else:
            logger.warning("⚠️ FreepikService: No FREEPIK_API_KEY set")

    # ──────────────────────────────────────────────────────
    # SEARCH VIDEOS
    # ──────────────────────────────────────────────────────

    def search_videos(
        self,
        query: str,
        limit: int = 10,
        aspect_ratio: str = "16:9",
    ) -> List[Dict]:
        """
        Search for stock videos on Freepik.
        Returns list of video metadata with download capability.
        """
        if not self.api_key:
            return []

        try:
            params = {
                "term": query,
                "limit": min(limit, 50),
            }

            resp = self.session.get(f"{BASE_URL}/videos", params=params)
            resp.raise_for_status()
            data = resp.json()

            videos = []
            for item in data.get("data", []):
                if aspect_ratio and item.get("aspect_ratio") != aspect_ratio:
                    continue

                video = {
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "quality": item.get("quality", ""),
                    "duration": item.get("duration", ""),
                    "duration_seconds": self._parse_duration(item.get("duration", "")),
                    "aspect_ratio": item.get("aspect_ratio", ""),
                    "is_ai_generated": item.get("is_ai_generated", False),
                    "url": item.get("url", ""),
                    "author": item.get("author", {}).get("name", ""),
                    "source": "freepik",
                }
                videos.append(video)

            logger.info(f"🔍 Freepik: {len(videos)} videos for '{query}'")
            return videos

        except Exception as e:
            logger.error(f"Freepik search failed: {e}")
            return []

    def _parse_duration(self, duration_str: str) -> int:
        """Parse '00:00:17' to seconds."""
        try:
            parts = duration_str.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0
        except:
            return 0

    # ──────────────────────────────────────────────────────
    # DOWNLOAD VIDEO (Full Quality, Premium)
    # ──────────────────────────────────────────────────────

    def download_video(self, video_id: int, filename: Optional[str] = None) -> Optional[str]:
        """
        Download full quality stock video using Premium API.
        
        Endpoint: GET /v1/videos/{id}/download
        Returns: local file path or None
        """
        if not self.api_key:
            logger.warning("No Freepik API key")
            return None

        # Check cache first
        cached = self._find_cached(video_id)
        if cached:
            logger.info(f"  ♻️ Cache hit: {os.path.basename(cached)}")
            return cached

        try:
            # Step 1: Get download URL
            resp = self.session.get(f"{BASE_URL}/videos/{video_id}/download")
            resp.raise_for_status()
            dl_data = resp.json().get("data", {})

            dl_url = dl_data.get("url", "")
            dl_filename = dl_data.get("filename", f"freepik_{video_id}.mp4")

            if not dl_url:
                logger.error(f"No download URL for video {video_id}")
                return None

            # Use custom filename or default
            if filename:
                dl_filename = filename
            else:
                # Normalize: freepik_ID_name.ext
                ext = os.path.splitext(dl_filename)[1] or ".mp4"
                dl_filename = f"freepik_{video_id}{ext}"

            output_path = os.path.join(self.output_dir, dl_filename)

            # Step 2: Download the actual video
            logger.info(f"  📥 Downloading {dl_filename}...")
            video_resp = requests.get(dl_url, stream=True, timeout=180)
            video_resp.raise_for_status()

            total_size = int(video_resp.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in video_resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)

            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"  ✅ Downloaded: {dl_filename} ({size_mb:.1f} MB)")
            return output_path

        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 403:
                logger.error(f"❌ Download denied for video {video_id} — check API plan")
            else:
                logger.error(f"Download failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def _find_cached(self, video_id: int) -> Optional[str]:
        """Check if video is already cached locally."""
        prefix = f"freepik_{video_id}"
        for fname in os.listdir(self.output_dir):
            if fname.startswith(prefix):
                path = os.path.join(self.output_dir, fname)
                if os.path.getsize(path) > 1000:  # Not corrupted
                    return path
        return None

    # ──────────────────────────────────────────────────────
    # MULTI-VIDEO DOWNLOAD (for ambient long-form)
    # ──────────────────────────────────────────────────────

    def get_multiple_videos(
        self,
        keywords: List[str],
        count: int = 5,
        orientation: str = "landscape",
    ) -> List[str]:
        """
        Search and download multiple unique video clips.
        Used for assembling long-form ambient videos (1-16 hours).
        
        Returns list of local file paths to downloaded videos.
        """
        if not self.api_key:
            return []

        downloaded = []
        seen_ids = set()

        for keyword in keywords:
            if len(downloaded) >= count:
                break

            videos = self.search_videos(keyword, limit=10)

            for video in videos:
                if len(downloaded) >= count:
                    break
                if video["id"] in seen_ids:
                    continue

                # Prefer longer clips (more content per download)
                if video["duration_seconds"] < 5:
                    continue

                seen_ids.add(video["id"])

                path = self.download_video(video["id"])
                if path:
                    downloaded.append(path)

                time.sleep(0.5)  # Rate limiting

        logger.info(f"📦 Freepik: Downloaded {len(downloaded)}/{count} clips")
        return downloaded

    # ──────────────────────────────────────────────────────
    # SEARCH IMAGES (for thumbnails)
    # ──────────────────────────────────────────────────────

    def search_images(self, query: str, limit: int = 5) -> List[Dict]:
        """Search premium stock images for thumbnails."""
        if not self.api_key:
            return []

        try:
            params = {
                "term": query,
                "limit": min(limit, 50),
                "filters[content_type][photo]": 1,
            }

            resp = self.session.get(f"{BASE_URL}/resources", params=params)
            resp.raise_for_status()
            data = resp.json()

            images = []
            for item in data.get("data", []):
                images.append({
                    "id": item.get("id"),
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "thumbnail": item.get("image", {}).get("source", {}).get("url", ""),
                })

            logger.info(f"🖼️ Freepik: {len(images)} images for '{query}'")
            return images

        except Exception as e:
            logger.error(f"Image search failed: {e}")
            return []
