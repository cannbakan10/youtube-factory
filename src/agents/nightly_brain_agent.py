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

# Turkish detection patterns
TURKISH_CHARS = set("çğıöşüÇĞİÖŞÜ")
TURKISH_KEYWORDS = [
    "hakkında", "neden", "nasıl", "dünyanın", "türkiye", "bilmediğin",
    "şok", "inanılmaz", "edici", "gerçekler", "sırrı", "gizemi",
    "tarihinin", "osmanlı", "şehzade", "ölümcül", "zengin", "meslek",
    "pasaport", "savaş", "fethi", "hamlesi", "irkı", "kediler",
    "bilgiler", "olacaksınız", "insanlık", "öldü", "oluyor",
]

# Minimum performance thresholds
MIN_SHORTS_VIEWS_7D = 10       # Minimum views after 7 days
MIN_SHORTS_VIEWS_14D = 25      # Minimum views after 14 days
MIN_SHORTS_VIEWS_30D = 50      # Minimum views after 30 days
MIN_LONGFORM_VIEWS_14D = 15    # Minimum views for longform after 14 days
DUPLICATE_SIMILARITY_THRESHOLD = 0.70


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

        # Gemini AI
        self.gemini = None
        try:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.gemini = genai.Client(api_key=api_key)
                logger.info("🧠 Nightly Brain: Gemini AI connected")
        except Exception:
            logger.info("Nightly Brain: Running without Gemini")

    # ──────────────────────────────────────────────────────
    # PHASE 1: CLEANUP — Delete underperformers
    # ──────────────────────────────────────────────────────

    def cleanup_channel(self, dry_run: bool = False) -> Dict:
        """
        Delete underperforming and Turkish-language videos.
        Returns cleanup report.
        """
        if not self.youtube or not self.youtube.youtube:
            logger.error("YouTube service not available for cleanup")
            return {"error": "No YouTube service"}

        logger.info("🗑️ Phase 1: Channel Cleanup Starting...")

        # Import analytics to get all videos
        from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
        analytics = YouTubeAnalyticsAgent(youtube_service=self.youtube)
        videos = analytics.get_all_videos()

        if not videos:
            return {"error": "No videos found"}

        to_delete = []
        to_keep = []

        for v in videos:
            delete_reasons = []

            # Rule 1: Turkish content — DELETE ALL (except high performers)
            if self._is_turkish(v["title"]):
                if v["views"] >= 1000:
                    # High-performing Turkish video — keep but mark for review
                    # These still drive engagement, don't auto-delete
                    pass
                else:
                    delete_reasons.append("Turkish content (channel is English-only)")

            # Rule 2: Zero views after 7+ days
            if v["views"] == 0 and v["days_since_publish"] > 7:
                delete_reasons.append(f"Zero views after {v['days_since_publish']} days")

            # Rule 3: Very low views for shorts
            if v["is_shorts"] and v["days_since_publish"] > 7:
                if v["views"] < MIN_SHORTS_VIEWS_7D:
                    delete_reasons.append(f"Only {v['views']} views after 7+ days (min: {MIN_SHORTS_VIEWS_7D})")

            if v["is_shorts"] and v["days_since_publish"] > 14:
                if v["views"] < MIN_SHORTS_VIEWS_14D:
                    delete_reasons.append(f"Only {v['views']} views after 14+ days (min: {MIN_SHORTS_VIEWS_14D})")

            if v["is_shorts"] and v["days_since_publish"] > 30:
                if v["views"] < MIN_SHORTS_VIEWS_30D:
                    delete_reasons.append(f"Only {v['views']} views after 30+ days (min: {MIN_SHORTS_VIEWS_30D})")

            # Rule 4: Low views for longform
            if not v["is_shorts"] and v["days_since_publish"] > 14:
                if v["views"] < MIN_LONGFORM_VIEWS_14D:
                    delete_reasons.append(f"Longform with only {v['views']} views after 14+ days")

            # Rule 5: Don't delete recent videos (< 3 days)
            if v["days_since_publish"] < 3:
                delete_reasons = []  # Too new to judge

            if delete_reasons:
                to_delete.append({**v, "delete_reasons": delete_reasons})
            else:
                to_keep.append(v)

        # Find duplicates among kept videos
        duplicates = self._find_duplicates(to_keep)
        for dup in duplicates:
            to_delete.append({
                **dup["delete_video"],
                "delete_reasons": [f"Duplicate of '{dup['keep_video']['title'][:40]}' ({dup['similarity']}% similar)"]
            })

        logger.info(f"📊 Cleanup summary: {len(to_delete)} to delete, {len(to_keep)} to keep")

        # Execute deletions
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
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"  ❌ Failed to delete {v['id']}: {e}")
                    failed.append({**v, "error": str(e)})

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_videos": len(videos),
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "kept_count": len(to_keep),
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

        logger.info(f"✅ Cleanup complete: {len(deleted)} deleted, {len(failed)} failed, {len(to_keep)} kept")
        return report

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

    def generate_content_plan(self, trending: List[Dict], channel_videos: List[Dict] = None) -> Dict:
        """
        Analyze trending videos and create a content plan for tomorrow.
        Uses Gemini AI to identify the best topics to create content about.
        """
        logger.info("📝 Phase 3: Generating content plan...")

        # Extract trending topics/themes
        trending_topics = self._extract_topics_from_trending(trending)

        # Get existing video titles to avoid duplicates
        existing_titles = set()
        if channel_videos:
            existing_titles = {self._normalize_title(v["title"]) for v in channel_videos}

        if not self.gemini:
            # Fallback: manually pick from trending
            return self._manual_plan(trending, existing_titles)

        # AI-powered plan generation
        try:
            top_20_summary = "\n".join(
                f"{i+1}. [{v['category']}] {v['title']} | "
                f"Views: {v['views']:,} | Engagement: {v['engagement_rate']}% | "
                f"Tags: {', '.join(v.get('tags', [])[:5])}"
                for i, v in enumerate(trending[:20])
            )

            existing_sample = "\n".join(list(existing_titles)[:20]) if existing_titles else "None"

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

            prompt = f"""You are a YouTube content strategist for a channel called "StreamGlobal" 
that creates English-language Shorts and long-form videos targeting a US audience.

Here are today's top 20 trending YouTube videos in the US:

{top_20_summary}
{channel_section}
Here are some of our existing video topics (to avoid duplicates):
{existing_sample}

Create a content plan for TOMORROW with exactly 10 video ideas:
- 8 YouTube Shorts (under 60 seconds, fact/info style)
- 2 Long-form ideas (8-15 minutes, documentary/educational style)

Requirements:
1. Topics must be INSPIRED by trending content AND successful channel patterns
2. Study the trending channels' title formats and content styles — create similar content
3. Must be in ENGLISH only
4. Must NOT duplicate any existing channel content
5. Each idea should have viral potential
6. Include relevant tags and hashtags
7. Consider the "hook in first 3 seconds" rule for Shorts
8. Prioritize topics from channels with high engagement rates

Output STRICT JSON format:
{{
    "date": "YYYY-MM-DD",
    "shorts": [
        {{
            "title": "Catchy Short Title",
            "topic": "Detailed topic description for script generation",
            "hook": "First 3 seconds hook text",
            "tags": ["tag1", "tag2", "tag3"],
            "inspired_by": "Which trending video/channel inspired this",
            "estimated_views": "low/medium/high based on trend analysis"
        }}
    ],
    "longform": [
        {{
            "title": "Long-form Video Title",
            "topic": "Detailed topic for research and scripting",
            "outline": "Brief outline of what the video should cover",
            "tags": ["tag1", "tag2"],
            "inspired_by": "Which trending video/channel inspired this",
            "estimated_views": "low/medium/high"
        }}
    ]
}}
"""
            response = self.gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )

            plan = json.loads(response.text)

            # Add metadata
            plan["generated_at"] = datetime.utcnow().isoformat()
            plan["trending_count"] = len(trending)
            plan["channels_analyzed"] = len(seen_channels)
            plan["status"] = "pending"

            logger.info(f"✅ Content plan: {len(plan.get('shorts', []))} shorts + {len(plan.get('longform', []))} longform")
            return plan

        except Exception as e:
            logger.error(f"AI plan generation failed: {e}")
            return self._manual_plan(trending, existing_titles)

    def _manual_plan(self, trending: List[Dict], existing_titles: set) -> Dict:
        """Fallback plan without AI."""
        shorts = []
        longform = []

        for v in trending[:30]:
            norm_title = self._normalize_title(v["title"])
            if norm_title in existing_titles:
                continue

            if v["is_shorts"] and len(shorts) < 8:
                shorts.append({
                    "title": f"Facts About {v['title'][:40]}",
                    "topic": v["title"],
                    "tags": v.get("tags", [])[:5],
                    "inspired_by": v["title"],
                    "estimated_views": "medium",
                })
            elif not v["is_shorts"] and len(longform) < 2:
                longform.append({
                    "title": f"Deep Dive: {v['title'][:40]}",
                    "topic": v["title"],
                    "tags": v.get("tags", [])[:5],
                    "inspired_by": v["title"],
                    "estimated_views": "medium",
                })

            if len(shorts) >= 8 and len(longform) >= 2:
                break

        return {
            "date": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "shorts": shorts,
            "longform": longform,
            "generated_at": datetime.utcnow().isoformat(),
            "trending_count": len(trending),
            "status": "pending",
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

    def execute_plan(self, factory_instance, max_shorts: int = 2, max_longform: int = 0) -> Dict:
        """
        Read the daily plan and produce content.
        Called by morning automation workflows.
        """
        logger.info("🎬 Executing daily content plan...")

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
        pending_shorts = [s for s in plan.get("shorts", []) if s.get("status", "pending") == "pending"]
        pending_longform = [l for l in plan.get("longform", []) if l.get("status", "pending") == "pending"]

        logger.info(f"📋 Pending: {len(pending_shorts)} shorts, {len(pending_longform)} longform")

        # Produce Shorts (only pending ones)
        for i, short in enumerate(pending_shorts[:max_shorts]):
            try:
                logger.info(f"\n🎬 Producing Short {i+1}: {short['title'][:50]}")
                production_id = factory_instance.run(
                    topic=short.get("topic", short["title"]),
                    languages=["en"],
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
                    results["errors"].append(f"Short '{short['title'][:30]}' failed")
            except Exception as e:
                short["status"] = "error"
                results["errors"].append(str(e))
                logger.error(f"Short production error: {e}")

        # Produce Long-form (only pending ones)
        for i, lf in enumerate(pending_longform[:max_longform]):
            try:
                logger.info(f"\n🎬 Producing Long-form {i+1}: {lf['title'][:50]}")
                production_id = factory_instance.run(
                    topic=lf.get("topic", lf["title"]),
                    languages=["en"],
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
        return results

    # ──────────────────────────────────────────────────────
    # MAIN: Run full nightly pipeline
    # ──────────────────────────────────────────────────────

    def run_nightly(self, dry_run: bool = False) -> Dict:
        """
        Run the complete nightly pipeline:
        1. Cleanup underperformers
        2. Discover top 100 trending
        3. Generate tomorrow's content plan
        """
        logger.info("=" * 60)
        logger.info("🧠 NIGHTLY BRAIN — Starting...")
        logger.info(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        logger.info(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("=" * 60)

        nightly_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
        }

        # ─── PHASE 1: Cleanup ───
        logger.info("\n" + "─" * 40)
        logger.info("🗑️ PHASE 1: Channel Cleanup")
        logger.info("─" * 40)
        cleanup = self.cleanup_channel(dry_run=dry_run)
        nightly_report["cleanup"] = {
            "deleted": cleanup.get("deleted_count", 0),
            "failed": cleanup.get("failed_count", 0),
            "kept": cleanup.get("kept_count", 0),
        }

        # ─── PHASE 2: Discover Trending ───
        logger.info("\n" + "─" * 40)
        logger.info("🔍 PHASE 2: Trend Discovery")
        logger.info("─" * 40)
        trending = self.discover_trending(region="US", count=100)
        nightly_report["trending"] = {
            "found": len(trending),
            "top_5": [
                {"title": v["title"][:60], "views": v["views"], "category": v["category"]}
                for v in trending[:5]
            ]
        }

        # ─── PHASE 3: Generate Plan ───
        logger.info("\n" + "─" * 40)
        logger.info("📝 PHASE 3: Content Planning")
        logger.info("─" * 40)

        # Get existing channel videos to avoid duplicates
        from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
        analytics = YouTubeAnalyticsAgent(youtube_service=self.youtube)
        channel_videos = analytics.get_all_videos(max_results=200)

        plan = self.generate_content_plan(trending, channel_videos)

        # Save plan
        os.makedirs(os.path.dirname(self.plan_file), exist_ok=True)
        with open(self.plan_file, "w") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Plan saved: {self.plan_file}")

        nightly_report["plan"] = {
            "shorts_planned": len(plan.get("shorts", [])),
            "longform_planned": len(plan.get("longform", [])),
            "shorts": [s.get("title", "?")[:50] for s in plan.get("shorts", [])],
            "longform": [l.get("title", "?")[:50] for l in plan.get("longform", [])],
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

        return nightly_report

    def _print_summary(self, report: Dict, plan: Dict):
        """Print nightly summary."""
        print("\n" + "=" * 60)
        print("🧠 NIGHTLY BRAIN SUMMARY")
        print("=" * 60)

        cleanup = report.get("cleanup", {})
        print(f"\n🗑️ Cleanup:")
        print(f"   Deleted: {cleanup.get('deleted', 0)}")
        print(f"   Failed: {cleanup.get('failed', 0)}")
        print(f"   Kept: {cleanup.get('kept', 0)}")

        trending = report.get("trending", {})
        print(f"\n🔍 Trending Videos Found: {trending.get('found', 0)}")
        for t in trending.get("top_5", []):
            print(f"   🔥 {t['title'][:50]} ({t['views']:,} views)")

        plan_info = report.get("plan", {})
        print(f"\n📝 Tomorrow's Plan:")
        print(f"   Shorts: {plan_info.get('shorts_planned', 0)}")
        for s in plan_info.get("shorts", []):
            print(f"   📹 {s}")
        print(f"   Long-form: {plan_info.get('longform_planned', 0)}")
        for l in plan_info.get("longform", []):
            print(f"   🎬 {l}")

        print("\n" + "=" * 60)

    def _parse_iso_duration(self, duration: str) -> int:
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
