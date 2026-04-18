"""
Nightly Brain Agent — The Central Intelligence System

Runs every night automatically via GitHub Actions. Performs:
1. CLEANUP: Deletes underperforming videos (Turkish content, low views, duplicates)
2. ANALYZE: Full channel analytics and performance report
3. DISCOVER: Uses YouTube Data API to find top 100 trending videos in US
4. PLAN: Creates next-day content plan based on trending topics
5. SCHEDULE: Saves plan for morning automation to execute

Strategy: English-only, US-focused, data-driven content creation.

Flow:
  23:00 UTC → Nightly Brain runs
    ├── Delete underperformers
    ├── Analyze channel health
    ├── Find top 100 trending US videos
    ├── Generate content plan for tomorrow
    └── Save plan to data/daily_plan.json

  Content Engine workflows read daily_plan.json and produce content

  Daily Budget (3,000 hrs/month):
    Nightly Brain: ~20 min/run × 30 = 10 hrs/month
    Content Engine: 5 runs × ~25 min = 125 min/day = ~63 hrs/month
    Total: ~73 hrs/month = 2.4% of budget

  Daily Output: 8 Shorts + 2 Long-form = 10 videos/day
  Monthly Output: ~300 videos/month
"""

import os
import json
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import Counter

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Plan file locations
DAILY_PLAN_FILE = "data/daily_plan.json"
NIGHTLY_LOG_DIR = "data/nightly_logs"
WINNERS_FILE = "data/winners.json"
PEAK_HOURS_FILE = "data/peak_hours.json"
RETENTION_FILE = "data/retention_insights.json"

# Winner amplification thresholds
WINNER_MIN_VIEWS = 300          # Absolute minimum to qualify as winner
WINNER_MULTIPLIER = 2.0         # Or 2x channel median views (whichever is higher)
WINNER_STORE_MAX = 30           # Keep last 30 winners
WINNER_MAX_VARIATIONS = 5       # Stop re-using a winner after 5 variations generated
WINNER_SLOT_RATIO = 0.30        # 30% of new plan shorts should be winner variations

# Turkish detection patterns
TURKISH_CHARS = set("çğıöşüÇĞİÖŞÜ")
TURKISH_KEYWORDS = [
    "hakkında", "neden", "nasıl", "dünyanın", "türkiye", "bilmediğin",
    "şok", "inanılmaz", "edici", "gerçekler", "sırrı", "gizemi",
    "tarihinin", "osmanlı", "şehzade", "ölümcül", "zengin", "meslek",
    "pasaport", "savaş", "fethi", "hamlesi", "irkı", "kediler",
    "bilgiler", "olacaksınız", "insanlık", "öldü", "oluyor",
]

# Minimum performance thresholds (aggressive — low performers hurt channel score)
MIN_SHORTS_VIEWS_7D = 50        # Minimum views after 7 days
MIN_SHORTS_VIEWS_14D = 100      # Minimum views after 14 days
MIN_SHORTS_VIEWS_30D = 200      # Minimum views after 30 days
MIN_LONGFORM_VIEWS_14D = 50     # Minimum views for longform after 14 days
MIN_LONGFORM_VIEWS_30D = 100    # Minimum views for longform after 30 days
DUPLICATE_SIMILARITY_THRESHOLD = 0.60  # Lower = More aggressive cleanup


