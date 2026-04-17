"""
TikTok Content Agent

Cross-posts YouTube Shorts and Nature Shorts to TikTok with
optimized titles, hashtags, and descriptions for TikTok's algorithm.

Uses Gemini AI for:
- TikTok-optimized title generation
- Trending hashtag selection
- Caption/description optimization

Strategy:
- Cross-post existing Shorts (nature, trending) to TikTok
- Optimize metadata for TikTok's algorithm (first 3 seconds, hashtags, sounds)
- Track posted content to avoid duplicates
"""

import os
import json
import time
import uuid
from typing import Optional, Dict, List

from src.services.tiktok_service import TikTokService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# History file to track posted content
HISTORY_FILE = "data/tiktok_history.json"

# TikTok-optimized hashtags by category
TIKTOK_HASHTAGS = {
    "nature": [
        "#nature", "#rain", "#rainsounds", "#relaxing", "#asmr",
        "#sleep", "#whitenoise", "#peaceful", "#calming", "#ambient",
        "#fyp", "#foryou", "#viral", "#satisfying", "#meditation",
    ],
    "rain": [
        "#rain", "#rainsounds", "#rainyday", "#rainsoundsforsleeeping",
        "#thunderstorm", "#asmr", "#relaxing", "#sleep", "#cozy",
        "#fyp", "#foryou", "#viral", "#satisfying",
    ],
    "thunderstorm": [
        "#thunder", "#thunderstorm", "#storm", "#lightning",
        "#rainsounds", "#asmr", "#relaxing", "#sleep",
        "#fyp", "#foryou", "#viral",
    ],
    "ocean": [
        "#ocean", "#waves", "#oceanwaves", "#beach", "#sea",
        "#relaxing", "#asmr", "#sleep", "#nature", "#peaceful",
        "#fyp", "#foryou", "#viral",
    ],
    "forest": [
        "#forest", "#nature", "#birds", "#birdsong", "#trees",
        "#peaceful", "#relaxing", "#outdoors", "#hiking",
        "#fyp", "#foryou", "#viral",
    ],
    "waterfall": [
        "#waterfall", "#nature", "#water", "#relaxing", "#asmr",
        "#peaceful", "#amazing", "#beautiful",
        "#fyp", "#foryou", "#viral",
    ],
    "fireplace": [
        "#fireplace", "#fire", "#cozy", "#crackling", "#warm",
        "#relaxing", "#asmr", "#winter", "#comfort",
        "#fyp", "#foryou", "#viral",
    ],
    "sunset": [
        "#sunset", "#sunrise", "#golden", "#sky", "#beautiful",
        "#nature", "#timelapse", "#peaceful",
        "#fyp", "#foryou", "#viral",
    ],
    "trending": [
        "#trending", "#viral", "#fyp", "#foryou", "#foryoupage",
        "#explore", "#discover", "#trend",
    ],
    "default": [
        "#fyp", "#foryou", "#viral", "#foryoupage",
        "#trending", "#explore",
    ],
}


class TikTokAgent:
    """Agent for posting content to TikTok."""

    def __init__(self, tiktok_service: Optional[TikTokService] = None):
        self.tiktok = tiktok_service
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.history_file = os.path.join(self.project_root, HISTORY_FILE)
        self.history = self._load_history()

        # Try to import Gemini for title optimization
        self.gemini = None
        try:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.gemini = genai.Client(api_key=api_key)
                logger.info("🤖 TikTok Agent: Gemini AI connected")
        except Exception:
            logger.info("TikTok Agent: Running without Gemini AI")

    # ──────────────────────────────────────────────────────
    # HISTORY MANAGEMENT
    # ──────────────────────────────────────────────────────

    def _load_history(self) -> Dict:
        """Load posting history."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"posted_videos": [], "total_posts": 0}

    def _save_history(self):
        """Save posting history."""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def _is_already_posted(self, video_path: str) -> bool:
        """Check if a video has already been posted."""
        basename = os.path.basename(video_path)
        return basename in [p.get("filename") for p in self.history.get("posted_videos", [])]

    def _record_post(self, video_path: str, title: str, publish_id: str, category: str = ""):
        """Record a successful post."""
        if "posted_videos" not in self.history:
            self.history["posted_videos"] = []
        self.history["posted_videos"].append({
            "filename": os.path.basename(video_path),
            "title": title,
            "publish_id": publish_id,
            "category": category,
            "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        self.history["total_posts"] = self.history.get("total_posts", 0) + 1
        self._save_history()

    # ──────────────────────────────────────────────────────
    # TITLE & HASHTAG OPTIMIZATION
    # ──────────────────────────────────────────────────────

    def _optimize_title_for_tiktok(self, original_title: str, category: str = "") -> str:
        """
        Optimize a YouTube title for TikTok's algorithm.
        TikTok titles are captions — shorter, more hashtag-heavy.
        """
        if self.gemini:
            try:
                prompt = f"""Convert this YouTube video title into a TikTok caption.

YouTube Title: {original_title}
Category: {category or 'nature/relaxation'}

Rules:
- Maximum 150 characters total (including hashtags)
- Start with a hook emoji + short catchy text (max 60 chars)
- Add 4-6 relevant trending TikTok hashtags
- Must include #fyp and #foryou
- Use TikTok language style (casual, engaging)
- If it's a nature/relaxation video, emphasize sleep/ASMR/relaxation
- NO quotes around the output
- Output ONLY the caption, nothing else

Example outputs:
☔ This rain sound hits different at 3am #rain #asmr #sleep #fyp #foryou
🌊 Close your eyes and listen 😌 #ocean #waves #relaxing #fyp #foryou
"""
                response = self.gemini.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                caption = response.text.strip().strip('"').strip("'")
                if len(caption) > 10:
                    logger.info(f"  🤖 TikTok caption: {caption[:80]}...")
                    return caption[:150]
            except Exception as e:
                logger.warning(f"Gemini caption generation failed: {e}")

        # Fallback: manual optimization
        hashtags = TIKTOK_HASHTAGS.get(category, TIKTOK_HASHTAGS["default"])
        short_title = original_title.split("|")[0].split("-")[0].strip()[:60]
        tags_str = " ".join(hashtags[:6])
        return f"{short_title} {tags_str}"[:150]

    # ──────────────────────────────────────────────────────
    # CROSS-POST FROM EXISTING SHORTS
    # ──────────────────────────────────────────────────────

    def post_video(
        self,
        video_path: str,
        title: str,
        category: str = "",
        privacy_level: str = "PUBLIC_TO_EVERYONE",
    ) -> Optional[str]:
        """
        Post a video to TikTok.

        Args:
            video_path: Path to the video file
            title: Original title (will be optimized for TikTok)
            category: Content category for hashtag selection
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY

        Returns:
            publish_id if successful
        """
        if not self.tiktok or not self.tiktok.authenticated:
            logger.error("TikTok service not authenticated")
            return None

        if not os.path.exists(video_path):
            logger.error(f"Video not found: {video_path}")
            return None

        if self._is_already_posted(video_path):
            logger.info(f"⏭️ Already posted to TikTok: {os.path.basename(video_path)}")
            return None

        # Optimize title for TikTok
        tiktok_caption = self._optimize_title_for_tiktok(title, category)
        logger.info(f"📱 TikTok posting: {tiktok_caption[:60]}...")

        # Upload
        publish_id = self.tiktok.upload_video(
            file_path=video_path,
            title=tiktok_caption,
            privacy_level=privacy_level,
        )

        if publish_id:
            self._record_post(video_path, tiktok_caption, publish_id, category)
            logger.info(f"✅ TikTok post successful: {publish_id}")
            return publish_id
        else:
            logger.error("❌ TikTok post failed")
            return None

    def cross_post_nature_shorts(self, count: int = 3) -> int:
        """
        Find recent nature shorts and cross-post them to TikTok.
        Returns number of successful posts.
        """
        productions_dir = os.path.join(self.project_root, "assets", "productions")
        if not os.path.exists(productions_dir):
            logger.warning("No productions directory found")
            return 0

        # Find nature shorts folders
        shorts_dirs = []
        for d in sorted(os.listdir(productions_dir), reverse=True):
            if d.startswith("nature_shorts_"):
                full_path = os.path.join(productions_dir, d)
                if os.path.isdir(full_path):
                    shorts_dirs.append(full_path)

        if not shorts_dirs:
            logger.info("No nature shorts found to cross-post")
            return 0

        posted = 0
        for short_dir in shorts_dirs[:count * 3]:  # Check more to find unposted ones
            if posted >= count:
                break

            # Find the video file
            video_file = None
            metadata_file = None
            for f in os.listdir(short_dir):
                if f.endswith(".mp4"):
                    video_file = os.path.join(short_dir, f)
                elif f.endswith("_metadata.json"):
                    metadata_file = os.path.join(short_dir, f)

            if not video_file:
                continue

            if self._is_already_posted(video_file):
                continue

            # Load metadata for title
            title = "Nature Sounds 🌿 #nature #asmr #fyp"
            category = ""
            if metadata_file and os.path.exists(metadata_file):
                try:
                    with open(metadata_file, "r") as f:
                        meta = json.load(f)
                    title = meta.get("title", title)
                    category = meta.get("category", "")
                except Exception:
                    pass

            # Extract category from folder name
            if not category:
                folder_name = os.path.basename(short_dir)
                for cat in ["rain", "ocean", "forest", "thunderstorm", "waterfall",
                            "fireplace", "sunset", "snow", "river", "aurora", "underwater"]:
                    if cat in folder_name:
                        category = cat
                        break

            result = self.post_video(video_file, title, category)
            if result:
                posted += 1

        logger.info(f"\n📱 TikTok cross-post complete: {posted}/{count} posted")
        return posted

    def cross_post_trending_shorts(self, count: int = 3) -> int:
        """
        Find recent trending shorts and cross-post them to TikTok.
        Returns number of successful posts.
        """
        productions_dir = os.path.join(self.project_root, "assets", "productions")
        if not os.path.exists(productions_dir):
            return 0

        # Find trending shorts (non-nature)
        shorts_dirs = []
        for d in sorted(os.listdir(productions_dir), reverse=True):
            if d.startswith("shorts_") and not d.startswith("nature_"):
                full_path = os.path.join(productions_dir, d)
                if os.path.isdir(full_path):
                    shorts_dirs.append(full_path)

        posted = 0
        for short_dir in shorts_dirs[:count * 3]:
            if posted >= count:
                break

            video_file = None
            for f in os.listdir(short_dir):
                if f.endswith(".mp4"):
                    video_file = os.path.join(short_dir, f)
                    break

            if not video_file or self._is_already_posted(video_file):
                continue

            result = self.post_video(video_file, "Trending 🔥 #trending #viral #fyp", "trending")
            if result:
                posted += 1

        return posted

    # ──────────────────────────────────────────────────────
    # DAILY AUTOMATION
    # ──────────────────────────────────────────────────────

    def run_daily_automation(self, count: int = 3) -> int:
        """
        Run daily TikTok automation:
        - Cross-post nature shorts
        - Cross-post trending shorts

        Returns total number of posts made.
        """
        logger.info("📱 TikTok Daily Automation Starting...")
        logger.info(f"   Target: {count} posts")

        total = 0

        # 70% nature shorts, 30% trending
        nature_count = max(1, int(count * 0.7))
        trending_count = count - nature_count

        # Cross-post nature shorts
        logger.info(f"\n🌿 Cross-posting {nature_count} nature shorts...")
        total += self.cross_post_nature_shorts(nature_count)

        # Cross-post trending shorts
        if trending_count > 0:
            logger.info(f"\n🔥 Cross-posting {trending_count} trending shorts...")
            total += self.cross_post_trending_shorts(trending_count)

        logger.info(f"\n✅ TikTok Daily Automation Complete: {total}/{count} posted")
        return total