class NightlyBrainAgent:
    """
    The central intelligence system that runs nightly to:
    - Clean up underperforming content
    - Discover trending topics via YouTube API
    - Plan next day's content production
    """

    def __init__(self, youtube_service=None):
        self.youtube = youtube_service
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.plan_file = os.path.join(self.project_root, DAILY_PLAN_FILE)
        self.log_dir = os.path.join(self.project_root, NIGHTLY_LOG_DIR)
        os.makedirs(self.log_dir, exist_ok=True)

        # Public YouTube API client (API key, no OAuth needed)
        # OAuth tokens may lack youtube.readonly scope, causing 403 on public data
        self.yt_public = None
        api_key = os.getenv("YOUTUBE_API_KEY")
        if api_key:
            try:
                from googleapiclient.discovery import build
                self.yt_public = build("youtube", "v3", developerKey=api_key)
                logger.info("🔑 Nightly Brain: YouTube API key client ready")
            except Exception as e:
                logger.warning(f"YouTube API key client failed: {e}")

        # Fallback: try OAuth service if API key not available
        if not self.yt_public and self.youtube and self.youtube.youtube:
            self.yt_public = self.youtube.youtube
            logger.info("🔄 Using OAuth client for public data (may lack scopes)")

        # Gemini AI (with model fallback chain for quota exhaustion)
        self.gemini = None
        self.gemini_models = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
        try:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.gemini = genai.Client(api_key=api_key)
                logger.info("🧠 Nightly Brain: Gemini AI connected")
        except Exception:
            logger.info("Nightly Brain: Running without Gemini")

        # OpenAI fallback for plan generation
        self.oa_client = None
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                import httpx
                self.oa_client = OpenAI(
                    api_key=openai_key,
                    timeout=httpx.Timeout(90.0, connect=10.0),
                    max_retries=3,
                )
                logger.info("🤖 Nightly Brain: OpenAI fallback ready")
            except Exception as e:
                logger.warning(f"OpenAI client init failed: {e}")

    # ──────────────────────────────────────────────────────
    # PHASE 1: CLEANUP — Delete underperformers
    # ──────────────────────────────────────────────────────

    def cleanup_channel(self, dry_run: bool = False) -> Dict:
        """
        Smart cleanup with two-phase system:
        
        Phase A: Unlist underperformers (gives them a second chance)
        Phase B: Delete already-unlisted videos from previous cycles
        
        Also considers:
        - Dynamic thresholds based on channel subscriber count
        - Growth trajectory (skip videos still gaining momentum)
        - Engagement quality (protect high-engagement videos)
        """
        if not self.youtube or not self.youtube.youtube:
            logger.error("YouTube service not available for cleanup")
            return {"error": "No YouTube service"}

        logger.info("🗑️ Phase 1: Smart Channel Cleanup Starting...")

        # Import analytics to get all videos
        from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
        analytics = YouTubeAnalyticsAgent(youtube_service=self.youtube)
        channel_info = analytics.get_channel_info()
        videos = analytics.get_all_videos()

        if not videos:
            return {"error": "No videos found"}

        # Dynamic thresholds based on subscriber count
        subs = channel_info.get("subscriber_count", 0) if channel_info else 0
        thresholds = self._calculate_dynamic_thresholds(subs)
        logger.info(f"📐 Dynamic thresholds (based on {subs:,} subs): {thresholds}")

        to_unlist = []    # Phase A: Make unlisted first
        to_delete = []    # Phase B: Delete previously unlisted
        to_keep = []

        for v in videos:
            delete_reasons = []

            # ── SKIP: Too new to judge ──
            if v["days_since_publish"] < 5:
                to_keep.append(v)
                continue

            # ── Rule 0: Strategy enforcement — delete non-Shorts under 1 hour ──
            # Channel strategy: Shorts (discovery) + Ambient (1-16h watch time)
            # Mid-length videos (2-59 min) don't fit and hurt channel identity
            if not v["is_shorts"] and v["duration_seconds"] < 3600:
                delete_reasons.append(
                    f"Mid-length video ({v['duration_seconds'] // 60}min) — "
                    f"channel strategy is Shorts + Ambient only"
                )
                # Even if high views, remove to maintain channel identity
                if v.get("privacy_status") == "unlisted":
                    to_delete.append({**v, "delete_reasons": delete_reasons})
                else:
                    to_unlist.append({**v, "delete_reasons": delete_reasons})
                continue

            # ── PROTECT: High engagement (algorithm may push later) ──
            if v["engagement_rate"] > 8.0 and v["days_since_publish"] < 30:
                to_keep.append(v)
                continue

            # ── PROTECT: Growing videos (views_per_day > threshold) ──
            if v["views_per_day"] > 5 and v["days_since_publish"] < 21:
                to_keep.append(v)
                continue

            # ── Rule 1: Turkish content — always remove ──
            if self._is_turkish(v["title"]):
                if v["views"] >= 1000:
                    to_keep.append(v)
                    continue
                delete_reasons.append("Turkish content (channel is English-only)")

            # ── Rule 2: Zero views ──
            if v["views"] == 0 and v["days_since_publish"] > 5:
                delete_reasons.append(f"Zero views after {v['days_since_publish']} days")

            # ── Rule 3: Low views for Shorts ──
            if v["is_shorts"] and not delete_reasons:
                if v["days_since_publish"] > 7 and v["views"] < thresholds["shorts_7d"]:
                    delete_reasons.append(
                        f"Only {v['views']} views after 7+ days (min: {thresholds['shorts_7d']})"
                    )
                elif v["days_since_publish"] > 14 and v["views"] < thresholds["shorts_14d"]:
                    delete_reasons.append(
                        f"Only {v['views']} views after 14+ days (min: {thresholds['shorts_14d']})"
                    )
                elif v["days_since_publish"] > 30 and v["views"] < thresholds["shorts_30d"]:
                    delete_reasons.append(
                        f"Only {v['views']} views after 30+ days (min: {thresholds['shorts_30d']})"
                    )

            # ── Rule 4: Low views for Longform ──
            if not v["is_shorts"] and not delete_reasons:
                if v["days_since_publish"] > 14 and v["views"] < thresholds["long_14d"]:
                    delete_reasons.append(
                        f"Longform with only {v['views']} views after 14+ days (min: {thresholds['long_14d']})"
                    )
                elif v["days_since_publish"] > 30 and v["views"] < thresholds["long_30d"]:
                    delete_reasons.append(
                        f"Longform with only {v['views']} views after 30+ days (min: {thresholds['long_30d']})"
                    )

            # ── Rule 5: Dead engagement ──
            if v["views"] > 50 and v["engagement_rate"] == 0 and v["days_since_publish"] > 14:
                delete_reasons.append(
                    f"{v['views']} views but zero engagement — dead content"
                )

            # ── Decide: unlist or delete ──
            if delete_reasons:
                if v.get("privacy_status") == "unlisted":
                    # Already unlisted from a previous cycle → now delete
                    to_delete.append({**v, "delete_reasons": delete_reasons})
                else:
                    # First offense → unlist, give second chance
                    to_unlist.append({**v, "delete_reasons": delete_reasons})
            else:
                to_keep.append(v)

        # Find duplicates among kept videos
        duplicates = self._find_duplicates(to_keep)
        for dup in duplicates:
            to_delete.append({
                **dup["delete_video"],
                "delete_reasons": [f"Duplicate of '{dup['keep_video']['title'][:40]}' ({dup['similarity']}% similar)"]
            })

        logger.info(f"📊 Cleanup plan: {len(to_unlist)} to unlist, {len(to_delete)} to delete, {len(to_keep)} to keep")

        # ── Execute: Unlist (Phase A) ──
        unlisted = []
        for v in to_unlist:
            if dry_run:
                logger.info(f"  [DRY] Would unlist: {v['title'][:50]} | Views: {v['views']} | {v['delete_reasons'][0]}")
                unlisted.append({**v, "status": "DRY_RUN"})
            else:
                try:
                    self.youtube.youtube.videos().update(
                        part="status",
                        body={"id": v["id"], "status": {"privacyStatus": "unlisted"}}
                    ).execute()
                    logger.info(f"  🔒 Unlisted: {v['title'][:50]} ({v['views']} views)")
                    unlisted.append({**v, "status": "UNLISTED"})
                    time.sleep(0.3)
                except Exception as e:
                    logger.error(f"  ❌ Failed to unlist {v['id']}: {e}")

        # ── Execute: Delete (Phase B — previously unlisted) ──
        deleted = []
        failed = []
        for v in to_delete:
            if dry_run:
                logger.info(f"  [DRY] Would delete: {v['title'][:50]} | Views: {v['views']} | {v['delete_reasons'][0]}")
                deleted.append({**v, "status": "DRY_RUN"})
            else:
                try:
                    self.youtube.youtube.videos().delete(id=v["id"]).execute()
                    logger.info(f"  🗑️ Deleted: {v['title'][:50]} ({v['views']} views)")
                    deleted.append({**v, "status": "DELETED"})
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"  ❌ Failed to delete {v['id']}: {e}")
                    failed.append({**v, "error": str(e)})

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_videos": len(videos),
            "unlisted_count": len(unlisted),
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "kept_count": len(to_keep),
            "thresholds_used": thresholds,
            "subscriber_count": subs,
            "unlisted_videos": [
                {"id": v["id"], "title": v["title"], "views": v["views"],
                 "reasons": v["delete_reasons"], "status": v.get("status", "")}
                for v in unlisted
            ],
            "deleted_videos": [
                {"id": v["id"], "title": v["title"], "views": v["views"],
                 "reasons": v["delete_reasons"], "status": v.get("status", "DELETED")}
                for v in deleted
            ],
            "failed_videos": [
                {"id": v["id"], "title": v["title"], "error": v.get("error", "")}
                for v in failed
            ],
        }

        logger.info(
            f"✅ Cleanup complete: {len(unlisted)} unlisted, "
            f"{len(deleted)} deleted, {len(failed)} failed, {len(to_keep)} kept"
        )
        return report

    def _calculate_dynamic_thresholds(self, subscriber_count: int) -> Dict:
        """
        Calculate view thresholds relative to channel size.
        Larger channels should have higher standards.
        """
        # Base multiplier: 1.0 for ~1K subs, scales up
        if subscriber_count < 500:
            mult = 0.5
        elif subscriber_count < 2000:
            mult = 0.75
        elif subscriber_count < 5000:
            mult = 1.0
        elif subscriber_count < 20000:
            mult = 1.5
        elif subscriber_count < 100000:
            mult = 2.0
        else:
            mult = 3.0

        return {
            "shorts_7d": int(MIN_SHORTS_VIEWS_7D * mult),
            "shorts_14d": int(MIN_SHORTS_VIEWS_14D * mult),
            "shorts_30d": int(MIN_SHORTS_VIEWS_30D * mult),
            "long_14d": int(MIN_LONGFORM_VIEWS_14D * mult),
            "long_30d": int(MIN_LONGFORM_VIEWS_30D * mult),
            "multiplier": mult,
        }

    def _is_turkish(self, text: str) -> bool:
        """Detect if text is Turkish."""
        text_lower = text.lower()
        # Check for Turkish-specific characters
        if any(c in TURKISH_CHARS for c in text):
            return True
        # Check for Turkish keywords
        matching = sum(1 for kw in TURKISH_KEYWORDS if kw in text_lower)
        return matching >= 2  # At least 2 Turkish keywords

    def _find_duplicates(self, videos: List[Dict]) -> List[Dict]:
        """Find duplicate videos, keep the one with more views."""
        duplicates = []
        checked = set()

        for i, v1 in enumerate(videos):
            if v1["id"] in checked:
                continue
            t1 = self._normalize_title(v1["title"])

            for j, v2 in enumerate(videos):
                if i >= j or v2["id"] in checked:
                    continue
                t2 = self._normalize_title(v2["title"])
                sim = self._title_similarity(t1, t2)

                if sim > DUPLICATE_SIMILARITY_THRESHOLD:
                    if v1["views"] >= v2["views"]:
                        keep, delete = v1, v2
                    else:
                        keep, delete = v2, v1
                    duplicates.append({
                        "keep_video": keep,
                        "delete_video": delete,
                        "similarity": round(sim * 100, 1),
                    })
                    checked.add(delete["id"])

        return duplicates

    def _normalize_title(self, title: str) -> str:
        title = title.lower().strip()
        title = re.sub(r'[#@]\w+', '', title)
        title = re.sub(r'[^\w\s]', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def _title_similarity(self, t1: str, t2: str) -> float:
        words1 = set(t1.split())
        words2 = set(t2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    # ──────────────────────────────────────────────────────
    # PHASE 2: DISCOVER — Find trending videos + channels
    # ──────────────────────────────────────────────────────

    def discover_trending(self, region: str = "US", count: int = 100) -> List[Dict]:
        """
        Use YouTube Data API (API key) to find top trending videos + channels.
        
        Two-stage discovery:
        1. Find trending videos via mostPopular chart
        2. Identify top-performing channels → fetch their recent viral content
           to understand what makes content go viral
        """
        if not self.yt_public:
            logger.error("No YouTube API client available (set YOUTUBE_API_KEY)")
            return []

        logger.info(f"🔍 Phase 2: Discovering top {count} trending videos in {region}...")

        # ── STAGE 1: Trending Videos from mostPopular chart ──
        categories = {
            "0": "All",
            "24": "Entertainment",
            "28": "Science & Technology",
            "25": "News & Politics",
            "22": "People & Blogs",
            "27": "Education",
            "17": "Sports",
            "26": "Howto & Style",
            "1": "Film & Animation",
            "20": "Gaming",
        }

        all_trending = []
        seen_ids = set()
        channel_ids = {}  # channel_id -> channel_name
        per_category = max(count // len(categories), 10)

        for cat_id, cat_name in categories.items():
            try:
                request = self.yt_public.videos().list(
                    part="snippet,statistics,contentDetails",
                    chart="mostPopular",
                    regionCode=region,
                    videoCategoryId=cat_id,
                    maxResults=min(per_category, 50),
                    hl="en",
                )
                response = request.execute()

                for item in response.get("items", []):
                    vid_id = item["id"]
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    stats = item.get("statistics", {})
                    snippet = item.get("snippet", {})
                    content = item.get("contentDetails", {})

                    duration_str = content.get("duration", "PT0S")
                    duration_sec = self._parse_iso_duration(duration_str)
                    is_shorts = duration_sec <= 60

                    views = int(stats.get("viewCount", 0))
                    likes = int(stats.get("likeCount", 0))
                    comments = int(stats.get("commentCount", 0))

                    # Track channels for Stage 2
                    ch_id = snippet.get("channelId", "")
                    ch_title = snippet.get("channelTitle", "")
                    if ch_id and views > 100000:
                        channel_ids[ch_id] = ch_title

                    all_trending.append({
                        "id": vid_id,
                        "title": snippet.get("title", ""),
                        "channel": ch_title,
                        "channel_id": ch_id,
                        "category": cat_name,
                        "category_id": cat_id,
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
                        "duration_seconds": duration_sec,
                        "is_shorts": is_shorts,
                        "tags": snippet.get("tags", [])[:10],
                        "description": snippet.get("description", "")[:200],
                        "published_at": snippet.get("publishedAt", ""),
                    })

                logger.info(f"  📂 {cat_name}: {len(response.get('items', []))} trending")

            except Exception as e:
                logger.warning(f"  ⚠️ Category {cat_name} failed: {e}")

        # ── STAGE 2: Analyze top trending channels ──
        channel_insights = self._analyze_trending_channels(channel_ids)

        # Sort by views
        all_trending.sort(key=lambda v: v["views"], reverse=True)
        all_trending = all_trending[:count]

        # Attach channel insights to trending data
        if channel_insights:
            for vid in all_trending:
                ch_id = vid.get("channel_id", "")
                if ch_id in channel_insights:
                    vid["channel_patterns"] = channel_insights[ch_id]

        logger.info(f"✅ Found {len(all_trending)} trending videos + {len(channel_insights)} channel analyses")
        return all_trending

    def _analyze_trending_channels(self, channel_ids: Dict[str, str], max_channels: int = 10) -> Dict:
        """
        Analyze the top trending channels to understand their content strategy.
        Fetches their recent popular uploads to find patterns.
        
        Returns dict: channel_id -> {name, subscribers, recent_hits, content_patterns}
        """
        if not self.yt_public or not channel_ids:
            return {}

        logger.info(f"📡 Analyzing top {min(len(channel_ids), max_channels)} trending channels...")

        # Pick top channels (limit API calls)
        top_channels = dict(list(channel_ids.items())[:max_channels])
        insights = {}

        try:
            # Batch fetch channel details
            ch_ids_str = ",".join(top_channels.keys())
            ch_response = self.yt_public.channels().list(
                part="snippet,statistics,contentDetails",
                id=ch_ids_str,
            ).execute()

            for ch in ch_response.get("items", []):
                ch_id = ch["id"]
                ch_stats = ch.get("statistics", {})
                ch_snippet = ch.get("snippet", {})
                uploads_playlist = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")

                subscribers = int(ch_stats.get("subscriberCount", 0))
                total_videos = int(ch_stats.get("videoCount", 0))

                # Skip very small channels
                if subscribers < 10000:
                    continue

                # Fetch recent uploads from this channel
                recent_hits = []
                if uploads_playlist:
                    try:
                        pl_response = self.yt_public.playlistItems().list(
                            part="snippet",
                            playlistId=uploads_playlist,
                            maxResults=10,
                        ).execute()

                        video_ids = [
                            item["snippet"]["resourceId"]["videoId"]
                            for item in pl_response.get("items", [])
                            if item.get("snippet", {}).get("resourceId", {}).get("videoId")
                        ]

                        if video_ids:
                            vids_response = self.yt_public.videos().list(
                                part="snippet,statistics,contentDetails",
                                id=",".join(video_ids),
                            ).execute()

                            for vid in vids_response.get("items", []):
                                v_stats = vid.get("statistics", {})
                                v_snippet = vid.get("snippet", {})
                                v_content = vid.get("contentDetails", {})
                                dur = self._parse_iso_duration(v_content.get("duration", "PT0S"))
                                views = int(v_stats.get("viewCount", 0))

                                recent_hits.append({
                                    "title": v_snippet.get("title", ""),
                                    "views": views,
                                    "likes": int(v_stats.get("likeCount", 0)),
                                    "duration_sec": dur,
                                    "is_shorts": dur <= 60,
                                    "tags": v_snippet.get("tags", [])[:5],
                                    "published": v_snippet.get("publishedAt", ""),
                                })

                    except Exception as e:
                        logger.warning(f"  ⚠️ Failed to fetch uploads for {top_channels.get(ch_id, ch_id)}: {e}")

                # Extract patterns from recent hits
                if recent_hits:
                    avg_views = sum(h["views"] for h in recent_hits) / len(recent_hits)
                    shorts_ratio = sum(1 for h in recent_hits if h["is_shorts"]) / len(recent_hits)
                    
                    # Extract common title patterns
                    all_titles = [h["title"] for h in recent_hits]
                    all_tags = []
                    for h in recent_hits:
                        all_tags.extend(h.get("tags", []))
                    top_tags = [tag for tag, _ in Counter(all_tags).most_common(5)]

                    insights[ch_id] = {
                        "name": ch_snippet.get("title", top_channels.get(ch_id, "")),
                        "subscribers": subscribers,
                        "total_videos": total_videos,
                        "avg_recent_views": int(avg_views),
                        "shorts_ratio": round(shorts_ratio, 2),
                        "recent_titles": all_titles[:5],
                        "popular_tags": top_tags,
                        "content_type": "shorts-focused" if shorts_ratio > 0.6 else ("mixed" if shorts_ratio > 0.3 else "longform-focused"),
                    }

                    logger.info(f"  🔎 {insights[ch_id]['name']}: {subscribers:,} subs, avg {int(avg_views):,} views, {insights[ch_id]['content_type']}")

        except Exception as e:
            logger.warning(f"⚠️ Channel analysis failed: {e}")

        return insights

    # ──────────────────────────────────────────────────────
    # PHASE 3: PLAN — Generate next-day content plan
    # ──────────────────────────────────────────────────────

    def generate_content_plan(self, trending: List[Dict], channel_videos: List[Dict] = None,
                              performance_review: Dict = None, viral_shorts: List[Dict] = None,
                              competitor_insights: List[Dict] = None, audience_desires: List[str] = None,
                              ai_trends: List[Dict] = None, active_winners: List[Dict] = None,
                              world_news_videos: List[Dict] = None) -> Dict:
        """
        Analyze trending videos and create a content plan for tomorrow.
        Uses Gemini AI with deep insights from:
        - Trending chart videos
        - Viral Shorts search results (search.list)
        - Competitor channel monitoring
        - Audience comment mining
        - Performance feedback loop
        - AI Trend discovery (TrendAgent)
        """
        logger.info("📝 Phase 3: Generating content plan...")

        # Extract trending topics/themes
        trending_topics = self._extract_topics_from_trending(trending)

        # Get existing video titles for history and deduplication
        existing_titles_raw = []
        if channel_videos:
            existing_titles_raw = [v["title"] for v in channel_videos]
        
        # normalized set for fast exact lookups
        existing_titles_norm = {self._normalize_title(t) for t in existing_titles_raw}

        # --- ADVANCED VARIETY CHECK: Detect Saturated Topics ---
        saturated_topics = []
        if existing_titles_raw:
            all_words = " ".join(existing_titles_raw).lower().split()
            # Filter out common stop words and small words
            stop_words = {"the", "and", "how", "why", "what", "is", "a", "of", "to", "in", "with", "for", "on", "new", "this", "that", "that's", "it's", "you", "your"}
            keywords = [w for w in all_words if len(w) > 3 and w not in stop_words]
            counts = Counter(keywords)
            # Find keywords used more than 3 times
            saturated_topics = [f"'{word.upper()}' (used {count} times)" for word, count in counts.most_common(12) if count >= 3]

        if not self.gemini:
            # Fallback: manually pick from trending
            return self._manual_plan(trending, existing_titles_norm)

        # AI-powered plan generation
        try:
            top_20_summary = "\n".join(
                f"{i+1}. [{v['category']}] {v['title']} | "
                f"Views: {v['views']:,} | Engagement: {v['engagement_rate']}% | "
                f"Tags: {', '.join(v.get('tags', [])[:5])}"
                + (f" | Region: {v.get('source_region', 'US')}" if v.get("source_region") else "")
                for i, v in enumerate(trending[:20])
            )

            # Last 80 titles is enough to detect repeats — larger history
            # bloats the prompt and can push us past Gemini's response budget,
            # which was triggering silent fallbacks to _manual_plan.
            history_text = "\n".join(existing_titles_raw[:80]) if existing_titles_raw else "None"
            saturated_text = "\n".join(saturated_topics) if saturated_topics else "None"

            # Extract channel insights for the prompt
            channel_insights_text = ""
            seen_channels = set()
            for v in trending[:50]:
                patterns = v.get("channel_patterns")
                if patterns and patterns["name"] not in seen_channels:
                    seen_channels.add(patterns["name"])
                    channel_insights_text += (
                        f"\n🔎 {patterns['name']} ({patterns['subscribers']:,} subs, "
                        f"avg {patterns['avg_recent_views']:,} views/video, {patterns['content_type']})\n"
                        f"   Recent hits: {', '.join(patterns['recent_titles'][:3])}\n"
                        f"   Top tags: {', '.join(patterns['popular_tags'][:5])}\n"
                    )
                if len(seen_channels) >= 8:
                    break

            channel_section = ""
            if channel_insights_text:
                channel_section = f"""
Here are the TOP PERFORMING CHANNELS trending right now and their content patterns:
{channel_insights_text}
IMPORTANT: Study these channels' content patterns. Create content SIMILAR to their 
successful formats but with your own unique angle. Focus on topics that these proven 
channels have shown can go viral.
"""

            # Performance feedback section
            perf_section = ""
            if performance_review and performance_review.get("status") != "no_recent_videos":
                best_topics = ", ".join(performance_review.get("best_topics", [])[:3])
                loser_topics = ", ".join(performance_review.get("loser_titles", [])[:3])
                avg_views = performance_review.get("avg_views_48h", 0)
                perf_section = f"""
PERFORMANCE FEEDBACK (Last 48 hours):
- Average views: {avg_views}
- Best performing topics: {best_topics}
- Underperforming topics: {loser_topics}
- Winners count: {performance_review.get('winners_count', 0)}
- Losers count: {performance_review.get('losers_count', 0)}

STRATEGY ADJUSTMENT: Create MORE content similar to the best performing topics.
AVOID topics similar to the underperforming ones. Double down on what works!
"""

            # Viral Shorts section
            viral_section = ""
            if viral_shorts:
                viral_list = "\n".join(
                    f"  - \"{v['title']}\" ({v['views']:,} views, {v['engagement_rate']}% eng) [query: {v.get('search_query', '')}]"
                    for v in viral_shorts[:10]
                )
                viral_section = f"""

VIRAL SHORTS IN OUR NICHE (last 7 days, 10K+ views):
{viral_list}

IMPORTANT: These Shorts went viral in OUR exact niche. Study their titles, 
hooks, and topics. Create similar content with a fresh angle!
"""

            # Competitor section
            competitor_section = ""
            if competitor_insights:
                comp_list = "\n".join(
                    f"  📺 {c['channel']}: {', '.join(c['recent_titles'][:3])}"
                    for c in competitor_insights
                )
                competitor_section = f"""

COMPETITOR ACTIVITY (last 7 days):
{comp_list}

Study competitors' topics — create BETTER versions of their content.
"""

            # Audience desires section
            audience_section = ""
            if audience_desires:
                desires_list = "\n".join(f"  - \"{d}\"" for d in audience_desires[:10])
                audience_section = f"""

AUDIENCE COMMENTS (from top viral videos — what people want):
{desires_list}

Use these comments to understand what viewers are asking for. Create content that answers their curiosity!
"""

            # AI Trending Topics Section
            ai_trend_section = ""
            if ai_trends:
                ai_list = "\n".join(f"  🔥 {t['topic']}: {t['reason']}" for t in ai_trends)
                ai_trend_section = f"""
AI-CURATED VIRAL TRENDS (High Potential):
{ai_list}

PRIORITIZE these AI trends as they are specifically selected for Shorts viral potential!
"""

            # Winner Amplification Section (our own channel's proven winners)
            winners_section = ""
            target_winner_count = 0
            if active_winners:
                target_winner_count = max(1, int(round(20 * WINNER_SLOT_RATIO)))
                winner_list = "\n".join(
                    f"  🏆 [id:{w['video_id']}] \"{w['title']}\" — {w['views']:,} views "
                    f"({w.get('views_per_day', 0):.1f}/day, {w.get('engagement_rate', 0)}% eng)"
                    for w in active_winners[:8]
                )
                winners_section = f"""

🏆 YOUR CHANNEL'S OWN WINNERS (PROVEN high performers on this channel):
{winner_list}

CRITICAL WINNER AMPLIFICATION RULE:
- At least {target_winner_count} of the 20 new Shorts MUST be FRESH VARIATIONS/angles
  of these winning topics. These are PROVEN to work for THIS channel's audience.
- Do NOT copy the exact title. Create NEW angles: different facts, counter-perspectives,
  deeper dives, related sub-topics, "the truth about X", "X explained", part 2, etc.
- For each winner-variation Short, add `"winner_source_id": "<video_id>"` field
  pointing to the winner it was inspired by, and `"is_winner_variation": true`.
- Regular (non-winner) shorts should have `"is_winner_variation": false`.
"""

            # World news section for long-form planning
            world_news_section = ""
            if world_news_videos:
                news_list = "\n".join(
                    f"  🌍 \"{v['title']}\" ({v['views']:,} views, {v.get('channel', 'N/A')}) [{v.get('search_query', '')}]"
                    for v in world_news_videos[:10]
                )
                world_news_section = f"""

🌍 TRENDING WORLD NEWS VIDEOS (high-performing current events content):
{news_list}

IMPORTANT: Use these as inspiration for the 2 long-form documentary videos.
Study what world events are getting the most views and create deep-dive analysis content.
"""

            prompt = f"""You are a YouTube content strategist for a channel called "StreamGlobal"
that creates English-language content targeting a global (primarily US) audience.

CHANNEL STRATEGY:
- Shorts (under 60 seconds) = Discovery & subscriber growth
- Long-form documentaries (10-20 minutes) = Deep-dive analysis of world events, geopolitics, current affairs = Watch time & ad revenue
- Ambient videos (1-8 hour loops: fireplace, rain, forest, ocean etc.) = Passive watch time

Here are today's top 20 trending YouTube videos in the US:

{top_20_summary}
{channel_section}
{perf_section}
{winners_section}
{viral_section}
{competitor_section}
{audience_section}
{ai_trend_section}
{world_news_section}

CHANNEL HISTORY (LAST 150 VIDEOS — DO NOT REPEAT THESE TOPICS!):
{history_text}

⛔ CRITICAL NON-REPETITION WARNING:
The following keywords/themes have BEEN OVERUSED on this channel recently. 
DO NOT suggest any more videos about these specific topics:
{saturated_text}

Create a content plan for TOMORROW with:
- 20 YouTube Shorts (under 60 seconds, fact/info style)
- 2 Long-form videos (10-20 minutes, documentary/news analysis style)
- 3 Ambient video recommendations (which ambient type to produce next)

LONG-FORM VIDEO STRATEGY (CRITICAL):
These are the channel's FLAGSHIP content — deep-dive documentaries that drive
watch time and ad revenue. NOT just news — pick from ALL trending categories.

Long-form topic selection rules:
1. MOST-WATCHED FIRST: Focus on what YouTube audiences are watching most RIGHT NOW.
   This can be world events, science, technology, history, mysteries, economics,
   space, AI, true crime, nature — whatever long-form content is trending highest.
2. WORLD EVENTS ARE GREAT BUT NOT THE ONLY OPTION: Geopolitics, wars, crises are
   good topics BUT also consider science breakthroughs, tech explainers, historical
   deep dives, unsolved mysteries, and viral documentary topics.
3. DEEP ANALYSIS: Don't just report — explain WHY it matters, the history behind it,
   what could happen next. Give viewers context they can't get elsewhere.
4. EVERGREEN ANGLE: Frame topics with lasting relevance. Instead of
   "Breaking: X happened today", use "Why X Changes Everything" or
   "The Hidden History Behind X".
5. DURATION: Each long-form video should target 15 minutes (~2100 words of narration).
   Include "15 minute" in the topic field so the scriptwriter knows the target length.
6. HIGH SEARCH VOLUME: Pick topics people are actively searching for on YouTube.
7. VARIETY: Alternate between categories — don't do 2 geopolitics videos in a row.
   Mix news, science, history, technology, mysteries across days.

Available ambient types: fireplace, forest, rain, ocean, thunderstorm, waterfall,
snow, campfire, candle, underwater, river, garden, wind, aurora, sunset, cave,
jungle, lavender_field, zen_garden, japanese_garden

STRATEGY & VARIETY RULES:
1. STRICT NON-REPETITION: Do not suggest anything even remotely similar to the topics in the history.
2. DIVERSITY IS KEY: Suggest a wide mix of niches (History, Science, Mysteries, Logic Puzzles, Nature).
3. NO OVERUSED THEMES: If we've done 'James Webb', 'Everest', or 'Dinosaurs' too much, find something entirely different.
4. FRESH ANGLES: Explore specific, mind-blowing facts rather than general overviews.

Output STRICT JSON format:
{{
    "date": "{(datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')}",
    "shorts": [
        {{
            "title": "Catchy Short Title",
            "topic": "Detailed topic description for script generation",
            "hook": "First 3 seconds hook text",
            "tags": ["tag1", "tag2", "tag3"],
            "inspired_by": "Which trending video/channel inspired this",
            "estimated_views": "low/medium/high based on trend analysis",
            "is_winner_variation": false,
            "winner_source_id": ""
        }}
    ],
    "longform": [
        {{
            "title": "Compelling Documentary Title About Current Event",
            "topic": "15 minute deep analysis of [specific world event]. Cover the background, key players, current situation, and what could happen next. Include specific facts, dates, and geopolitical context.",
            "hook": "Opening hook that grabs attention in the first 10 seconds",
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
            "inspired_by": "Which news event or trending topic inspired this",
            "estimated_views": "medium/high",
            "duration_minutes": 15
        }}
    ],
    "ambient_recommendations": [
        {{
            "type": "one of the available ambient types",
            "hours": 8,
            "reason": "Why this type would perform well right now"
        }}
    ]
}}
"""
            # ── AI generation with model fallback chain ──
            plan = None
            last_err = None
            all_gemini_exhausted = False

            # Try each Gemini model (handles per-model quota)
            for model in self.gemini_models:
                for attempt in range(2):
                    try:
                        logger.info(f"  Trying {model} (attempt {attempt+1}/2)...")
                        response = self.gemini.models.generate_content(
                            model=model,
                            contents=prompt,
                            config={"response_mime_type": "application/json"},
                        )
                        raw_text = getattr(response, "text", None)
                        if not raw_text or not raw_text.strip():
                            raise ValueError(f"{model} returned empty response")
                        plan = json.loads(raw_text)
                        break
                    except json.JSONDecodeError as je:
                        last_err = je
                        logger.warning(
                            f"{model} JSON parse failed (attempt {attempt+1}): {je}. "
                            f"Raw preview: {(raw_text or '')[:200]!r}"
                        )
                    except Exception as ge:
                        last_err = ge
                        err_str = str(ge).lower()
                        if "resource_exhausted" in err_str or "quota" in err_str or "429" in err_str:
                            logger.warning(f"  {model} credits exhausted, trying next model...")
                            break
                        logger.warning(f"{model} call failed (attempt {attempt+1}): {ge}")
                    if attempt < 1:
                        time.sleep(2)
                if plan:
                    break

            # OpenAI fallback for plan generation if all Gemini models exhausted
            if plan is None and self.oa_client:
                all_gemini_exhausted = True
                logger.warning("⚠️ All Gemini models exhausted. Trying OpenAI for plan generation...")
                try:
                    oa_response = self.oa_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                    )
                    raw_text = oa_response.choices[0].message.content
                    if raw_text and raw_text.strip():
                        plan = json.loads(raw_text)
                        logger.info("✅ OpenAI plan generation succeeded")
                except Exception as oe:
                    logger.error(f"OpenAI plan generation also failed: {oe}")
                    last_err = oe

            if plan is None:
                self._send_api_failure_alert(all_gemini_exhausted)
                raise RuntimeError(f"All AI providers failed. Last error: {last_err}")

            # Ensure longform key exists
            if "longform" not in plan:
                plan["longform"] = []

            # ── POST-GENERATION DUPLICATE FILTER ──
            if existing_titles_norm and plan.get("shorts"):
                original_count = len(plan["shorts"])
                filtered_shorts = []
                seen_in_plan = set()

                for short in plan["shorts"]:
                    norm = self._normalize_title(short.get("title", ""))
                    
                    # Check exact match against history
                    if norm in existing_titles_norm:
                        logger.info(f"  🚫 Duplicate filtered (exact): {short['title'][:50]}")
                        continue

                    # Check fuzzy match against history
                    is_dupe = False
                    norm_words = set(norm.split())
                    for existing_norm in existing_titles_norm:
                        existing_words = set(existing_norm.split())
                        if not norm_words or not existing_words:
                            continue
                        overlap = len(norm_words & existing_words)
                        ratio = overlap / min(len(norm_words), len(existing_words))
                        # Stricter: 60% overlap OR 4+ common words
                        if ratio > 0.6 or overlap >= 4:
                            logger.info(f"  🚫 Duplicate filtered (fuzzy {ratio:.0%}): {short['title'][:50]}")
                            is_dupe = True
                            break

                    if is_dupe:
                        continue

                    # Check within plan (dedup against itself)
                    if norm in seen_in_plan:
                        logger.info(f"  🚫 Duplicate filtered (self): {short['title'][:50]}")
                        continue

                    seen_in_plan.add(norm)
                    filtered_shorts.append(short)

                plan["shorts"] = filtered_shorts
                removed = original_count - len(filtered_shorts)
                if removed > 0:
                    logger.info(f"  📊 Removed {removed} duplicate Shorts from plan ({len(filtered_shorts)} remaining)")

            # ── WINNER VARIATION TRACKING ──
            # Count variations per winner and bump their counters
            winner_variation_count = 0
            if active_winners and plan.get("shorts"):
                valid_winner_ids = {w["video_id"] for w in active_winners}
                bumped_ids = set()
                for short in plan["shorts"]:
                    if short.get("is_winner_variation") and short.get("winner_source_id") in valid_winner_ids:
                        winner_variation_count += 1
                        src_id = short["winner_source_id"]
                        if src_id not in bumped_ids:
                            self.mark_winner_variation(src_id)
                            bumped_ids.add(src_id)
                logger.info(
                    f"🏆 Winner amplification: {winner_variation_count} shorts inspired by "
                    f"{len(bumped_ids)} winners"
                )

            # Add metadata
            plan["generated_at"] = datetime.utcnow().isoformat()
            plan["trending_count"] = len(trending)
            plan["channels_analyzed"] = len(seen_channels)
            plan["winner_variations_count"] = winner_variation_count
            plan["status"] = "pending"

            shorts_count = len(plan.get("shorts", []))
            ambient_recs = len(plan.get("ambient_recommendations", []))
            logger.info(f"✅ Content plan: {shorts_count} shorts + {ambient_recs} ambient recommendations")
            return plan

        except Exception as e:
            import traceback
            logger.error(f"AI plan generation failed: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.warning("⚠️ Falling back to manual plan (titles will be generic)")
            return self._manual_plan(trending, existing_titles_norm)

    def _manual_plan(self, trending: List[Dict], existing_titles_norm: set) -> Dict:
        """
        Fallback plan without AI. Builds more varied titles than the old
        'Facts About X' prefix — rotates through curiosity-gap templates.
        """
        hook_templates = [
            "The Shocking Truth About {topic}",
            "What Nobody Tells You About {topic}",
            "The Hidden Secret Of {topic}",
            "You Won't Believe This About {topic}",
            "3 Mind-Blowing Facts About {topic}",
            "The Dark Side Of {topic}",
            "Why {topic} Changed Everything",
            "This Will Change How You See {topic}",
        ]

        shorts = []
        longform = []

        for v in trending[:40]:
            norm_title = self._normalize_title(v["title"])
            if norm_title in existing_titles_norm:
                continue

            # Clean/shorten source title for use as a topic noun phrase
            raw_topic = v["title"][:50].strip().rstrip(".,!?…")
            # Strip trailing "#shorts" style hashtags from derived topic
            raw_topic = re.sub(r"#\w+", "", raw_topic).strip()
            if len(raw_topic) < 4:
                continue

            if v.get("is_shorts") and len(shorts) < 20:
                template = hook_templates[len(shorts) % len(hook_templates)]
                shorts.append({
                    "title": template.format(topic=raw_topic),
                    "topic": v["title"],
                    "hook": f"You're about to learn something shocking about {raw_topic.lower()}.",
                    "tags": v.get("tags", [])[:5],
                    "inspired_by": v["title"],
                    "estimated_views": "medium",
                    "is_winner_variation": False,
                    "winner_source_id": "",
                })
            elif not v.get("is_shorts") and len(longform) < 2:
                longform.append({
                    "title": f"Deep Dive: {raw_topic}",
                    "topic": f"15 minute deep analysis of {v['title']}. Cover the background, key context, current situation, and implications.",
                    "hook": f"What you're about to learn about {raw_topic.lower()} will change how you see the world.",
                    "tags": v.get("tags", [])[:5],
                    "inspired_by": v["title"],
                    "estimated_views": "medium",
                    "duration_minutes": 15,
                })

            if len(shorts) >= 20 and len(longform) >= 2:
                break

        return {
            "date": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "shorts": shorts,
            "longform": longform,
            "generated_at": datetime.utcnow().isoformat(),
            "trending_count": len(trending),
            "status": "pending",
            "fallback_mode": True,
        }

    def _extract_topics_from_trending(self, trending: List[Dict]) -> List[str]:
        """Extract common topics/themes from trending videos."""
        all_tags = []
        for v in trending:
            all_tags.extend(v.get("tags", []))
        tag_counts = Counter(t.lower() for t in all_tags)
        return [tag for tag, count in tag_counts.most_common(20)]

    # ──────────────────────────────────────────────────────
    # PHASE 4: EXECUTE PLAN — Produce content from plan
    # ──────────────────────────────────────────────────────

    def execute_plan(self, factory_instance, max_shorts: int = 2, max_longform: int = 0, languages: List[str] = None) -> Dict:
        """
        Read the daily plan and produce content.
        Called by morning automation workflows.
        """
        logger.info("🎬 Executing daily content plan...")

        # Quick health check before wasting time on setup
        health = self.preflight_check()
        logger.info(f"🔍 Pre-flight: Gemini={health['gemini']}, OpenAI={health['openai']}")
        if not health["healthy"]:
            logger.error("❌ ALL AI PROVIDERS DOWN — cannot produce videos")
            logger.error("   Fix: Top up Gemini credits at https://aistudio.google.com/apikey")
            logger.error("   Fix: Check OPENAI_API_KEY secret in GitHub repo settings")
            self._send_api_failure_alert(gemini_exhausted="exhausted" in health.get("gemini", ""))
            return {"error": "All AI providers unavailable. Top up Gemini credits or fix OpenAI key."}

        if not os.path.exists(self.plan_file):
            logger.error("No daily plan found. Run nightly brain first.")
            return {"error": "No plan"}

        with open(self.plan_file, "r") as f:
            plan = json.load(f)

        if plan.get("status") == "completed":
            logger.info("Plan already fully completed today")
            return {"status": "already_completed"}

        results = {"shorts_produced": 0, "longform_produced": 0, "errors": []}

        # Find pending shorts (not yet produced)
        # Reset failed/error items from previous interrupted runs if they are from today's plan
        for s in plan.get("shorts", []):
            if s.get("status") in ["failed", "error"]:
                # Only reset if we are explicitly retrying or if it was marked error in a past session
                # For now, let's just include them in pending for convenience
                pass

        pending_shorts = [s for s in plan.get("shorts", []) if s.get("status", "pending") in ["pending", "failed", "error"]]
        pending_longform = [l for l in plan.get("longform", []) if l.get("status", "pending") in ["pending", "failed", "error"]]

        logger.info(f"📋 Pending: {len(pending_shorts)} shorts, {len(pending_longform)} longform")

        # Notify start
        batch_target = min(max_shorts, len(pending_shorts))
        total_in_plan = len(plan.get("shorts", []))
        produced_so_far = sum(1 for s in plan.get("shorts", []) if s.get("status") == "produced")
        self._send_telegram(
            f"🎬 *Content Engine Başladı*\n\n"
            f"📋 Bu batch: {batch_target} Short üretilecek\n"
            f"📊 Plan durumu: {produced_so_far}/{total_in_plan} tamamlandı"
        )

        # Produce Shorts (only pending ones)
        for i, short in enumerate(pending_shorts[:max_shorts]):
            try:
                logger.info(f"\n🎬 Producing Short {i+1}: {short['title'][:50]}")
                production_id = factory_instance.run(
                    topic=short.get("topic", short["title"]),
                    languages=languages or ["en"],
                    auto_upload=True,
                    video_type="shorts",
                    mode="info",
                )
                if production_id:
                    results["shorts_produced"] += 1
                    short["status"] = "produced"
                    short["production_id"] = production_id
                else:
                    short["status"] = "failed"
                    results["errors"].append(f"Short '{short['title']}' failed (Reason: check logs)")
                    self._send_telegram(
                        f"❌ *Short Üretim Başarısız*\n\n"
                        f"*Başlık:* {short['title'][:60]}\n"
                        f"Logları kontrol et."
                    )
            except Exception as e:
                short["status"] = "error"
                results["errors"].append(f"Short '{short['title']}' error: {str(e)}")
                logger.error(f"Short production error: {e}")
                self._send_telegram(
                    f"❌ *Short Üretim Hatası*\n\n"
                    f"*Başlık:* {short['title'][:60]}\n"
                    f"*Hata:* `{str(e)[:150]}`"
                )

        # Produce Long-form (only pending ones)
        for i, lf in enumerate(pending_longform[:max_longform]):
            try:
                logger.info(f"\n🎬 Producing Long-form {i+1}: {lf['title'][:50]}")
                production_id = factory_instance.run(
                    topic=lf.get("topic", lf["title"]),
                    languages=languages or ["en"],
                    auto_upload=True,
                    video_type="long",
                    mode="info",
                )
                if production_id:
                    results["longform_produced"] += 1
                    lf["status"] = "produced"
                else:
                    lf["status"] = "failed"
            except Exception as e:
                lf["status"] = "error"
                results["errors"].append(str(e))

        # Check if all items are done
        all_shorts_done = all(s.get("status", "pending") != "pending" for s in plan.get("shorts", []))
        all_longform_done = all(l.get("status", "pending") != "pending" for l in plan.get("longform", []))

        if all_shorts_done and all_longform_done:
            plan["status"] = "completed"
            plan["completed_at"] = datetime.utcnow().isoformat()
            logger.info("✅ All plan items completed!")
        else:
            plan["status"] = "in_progress"

        plan["last_executed_at"] = datetime.utcnow().isoformat()
        plan["results"] = results

        with open(self.plan_file, "w") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Plan executed: {results['shorts_produced']} shorts, {results['longform_produced']} longform")

        # Completion notification
        now_produced = sum(1 for s in plan.get("shorts", []) if s.get("status") == "produced")
        total_shorts = len(plan.get("shorts", []))
        error_count = len(results.get("errors", []))
        status_emoji = "✅" if error_count == 0 else "⚠️"

        msg_lines = [
            f"{status_emoji} *Content Engine Bitti*\n",
            f"📹 Bu batch: {results['shorts_produced']} Short üretildi",
            f"📊 Toplam: {now_produced}/{total_shorts} tamamlandı",
        ]
        if error_count > 0:
            msg_lines.append(f"❌ Hatalar: {error_count}")
            for err in results["errors"][:3]:
                msg_lines.append(f"   • `{err[:80]}`")
        if plan.get("status") == "completed":
            msg_lines.append("\n🎉 Bugünkü plan tamamen bitti!")

        self._send_telegram("\n".join(msg_lines))

        return results

    # ──────────────────────────────────────────────────────
    # MAIN: Run full nightly pipeline
    # ──────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────
    # WINNER AMPLIFICATION (Feedback Loop)
    # ──────────────────────────────────────────────────────

    def _winners_path(self) -> str:
        return os.path.join(self.project_root, WINNERS_FILE)

    def _load_winners(self) -> List[Dict]:
        """Load persisted winner topics from disk."""
        path = self._winners_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("winners", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.warning(f"Could not load winners: {e}")
            return []

    def _save_winners(self, winners: List[Dict]):
        """Persist winner topics to disk."""
        path = self._winners_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": datetime.utcnow().isoformat(),
                    "winners": winners,
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save winners: {e}")

    def update_winners_store(self, all_videos: List[Dict]) -> Dict:
        """
        Scan the channel and update the persistent winners store.
        A video becomes a 'winner' if it exceeds:
            max(WINNER_MIN_VIEWS, WINNER_MULTIPLIER * channel_shorts_median)

        Keeps the top WINNER_STORE_MAX winners by views_per_day (freshness bias).
        """
        if not all_videos:
            return {"added": 0, "total": 0}

        shorts = [v for v in all_videos if v.get("is_shorts") and v.get("days_since_publish", 0) >= 2]
        if not shorts:
            return {"added": 0, "total": 0}

        # Dynamic threshold
        views_list = sorted([v["views"] for v in shorts])
        median = views_list[len(views_list) // 2] if views_list else 0
        threshold = max(WINNER_MIN_VIEWS, int(median * WINNER_MULTIPLIER))

        existing = self._load_winners()
        existing_ids = {w["video_id"] for w in existing}

        added = 0
        for v in shorts:
            if v["views"] < threshold:
                continue
            if v["id"] in existing_ids:
                continue
            existing.append({
                "video_id": v["id"],
                "title": v["title"],
                "views": v["views"],
                "engagement_rate": v.get("engagement_rate", 0),
                "views_per_day": v.get("views_per_day", 0),
                "tags": v.get("tags", [])[:8],
                "added_at": datetime.utcnow().isoformat(),
                "variations_generated": 0,
            })
            added += 1

        # Refresh stats on existing winners (views may have grown)
        id_to_current = {v["id"]: v for v in shorts}
        for w in existing:
            current = id_to_current.get(w["video_id"])
            if current:
                w["views"] = current["views"]
                w["views_per_day"] = current.get("views_per_day", w.get("views_per_day", 0))
                w["engagement_rate"] = current.get("engagement_rate", w.get("engagement_rate", 0))

        # Sort by views_per_day desc, keep top N
        existing.sort(key=lambda w: (w.get("views_per_day", 0), w.get("views", 0)), reverse=True)
        existing = existing[:WINNER_STORE_MAX]

        self._save_winners(existing)

        logger.info(
            f"🏆 Winners store: +{added} new, {len(existing)} total "
            f"(threshold: {threshold} views, median: {median})"
        )
        return {
            "added": added,
            "total": len(existing),
            "threshold": threshold,
            "median": median,
        }

    def get_active_winners(self, limit: int = 10) -> List[Dict]:
        """
        Return top winners that haven't been amplified too many times yet.
        """
        winners = self._load_winners()
        active = [w for w in winners if w.get("variations_generated", 0) < WINNER_MAX_VARIATIONS]
        return active[:limit]

    def mark_winner_variation(self, winner_video_id: str):
        """Increment variation counter so the same winner isn't re-used forever."""
        winners = self._load_winners()
        changed = False
        for w in winners:
            if w.get("video_id") == winner_video_id:
                w["variations_generated"] = w.get("variations_generated", 0) + 1
                changed = True
                break
        if changed:
            self._save_winners(winners)

    # ──────────────────────────────────────────────────────
    # PERFORMANCE REVIEW (Feedback Loop)
    # ──────────────────────────────────────────────────────

    def review_recent_performance(self) -> Dict:
        """
        Review performance of videos uploaded in the last 48 hours.
        Returns insights to feed into the next content plan.
        """
        logger.info("📊 Reviewing recent video performance (48h)...")
        try:
            from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
            analytics = YouTubeAnalyticsAgent(youtube_service=self.youtube)
            videos = analytics.get_all_videos(max_results=50)

            recent = [v for v in videos if v.get("days_since_publish", 999) <= 2]

            if not recent:
                logger.info("  No videos uploaded in last 48 hours")
                return {"status": "no_recent_videos"}

            winners = [v for v in recent if v.get("views", 0) > 100]
            losers = [v for v in recent if v.get("views", 0) < 10 and v.get("days_since_publish", 0) >= 1]

            avg_views = sum(v.get("views", 0) for v in recent) / max(len(recent), 1)
            best = sorted(recent, key=lambda x: x.get("views", 0), reverse=True)[:3]

            review = {
                "total_recent": len(recent),
                "winners_count": len(winners),
                "losers_count": len(losers),
                "avg_views_48h": round(avg_views, 1),
                "best_topics": [v.get("title", "")[:60] for v in best],
                "best_views": [v.get("views", 0) for v in best],
                "winner_titles": [v.get("title", "") for v in winners],
                "loser_titles": [v.get("title", "") for v in losers[:5]],
            }

            logger.info(f"  📈 Recent: {len(recent)} videos | Winners: {len(winners)} | Losers: {len(losers)} | Avg Views: {avg_views:.0f}")
            return review

        except Exception as e:
            logger.warning(f"  Performance review failed: {e}")
            return {"status": "error", "error": str(e)}

    # ──────────────────────────────────────────────────────
    # DEEP US TRENDING (chart + search + niche + competitors)
    # ──────────────────────────────────────────────────────

    def discover_trending_deep(self, count: int = 100) -> Dict:
        """
        Deep US-only trending analysis using ALL YouTube API capabilities:
        1. mostPopular chart (existing)
        2. search.list — find viral Shorts by niche keywords
        3. Competitor channel monitoring — track what top channels upload
        4. Comment mining — extract audience desires from viral video comments
        
        Returns dict with trending videos + viral shorts + competitor insights
        """
        logger.info("🇺🇸 Deep US Trending Discovery...")
        result = {
            "trending": [],
            "viral_shorts": [],
            "world_news_videos": [],
            "competitor_insights": [],
            "audience_desires": [],
        }

        # ── STAGE 1: Standard trending chart ──
        result["trending"] = self.discover_trending(region="US", count=count)
        logger.info(f"  📊 Chart trending: {len(result['trending'])} videos")

        # ── STAGE 2: AI-Powered Niche Trends ──
        try:
            from src.agents.trend_agent import TrendAgent
            trend_agent = TrendAgent()
            result["ai_trends"] = trend_agent.get_trending_topics(region="USA", count=15)
            logger.info(f"  🤖 AI Trends found: {len(result.get('ai_trends', []))}")
        except Exception as e:
            logger.warning(f"  TrendAgent failed: {e}")
            result["ai_trends"] = []

        # ── STAGE 2b: Search for viral Shorts by niche ──
        result["viral_shorts"] = self._search_viral_shorts()
        logger.info(f"  🔥 Viral Shorts found: {len(result['viral_shorts'])}")

        # ── STAGE 2c: World news / current events long-form discovery ──
        result["world_news_videos"] = self._search_world_news_videos()
        logger.info(f"  🌍 World news videos found: {len(result['world_news_videos'])}")

        # ── STAGE 3: Competitor monitoring ──
        result["competitor_insights"] = self._monitor_competitors()
        logger.info(f"  🔎 Competitor insights: {len(result['competitor_insights'])} channels")

        # ── STAGE 4: Comment mining from top viral videos ──
        top_viral_ids = [v["id"] for v in result["trending"][:5]]
        result["audience_desires"] = self._mine_comments(top_viral_ids)
        logger.info(f"  💬 Audience desires: {len(result['audience_desires'])} insights")

        return result

    def _search_viral_shorts(self) -> List[Dict]:
        """
        Use search.list to find recent viral Shorts in our niche categories.
        This catches viral content that doesn't appear on the mostPopular chart.
        """
        if not self.yt_public:
            return []

        # Our content niches — search for what's working NOW
        niche_queries = [
            "amazing facts you didn't know",
            "psychology facts about human behavior",
            "science facts that will blow your mind",
            "history facts nobody told you",
            "space facts universe",
            "animal facts wildlife",
            "country facts geography",
            "mystery unsolved creepy",
            "technology AI future",
            "ocean deep sea facts",
            "did you know facts",
            "top 5 facts",
        ]

        viral_shorts = []
        seen_ids = set()

        for query in niche_queries:
            try:
                response = self.yt_public.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    videoDuration="short",          # Shorts only
                    order="viewCount",              # Sort by views
                    publishedAfter=(
                        (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    ),
                    regionCode="US",
                    relevanceLanguage="en",
                    maxResults=5,
                ).execute()

                video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
                if not video_ids:
                    continue

                # Get full stats
                stats_response = self.yt_public.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(video_ids),
                ).execute()

                for item in stats_response.get("items", []):
                    vid_id = item["id"]
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    stats = item.get("statistics", {})
                    snippet = item.get("snippet", {})
                    content = item.get("contentDetails", {})
                    dur = self._parse_iso_duration(content.get("duration", "PT0S"))

                    if dur > 180:  # Skip non-shorts
                        continue

                    views = int(stats.get("viewCount", 0))
                    likes = int(stats.get("likeCount", 0))
                    comments = int(stats.get("commentCount", 0))

                    if views < 10000:  # Only truly viral
                        continue

                    viral_shorts.append({
                        "id": vid_id,
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "channel_id": snippet.get("channelId", ""),
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
                        "tags": snippet.get("tags", [])[:10],
                        "duration_seconds": dur,
                        "search_query": query,
                        "published_at": snippet.get("publishedAt", ""),
                        "description": snippet.get("description", "")[:200],
                    })

            except Exception as e:
                logger.warning(f"  ⚠️ Search '{query[:30]}' failed: {e}")

        # Sort by views
        viral_shorts.sort(key=lambda v: v["views"], reverse=True)
        return viral_shorts[:30]  # Top 30

    def _search_world_news_videos(self) -> List[Dict]:
        """
        Search for high-performing long-form videos across ALL trending categories.
        Not just news — includes science, history, technology, documentaries, etc.
        """
        if not self.yt_public:
            return []

        news_queries = [
            # World news & geopolitics
            "world news today explained",
            "geopolitics analysis",
            "global conflict update",
            "breaking world news documentary",
            "economic crisis explained",
            # Science & technology
            "science documentary 2024",
            "technology explained",
            "space discovery documentary",
            "AI technology explained",
            # History & mysteries
            "history documentary",
            "ancient mysteries explained",
            "unsolved mysteries documentary",
            # Popular trending long-form
            "most watched documentary this week",
            "trending explained video",
            "deep dive analysis",
        ]

        news_videos = []
        seen_ids = set()

        for query in news_queries:
            try:
                response = self.yt_public.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    videoDuration="medium",  # 4-20 minutes
                    order="viewCount",
                    publishedAfter=(
                        (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    ),
                    regionCode="US",
                    relevanceLanguage="en",
                    maxResults=5,
                ).execute()

                video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
                if not video_ids:
                    continue

                stats_response = self.yt_public.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(video_ids),
                ).execute()

                for item in stats_response.get("items", []):
                    vid_id = item["id"]
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    stats = item.get("statistics", {})
                    snippet = item.get("snippet", {})
                    content = item.get("contentDetails", {})
                    dur = self._parse_iso_duration(content.get("duration", "PT0S"))

                    if dur < 300 or dur > 2400:  # 5-40 min only
                        continue

                    views = int(stats.get("viewCount", 0))
                    if views < 5000:
                        continue

                    news_videos.append({
                        "id": vid_id,
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "views": views,
                        "likes": int(stats.get("likeCount", 0)),
                        "duration_seconds": dur,
                        "tags": snippet.get("tags", [])[:10],
                        "search_query": query,
                        "published_at": snippet.get("publishedAt", ""),
                        "description": snippet.get("description", "")[:200],
                    })

            except Exception as e:
                logger.warning(f"  ⚠️ News search '{query[:30]}' failed: {e}")

        news_videos.sort(key=lambda v: v["views"], reverse=True)
        return news_videos[:20]

    def _monitor_competitors(self) -> List[Dict]:
        """
        Monitor competitor channels that create similar Shorts content.
        Tracks their recent uploads to see what's working.
        """
        if not self.yt_public:
            return []

        # Top fact/educational Shorts channels to monitor
        competitor_handles = [
            "@MrBeast", "@FactsVerse", "@BrightSide",
            "@ThoughtFactory", "@ScienceChannel",
        ]

        insights = []

        for handle in competitor_handles:
            try:
                # Search for channel by handle
                ch_response = self.yt_public.search().list(
                    part="snippet",
                    q=handle,
                    type="channel",
                    maxResults=1,
                ).execute()

                if not ch_response.get("items"):
                    continue

                ch_id = ch_response["items"][0]["snippet"]["channelId"]
                ch_name = ch_response["items"][0]["snippet"]["channelTitle"]

                # Get their recent Shorts
                vids_response = self.yt_public.search().list(
                    part="snippet",
                    channelId=ch_id,
                    type="video",
                    videoDuration="short",
                    order="date",
                    publishedAfter=(
                        (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    ),
                    maxResults=5,
                ).execute()

                recent_titles = []
                for item in vids_response.get("items", []):
                    recent_titles.append(item["snippet"]["title"])

                if recent_titles:
                    insights.append({
                        "channel": ch_name,
                        "channel_id": ch_id,
                        "recent_titles": recent_titles,
                    })

            except Exception as e:
                logger.warning(f"  ⚠️ Competitor {handle} failed: {e}")

        return insights

    def _mine_comments(self, video_ids: List[str], max_per_video: int = 20) -> List[str]:
        """
        Mine top comments from viral videos to understand audience desires.
        Returns a list of comment themes/requests.
        """
        if not self.yt_public or not video_ids:
            return []

        all_comments = []

        for vid_id in video_ids[:5]:
            try:
                response = self.yt_public.commentThreads().list(
                    part="snippet",
                    videoId=vid_id,
                    order="relevance",
                    maxResults=max_per_video,
                    textFormat="plainText",
                ).execute()

                for item in response.get("items", []):
                    comment = item["snippet"]["topLevelComment"]["snippet"]
                    text = comment.get("textDisplay", "")
                    likes = comment.get("likeCount", 0)

                    # Only high-engagement comments (what audiences want)
                    if likes >= 5 and len(text) > 10:
                        all_comments.append(text[:150])

            except Exception as e:
                logger.debug(f"  Comment mining for {vid_id} failed: {e}")

        return all_comments[:20]

    # ──────────────────────────────────────────────────────
    # SEO KEYWORD ENRICHMENT
    # ──────────────────────────────────────────────────────

    def enrich_plan_with_seo(self, plan: Dict) -> Dict:
        """
        Enrich each planned video with YouTube Search Suggest keywords.
        Optimizes titles and adds SEO tags for better discoverability.
        """
        from src.services.youtube_service import YouTubeService

        items = plan.get("shorts", []) + plan.get("longform", [])
        enriched_count = 0

        for item in items:
            topic = item.get("topic", item.get("title", ""))
            if not topic:
                continue

            try:
                suggestions = YouTubeService.get_youtube_suggestions(topic)
                if suggestions:
                    # Add SEO tags
                    item["seo_keywords"] = suggestions[:8]
                    # Optimize title if not already optimized
                    if "optimized_title" not in item:
                        item["optimized_title"] = YouTubeService.optimize_title_with_keywords(
                            item.get("title", topic), suggestions
                        )
                    enriched_count += 1
            except Exception as e:
                logger.warning(f"  SEO enrichment failed for '{topic[:30]}': {e}")

        logger.info(f"  🔎 SEO enriched: {enriched_count}/{len(items)} videos")
        return plan

    # ──────────────────────────────────────────────────────
    # VIDEO SCORE CALCULATOR
    # ──────────────────────────────────────────────────────

    @staticmethod
    def calculate_video_score(video: Dict) -> int:
        """
        Calculate a 0-100 performance score for a video.
        Used to evaluate content strategy effectiveness.
        """
        score = 0
        views = video.get("views", 0)
        engagement = video.get("engagement_rate", 0)
        days = video.get("days_since_publish", 30)
        views_per_day = views / max(days, 1)

        # Views (max 30 points)
        if views > 1000: score += 30
        elif views > 500: score += 25
        elif views > 100: score += 20
        elif views > 50: score += 15
        elif views > 10: score += 10
        elif views > 0: score += 5

        # Engagement (max 25 points)
        if engagement > 10: score += 25
        elif engagement > 5: score += 20
        elif engagement > 2: score += 15
        elif engagement > 1: score += 10

        # Views per day momentum (max 20 points)
        if views_per_day > 50: score += 20
        elif views_per_day > 20: score += 15
        elif views_per_day > 5: score += 10

        # Freshness bonus (max 15 points)
        if days < 3 and views > 50: score += 15
        elif days < 7 and views > 100: score += 10

        # Consistency bonus (max 10 points)
        if views_per_day > 10 and days > 7: score += 10

        return min(score, 100)

    # ──────────────────────────────────────────────────────
    # MAIN: Run full nightly pipeline
    # ──────────────────────────────────────────────────────

    def run_nightly(self, dry_run: bool = False) -> Dict:
        """
        Run the complete nightly pipeline:
        0. Review recent performance (feedback loop)
        1. Cleanup underperformers
        2. Discover trending (multi-region)
        3. Generate tomorrow's content plan
        4. Enrich plan with SEO keywords
        """
        logger.info("=" * 60)
        logger.info("🧠 NIGHTLY BRAIN v2.1 — Starting...")
        logger.info(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        logger.info(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("=" * 60)

        # ─── PRE-FLIGHT: Check AI providers ───
        health = self.preflight_check()
        logger.info(f"🔍 Pre-flight: Gemini={health['gemini']}, OpenAI={health['openai']}")
        if not health["healthy"]:
            logger.error("❌ ALL AI PROVIDERS DOWN — pipeline cannot generate content")
            logger.error("   Fix: Top up Gemini credits or check OpenAI API key")
            self._send_api_failure_alert(gemini_exhausted="exhausted" in health.get("gemini", ""))

        nightly_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "api_health": health,
        }

        # ─── PHASE 0: Performance Review (NEW!) ───
        logger.info("\n" + "─" * 40)
        logger.info("📊 PHASE 0: Performance Review (48h Feedback)")
        logger.info("─" * 40)
        performance = self.review_recent_performance()
        nightly_report["performance_review"] = performance

        # ─── PHASE 1: Cleanup ───
        logger.info("\n" + "─" * 40)
        logger.info("🗑️ PHASE 1: Channel Cleanup")
        logger.info("─" * 40)
        cleanup = self.cleanup_channel(dry_run=dry_run)
        nightly_report["cleanup"] = {
            "unlisted": cleanup.get("unlisted_count", 0),
            "deleted": cleanup.get("deleted_count", 0),
            "failed": cleanup.get("failed_count", 0),
            "kept": cleanup.get("kept_count", 0),
            "thresholds": cleanup.get("thresholds_used", {}),
        }

        # ─── PHASE 2: Deep US Trending Discovery ───
        logger.info("\n" + "─" * 40)
        logger.info("🇺🇸 PHASE 2: Deep US Trending Discovery")
        logger.info("─" * 40)
        deep_trends = self.discover_trending_deep(count=100)
        trending = deep_trends["trending"]
        nightly_report["trending"] = {
            "found": len(trending),
            "viral_shorts_found": len(deep_trends.get("viral_shorts", [])),
            "world_news_found": len(deep_trends.get("world_news_videos", [])),
            "competitors_analyzed": len(deep_trends.get("competitor_insights", [])),
            "comments_mined": len(deep_trends.get("audience_desires", [])),
            "top_5": [
                {"title": v["title"][:60], "views": v["views"], "category": v["category"]}
                for v in trending[:5]
            ],
            "top_viral_shorts": [
                {"title": v["title"][:60], "views": v["views"], "query": v.get("search_query", "")}
                for v in deep_trends.get("viral_shorts", [])[:5]
            ],
        }

        # ─── PHASE 3: Ambient Performance Analysis ───
        logger.info("\n" + "─" * 40)
        logger.info("🔥 PHASE 3: Ambient Video Performance Analysis")
        logger.info("─" * 40)

        # Get existing channel videos to avoid duplicates
        from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
        analytics = YouTubeAnalyticsAgent(youtube_service=self.youtube)
        channel_videos = analytics.get_all_videos(max_results=200)

        # ─── WINNER AMPLIFICATION: scan channel for proven winners ───
        winners_stats = self.update_winners_store(channel_videos)
        active_winners = self.get_active_winners(limit=10)
        nightly_report["winners"] = {
            "added": winners_stats.get("added", 0),
            "total": winners_stats.get("total", 0),
            "threshold": winners_stats.get("threshold", 0),
            "median": winners_stats.get("median", 0),
            "active": len(active_winners),
            "top": [
                {
                    "video_id": w["video_id"],
                    "title": w["title"][:60],
                    "views": w["views"],
                    "views_per_day": round(w.get("views_per_day", 0), 1),
                    "variations_generated": w.get("variations_generated", 0),
                }
                for w in active_winners[:5]
            ],
        }

        # ─── PEAK HOUR DETECTION: find best UTC upload hours ───
        peak_hours = analytics.get_peak_upload_hours(
            videos=channel_videos, video_type="shorts"
        )
        peak_path = os.path.join(self.project_root, PEAK_HOURS_FILE)
        os.makedirs(os.path.dirname(peak_path), exist_ok=True)
        with open(peak_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.utcnow().isoformat(),
                **peak_hours,
            }, f, indent=2, ensure_ascii=False)
        nightly_report["peak_hours"] = {
            "utc": peak_hours.get("peak_hours_utc", []),
            "source": peak_hours.get("source"),
            "samples": peak_hours.get("sample_count", 0),
        }

        # ─── RETENTION INSIGHTS: fetch drop-off from YouTube Analytics v2 ───
        retention = analytics.get_retention_insights(videos=channel_videos)
        retention_path = os.path.join(self.project_root, RETENTION_FILE)
        with open(retention_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.utcnow().isoformat(),
                **retention,
            }, f, indent=2, ensure_ascii=False)
        nightly_report["retention"] = {
            "avg_pct": retention.get("avg_view_percentage", 0),
            "avg_dur_sec": retention.get("avg_view_duration_sec", 0),
            "source": retention.get("source"),
            "video_count": retention.get("video_count", 0),
        }

        # Analyze ambient video performance
        ambient_analysis = analytics.analyze_ambient_performance()
        nightly_report["ambient_analysis"] = {
            "total_ambient": ambient_analysis.get("total_ambient", 0),
            "total_views": ambient_analysis.get("total_ambient_views", 0),
            "top_type": ambient_analysis.get("top_type"),
            "worst_type": ambient_analysis.get("worst_type"),
            "type_rankings": ambient_analysis.get("type_rankings", [])[:5],
        }

        # ─── PHASE 4: Generate Plan ───
        logger.info("\n" + "─" * 40)
        logger.info("📝 PHASE 4: Content Planning (Shorts + Ambient Recs)")
        logger.info("─" * 40)

        plan = self.generate_content_plan(
            trending, channel_videos,
            performance_review=performance,
            viral_shorts=deep_trends.get("viral_shorts", []),
            competitor_insights=deep_trends.get("competitor_insights", []),
            audience_desires=deep_trends.get("audience_desires", []),
            ai_trends=deep_trends.get("ai_trends", []),
            active_winners=active_winners,
            world_news_videos=deep_trends.get("world_news_videos", []),
        )

        # ─── PHASE 5: SEO Enrichment ───
        logger.info("\n" + "─" * 40)
        logger.info("🔎 PHASE 5: SEO Keyword Enrichment")
        logger.info("─" * 40)
        plan = self.enrich_plan_with_seo(plan)

        # Save plan
        os.makedirs(os.path.dirname(self.plan_file), exist_ok=True)
        with open(self.plan_file, "w") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Plan saved: {self.plan_file}")

        nightly_report["plan"] = {
            "shorts_planned": len(plan.get("shorts", [])),
            "longform_planned": len(plan.get("longform", [])),
            "ambient_recommendations": plan.get("ambient_recommendations", []),
            "winner_variations_count": plan.get("winner_variations_count", 0),
            "shorts": [s.get("title", "?")[:50] for s in plan.get("shorts", [])],
            "longform": [l.get("title", "?")[:60] for l in plan.get("longform", [])],
        }

        # Save nightly log
        log_file = os.path.join(
            self.log_dir,
            f"nightly_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(log_file, "w") as f:
            json.dump(nightly_report, f, indent=2, ensure_ascii=False)

        # Print summary
        self._print_summary(nightly_report, plan)

        # Telegram notification
        self._send_nightly_summary_telegram(nightly_report, plan)

        return nightly_report

    def _print_summary(self, report: Dict, plan: Dict):
        """Print nightly summary."""
        print("\n" + "=" * 60)
        print("🧠 NIGHTLY BRAIN SUMMARY")
        print("=" * 60)

        # Performance review
        perf = report.get("performance_review", {})
        if perf and perf.get("status") != "no_recent_videos":
            print(f"\n📈 Performance (48h):")
            print(f"   Avg views: {perf.get('avg_views_48h', 0)}")
            print(f"   Winners: {perf.get('winners_count', 0)} | Losers: {perf.get('losers_count', 0)}")

        cleanup = report.get("cleanup", {})
        print(f"\n🗑️ Cleanup:")
        print(f"   Deleted: {cleanup.get('deleted', 0)}")
        print(f"   Failed: {cleanup.get('failed', 0)}")
        print(f"   Kept: {cleanup.get('kept', 0)}")

        winners = report.get("winners", {})
        if winners.get("total", 0) > 0:
            print(f"\n🏆 Winner Amplification:")
            print(f"   Store: {winners.get('total', 0)} total (+{winners.get('added', 0)} new)")
            print(f"   Threshold: {winners.get('threshold', 0)} views (median: {winners.get('median', 0)})")
            print(f"   Active for variations: {winners.get('active', 0)}")
            for w in winners.get("top", [])[:3]:
                print(f"   🏆 {w['title']} ({w['views']:,} views, x{w['variations_generated']} used)")

        trending = report.get("trending", {})
        print(f"\n🇺🇸 Deep US Trending:")
        print(f"   Chart trending: {trending.get('found', 0)}")
        print(f"   Viral Shorts: {trending.get('viral_shorts_found', 0)}")
        print(f"   World News: {trending.get('world_news_found', 0)}")
        print(f"   Competitors: {trending.get('competitors_analyzed', 0)}")
        print(f"   Comments mined: {trending.get('comments_mined', 0)}")
        for t in trending.get("top_5", []):
            print(f"   🔥 {t['title'][:50]} ({t['views']:,} views)")
        for s in trending.get("top_viral_shorts", []):
            print(f"   ⚡ {s['title'][:50]} ({s['views']:,} views) [{s.get('query', '')}]")

        plan_info = report.get("plan", {})
        print(f"\n📝 Tomorrow's Plan:")
        print(f"   Shorts: {plan_info.get('shorts_planned', 0)}")
        for s in plan_info.get("shorts", []):
            print(f"   📹 {s}")

        longform_titles = plan_info.get("longform", [])
        if longform_titles:
            print(f"   Long-form: {plan_info.get('longform_planned', 0)}")
            for lf in longform_titles:
                print(f"   🎬 {lf}")

        # Ambient analysis
        ambient = report.get("ambient_analysis", {})
        if ambient.get("total_ambient", 0) > 0:
            print(f"\n🔥 Ambient Performance:")
            print(f"   Total ambient videos: {ambient.get('total_ambient', 0)}")
            print(f"   Total ambient views: {ambient.get('total_views', 0):,}")
            print(f"   🏆 Best type: {ambient.get('top_type', 'N/A')}")
            for r in ambient.get("type_rankings", [])[:3]:
                print(f"   📊 {r['type'].upper()}: {r['total_views']:,} views ({r['video_count']} videos, {r['avg_views_per_day']} vpd)")

        # Ambient recommendations
        ambient_recs = plan_info.get("ambient_recommendations", [])
        if ambient_recs:
            print(f"\n🎯 Ambient Recommendations:")
            for rec in ambient_recs:
                print(f"   🔥 {rec.get('type', '?')} ({rec.get('hours', 8)}h) — {rec.get('reason', '')[:60]}")

        print("\n" + "=" * 60)

    def _send_nightly_summary_telegram(self, report: Dict, plan: Dict):
        """Send nightly brain summary to Telegram."""
        cleanup = report.get("cleanup", {})
        perf = report.get("performance_review", {})
        winners = report.get("winners", {})
        trending = report.get("trending", {})
        plan_info = report.get("plan", {})
        peak = report.get("peak_hours", {})
        retention = report.get("retention", {})

        lines = ["🧠 *Nightly Brain Tamamlandı!*\n"]

        # Performance
        if perf and perf.get("status") != "no_recent_videos":
            lines.append(f"📈 *Son 48s:* Ort. {perf.get('avg_views_48h', 0):.0f} izlenme")
            best = perf.get("best_topics", [])
            if best:
                lines.append(f"   🏆 En iyi: {best[0][:45]}")

        # Cleanup
        deleted = cleanup.get("deleted", 0)
        unlisted = cleanup.get("unlisted", 0)
        kept = cleanup.get("kept", 0)
        if deleted or unlisted:
            lines.append(f"🗑 *Temizlik:* {deleted} silindi, {unlisted} gizlendi, {kept} kaldı")
        else:
            lines.append(f"🗑 *Temizlik:* Değişiklik yok ({kept} video)")

        # Winners
        if winners.get("total", 0) > 0:
            lines.append(
                f"🏆 *Kazananlar:* {winners.get('total', 0)} toplam "
                f"(+{winners.get('added', 0)} yeni, eşik: {winners.get('threshold', 0)} izlenme)"
            )

        # Trending
        lines.append(
            f"🇺🇸 *Trend:* {trending.get('found', 0)} chart + "
            f"{trending.get('viral_shorts_found', 0)} viral shorts + "
            f"{trending.get('world_news_found', 0)} haber"
        )

        # Peak hours
        peak_utc = peak.get("utc", [])
        if peak_utc:
            lines.append(f"⏰ *Peak saatler (UTC):* {', '.join(str(h) for h in peak_utc)}")

        # Retention
        if retention.get("source") == "analytics_api":
            lines.append(
                f"📊 *Retention:* %{retention.get('avg_pct', 0):.0f} ort. "
                f"({retention.get('avg_dur_sec', 0):.0f}s)"
            )

        # Plan
        shorts_count = plan_info.get("shorts_planned", 0)
        winner_vars = plan_info.get("winner_variations_count", 0)
        is_fallback = plan.get("fallback_mode", False)
        plan_label = "Fallback" if is_fallback else "AI"

        longform_count = plan_info.get("longform_planned", 0)
        lines.append(f"\n📝 *Yarının Planı ({plan_label}):* {shorts_count} Shorts + {longform_count} Uzun Video")
        if winner_vars:
            lines.append(f"   🏆 {winner_vars} tanesi kazanan varyasyonu")

        # Longform titles
        longform_titles = plan_info.get("longform", [])
        if longform_titles:
            lines.append(f"\n🎬 *Uzun Videolar:*")
            for lf in longform_titles:
                lines.append(f"   🌍 {lf}")

        # First 8 shorts titles
        shorts_titles = plan_info.get("shorts", [])[:8]
        if shorts_titles:
            lines.append(f"\n📹 *Shorts:*")
        for i, title in enumerate(shorts_titles, 1):
            lines.append(f"   {i}. {title}")
        if shorts_count > 8:
            lines.append(f"   ... ve {shorts_count - 8} tane daha")

        # Ambient recs
        ambient_recs = plan_info.get("ambient_recommendations", [])
        if ambient_recs:
            recs_text = ", ".join(r.get("type", "?") for r in ambient_recs)
            lines.append(f"\n🎧 *Ambient önerisi:* {recs_text}")

        # API health
        health = report.get("api_health", {})
        if health:
            gemini_status = health.get("gemini", "?")
            openai_status = health.get("openai", "?")
            if not health.get("healthy", True):
                lines.append(f"\n⚠️ *API Durumu:* Gemini={gemini_status}, OpenAI={openai_status}")

        self._send_telegram("\n".join(lines))

    def _send_telegram(self, message: str):
        """Send a Telegram notification."""
        try:
            import requests as req
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id_file = os.path.join(self.project_root, "data", "telegram_chat_id.txt")
            if not token or not os.path.exists(chat_id_file):
                return
            with open(chat_id_file, "r") as f:
                chat_id = f.read().strip()
            if not chat_id:
                return
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        except Exception:
            pass

    def _send_api_failure_alert(self, gemini_exhausted: bool = False):
        """Send Telegram alert when AI providers are down."""
        if gemini_exhausted:
            msg = (
                "🚨 *PIPELINE DOWN — API Credits Exhausted*\n\n"
                "Gemini: `RESOURCE_EXHAUSTED` (all models)\n"
                "OpenAI: Connection failed\n\n"
                "📋 *Fix:*\n"
                "1. Gemini → https://aistudio.google.com/apikey (top up credits)\n"
                "2. OpenAI → Check `OPENAI_API_KEY` secret in GitHub\n"
                "3. Re-run nightly brain manually after fixing"
            )
        else:
            msg = (
                "⚠️ *Nightly Brain — Plan Generation Failed*\n\n"
                "Both Gemini and OpenAI failed to generate content plan.\n"
                "Check API keys and credits."
            )
        self._send_telegram(msg)

    def preflight_check(self) -> Dict:
        """Quick health check on AI providers before running the full pipeline."""
        results = {"gemini": "unknown", "openai": "unknown", "healthy": False}

        if self.gemini:
            for model in self.gemini_models:
                try:
                    response = self.gemini.models.generate_content(
                        model=model, contents="Say OK"
                    )
                    if getattr(response, "text", ""):
                        results["gemini"] = f"ok ({model})"
                        break
                except Exception as e:
                    err_str = str(e).lower()
                    if "resource_exhausted" in err_str or "429" in err_str:
                        results["gemini"] = f"credits_exhausted ({model})"
                        continue
                    results["gemini"] = f"error: {str(e)[:80]}"
                    break
        else:
            results["gemini"] = "not_configured"

        if self.oa_client:
            try:
                oa_resp = self.oa_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Say OK"}],
                    max_tokens=5,
                )
                if oa_resp.choices:
                    results["openai"] = "ok"
            except Exception as e:
                results["openai"] = f"error: {str(e)[:80]}"
        else:
            results["openai"] = "not_configured"

        results["healthy"] = (
            results["gemini"].startswith("ok") or results["openai"] == "ok"
        )
        return results

    def _parse_iso_duration(self, duration: str) -> int:
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
