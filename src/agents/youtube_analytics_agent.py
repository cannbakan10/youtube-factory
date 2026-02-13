"""
YouTube Analytics & Strategy Agent

Comprehensive channel analysis tool that:
1. Fetches all channel videos and their performance metrics
2. Identifies underperforming / duplicate / redundant videos
3. Applies latest YouTube algorithm research for strategy recommendations
4. Recommends optimal posting times based on engagement data
5. Generates a full strategy report with Gemini AI

Uses YouTube Data API v3 for video stats and Gemini for AI analysis.
"""

import os
import json
import time
import math
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from collections import Counter, defaultdict

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────
# YOUTUBE ALGORITHM KNOWLEDGE BASE (2025-2026)
# ──────────────────────────────────────────────────────

YOUTUBE_ALGORITHM_KNOWLEDGE = """
## YouTube Algorithm Intelligence (2025-2026)

### Core Algorithm Signals:
1. **Viewer Satisfaction** (Most important) - High retention, repeat views, session duration
2. **Gemini AI Analysis** - YouTube now uses Gemini to "watch" videos, analyzing speech, visuals, tone, emotion
3. **Channel Trust Score** - Established accounts, consistent quality, authentic content
4. **Interest-based Distribution** - Algorithm matches content to viewer interests, not just subscribers

### YouTube Shorts Best Practices:
- Average engagement rate: 5.91% (beats TikTok 5.75% and Instagram Reels 5.53%)
- Daily Shorts views: 200+ billion (2026)
- 74% of Shorts views come from NON-subscribers (great for discovery)
- Optimal Shorts length: 50-60 seconds (highest views)
- Shorts >40 seconds have 33% higher engagement
- Hook viewers in first 2-3 seconds
- Use trending sounds/effects when possible

### Optimal Posting Times:
SHORTS:
- Best days: Wednesday, Thursday, Monday
- Best times: 4:00 PM, or evenings 6-10 PM (viewer's timezone)
- Tuesday 4 PM has highest engagement

LONG-FORM:
- Best days: Wednesday, Monday, Thursday
- Best times: 3-5 PM weekdays
- Wednesday 4 PM is the golden hour
- Saturday 3-5 PM for casual content
- Sunday 9 AM-12 PM for family/education content

### Content Strategy:
- Niche focus > general content
- Natural keyword integration in speech (Gemini listens)
- Series/playlists encourage longer sessions
- Shorts as discovery → Long-form for loyalty
- Consistent upload schedule signals algorithm reliability
- Reply to early comments (boosts first-hour engagement)

### Video Performance Benchmarks:
SHORTS:
- Good CTR: >5%
- Good engagement rate: >5%
- Views in 48 hours: key indicator
- Low performance = <100 views after 48h for small channels

LONG-FORM:
- Good retention: >50% average view duration
- Good CTR: >4%
- Good engagement: likes + comments > 5% of views
"""


class YouTubeAnalyticsAgent:
    """Analyzes YouTube channel performance and provides strategy recommendations."""

    def __init__(self, youtube_service=None):
        self.youtube = youtube_service
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.reports_dir = os.path.join(self.project_root, "data", "analytics")
        os.makedirs(self.reports_dir, exist_ok=True)

        # Gemini AI for analysis
        self.gemini = None
        try:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.gemini = genai.Client(api_key=api_key)
                logger.info("🤖 Analytics Agent: Gemini AI connected")
        except Exception:
            logger.info("Analytics Agent: Running without Gemini AI")

    # ──────────────────────────────────────────────────────
    # DATA FETCHING
    # ──────────────────────────────────────────────────────

    def get_channel_info(self) -> Optional[Dict]:
        """Get channel information (subscriber count, total views, etc.)."""
        if not self.youtube or not self.youtube.youtube:
            logger.error("YouTube service not available")
            return None

        try:
            request = self.youtube.youtube.channels().list(
                part="snippet,statistics,contentDetails",
                mine=True,
            )
            response = request.execute()
            if response.get("items"):
                channel = response["items"][0]
                stats = channel.get("statistics", {})
                snippet = channel.get("snippet", {})
                info = {
                    "channel_id": channel["id"],
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")[:200],
                    "subscriber_count": int(stats.get("subscriberCount", 0)),
                    "total_views": int(stats.get("viewCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "uploads_playlist": channel.get("contentDetails", {})
                        .get("relatedPlaylists", {}).get("uploads", ""),
                }
                logger.info(
                    f"📊 Channel: {info['title']} | "
                    f"{info['subscriber_count']:,} subs | "
                    f"{info['total_views']:,} views | "
                    f"{info['video_count']} videos"
                )
                return info
            return None
        except Exception as e:
            logger.error(f"Channel info error: {e}")
            return None

    def get_all_videos(self, max_results: int = 500) -> List[Dict]:
        """
        Fetch all videos from the channel with full statistics.
        Returns sorted by publishedAt (newest first).
        """
        if not self.youtube or not self.youtube.youtube:
            logger.error("YouTube service not available")
            return []

        channel_info = self.get_channel_info()
        if not channel_info:
            return []

        uploads_playlist = channel_info.get("uploads_playlist")
        if not uploads_playlist:
            logger.error("Could not find uploads playlist")
            return []

        # Step 1: Get all video IDs from uploads playlist
        video_ids = []
        next_page = None

        logger.info(f"📥 Fetching video list from playlist: {uploads_playlist}")

        while True:
            try:
                request = self.youtube.youtube.playlistItems().list(
                    part="contentDetails",
                    playlistId=uploads_playlist,
                    maxResults=50,
                    pageToken=next_page,
                )
                response = request.execute()

                for item in response.get("items", []):
                    vid_id = item["contentDetails"]["videoId"]
                    video_ids.append(vid_id)

                next_page = response.get("nextPageToken")
                if not next_page or len(video_ids) >= max_results:
                    break

            except Exception as e:
                logger.error(f"Playlist fetch error: {e}")
                break

        logger.info(f"📋 Found {len(video_ids)} videos")

        if not video_ids:
            return []

        # Step 2: Get detailed stats for each video (batch of 50)
        all_videos = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            try:
                request = self.youtube.youtube.videos().list(
                    part="snippet,statistics,contentDetails,status",
                    id=",".join(batch),
                )
                response = request.execute()

                for item in response.get("items", []):
                    stats = item.get("statistics", {})
                    snippet = item.get("snippet", {})
                    content = item.get("contentDetails", {})
                    status = item.get("status", {})

                    # Parse duration (ISO 8601)
                    duration_str = content.get("duration", "PT0S")
                    duration_sec = self._parse_iso_duration(duration_str)

                    # Determine if Shorts
                    is_shorts = duration_sec <= 60 or "#shorts" in snippet.get("title", "").lower()
                    if "#shorts" in snippet.get("description", "").lower():
                        is_shorts = True

                    # Parse publish date
                    published_at = snippet.get("publishedAt", "")
                    days_since = self._days_since(published_at)

                    views = int(stats.get("viewCount", 0))
                    likes = int(stats.get("likeCount", 0))
                    comments = int(stats.get("commentCount", 0))

                    # Calculate metrics
                    engagement_rate = (
                        (likes + comments) / views * 100 if views > 0 else 0
                    )
                    views_per_day = views / max(days_since, 1)

                    video_data = {
                        "id": item["id"],
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:200],
                        "published_at": published_at,
                        "days_since_publish": days_since,
                        "duration_seconds": duration_sec,
                        "is_shorts": is_shorts,
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "engagement_rate": round(engagement_rate, 2),
                        "views_per_day": round(views_per_day, 1),
                        "tags": snippet.get("tags", []),
                        "category_id": snippet.get("categoryId", ""),
                        "privacy_status": status.get("privacyStatus", ""),
                        "publish_hour": self._get_hour(published_at),
                        "publish_day": self._get_day_of_week(published_at),
                    }
                    all_videos.append(video_data)

                logger.info(f"   📊 Fetched stats: {len(all_videos)}/{len(video_ids)}")

            except Exception as e:
                logger.error(f"Video stats error: {e}")

        # Sort by published date (newest first)
        all_videos.sort(key=lambda v: v["published_at"], reverse=True)

        logger.info(f"✅ Total videos analyzed: {len(all_videos)}")
        return all_videos

    # ──────────────────────────────────────────────────────
    # ANALYSIS
    # ──────────────────────────────────────────────────────

    def analyze_channel(self, videos: List[Dict]) -> Dict:
        """
        Comprehensive channel analysis.
        Returns analysis dict with categorized findings.
        """
        if not videos:
            return {"error": "No videos to analyze"}

        shorts = [v for v in videos if v["is_shorts"]]
        longform = [v for v in videos if not v["is_shorts"]]

        analysis = {
            "total_videos": len(videos),
            "total_shorts": len(shorts),
            "total_longform": len(longform),
            "total_views": sum(v["views"] for v in videos),
            "total_likes": sum(v["likes"] for v in videos),
            "total_comments": sum(v["comments"] for v in videos),
        }

        # Average metrics
        if shorts:
            analysis["shorts_avg_views"] = round(sum(v["views"] for v in shorts) / len(shorts))
            analysis["shorts_avg_engagement"] = round(
                sum(v["engagement_rate"] for v in shorts) / len(shorts), 2
            )
            analysis["shorts_median_views"] = sorted(
                [v["views"] for v in shorts]
            )[len(shorts) // 2]

        if longform:
            analysis["longform_avg_views"] = round(sum(v["views"] for v in longform) / len(longform))
            analysis["longform_avg_engagement"] = round(
                sum(v["engagement_rate"] for v in longform) / len(longform), 2
            )

        # Identify underperformers
        analysis["underperformers"] = self._find_underperformers(videos)
        analysis["duplicates"] = self._find_duplicates(videos)
        analysis["top_performers"] = self._find_top_performers(videos)
        analysis["posting_patterns"] = self._analyze_posting_patterns(videos)
        analysis["optimal_times"] = self._find_optimal_times(videos)
        analysis["content_gaps"] = self._find_content_gaps(videos)

        return analysis

    def _find_underperformers(self, videos: List[Dict]) -> List[Dict]:
        """
        Find videos with significantly below-average performance.
        Criteria:
        - Shorts: Views < 25% of median, or 0 engagement after 7+ days
        - Longform: Views < 25% of median, or very low engagement
        """
        shorts = [v for v in videos if v["is_shorts"]]
        longform = [v for v in videos if not v["is_shorts"]]

        underperformers = []

        # Shorts analysis
        if shorts:
            shorts_median = sorted([v["views"] for v in shorts])[len(shorts) // 2]
            threshold = max(shorts_median * 0.25, 10)  # At least 10 views threshold

            for v in shorts:
                if v["days_since_publish"] < 3:
                    continue  # Too new to judge

                reasons = []
                score = 0  # Lower = worse

                if v["views"] < threshold:
                    reasons.append(f"Views ({v['views']}) far below median ({shorts_median})")
                    score -= 2

                if v["views"] == 0 and v["days_since_publish"] > 7:
                    reasons.append("Zero views after 7+ days")
                    score -= 3

                if v["engagement_rate"] == 0 and v["views"] > 0 and v["days_since_publish"] > 3:
                    reasons.append("Zero engagement (no likes/comments)")
                    score -= 1

                if v["views_per_day"] < 1 and v["days_since_publish"] > 14:
                    reasons.append(f"Only {v['views_per_day']} views/day")
                    score -= 1

                if reasons:
                    underperformers.append({
                        **v,
                        "reasons": reasons,
                        "severity_score": score,
                        "recommendation": "DELETE" if score <= -3 else "REVIEW",
                    })

        # Longform analysis
        if longform:
            lf_median = sorted([v["views"] for v in longform])[len(longform) // 2]
            lf_threshold = max(lf_median * 0.25, 20)

            for v in longform:
                if v["days_since_publish"] < 7:
                    continue

                reasons = []
                score = 0

                if v["views"] < lf_threshold:
                    reasons.append(f"Views ({v['views']}) far below median ({lf_median})")
                    score -= 2

                if v["engagement_rate"] < 0.5 and v["views"] > 100:
                    reasons.append(f"Very low engagement ({v['engagement_rate']}%)")
                    score -= 1

                if reasons:
                    underperformers.append({
                        **v,
                        "reasons": reasons,
                        "severity_score": score,
                        "recommendation": "DELETE" if score <= -3 else "REVIEW",
                    })

        # Sort by severity
        underperformers.sort(key=lambda x: x["severity_score"])
        return underperformers

    def _find_duplicates(self, videos: List[Dict]) -> List[Dict]:
        """Find videos with very similar titles (potential duplicates)."""
        duplicates = []
        titles = [(v["id"], self._normalize_title(v["title"])) for v in videos]

        for i, (id1, t1) in enumerate(titles):
            for j, (id2, t2) in enumerate(titles):
                if i >= j:
                    continue
                similarity = self._title_similarity(t1, t2)
                if similarity > 0.75:  # >75% similar
                    v1 = next(v for v in videos if v["id"] == id1)
                    v2 = next(v for v in videos if v["id"] == id2)
                    duplicates.append({
                        "video_1": {"id": id1, "title": v1["title"], "views": v1["views"]},
                        "video_2": {"id": id2, "title": v2["title"], "views": v2["views"]},
                        "similarity": round(similarity * 100, 1),
                        "recommendation": f"Keep '{v1['title'][:40]}' (more views)" if v1["views"] >= v2["views"]
                            else f"Keep '{v2['title'][:40]}' (more views)",
                        "delete_id": id2 if v1["views"] >= v2["views"] else id1,
                    })

        return duplicates

    def _find_top_performers(self, videos: List[Dict]) -> Dict:
        """Find best performing videos by category."""
        shorts = [v for v in videos if v["is_shorts"]]
        longform = [v for v in videos if not v["is_shorts"]]

        return {
            "top_shorts_by_views": sorted(shorts, key=lambda v: v["views"], reverse=True)[:10],
            "top_shorts_by_engagement": sorted(shorts, key=lambda v: v["engagement_rate"], reverse=True)[:10],
            "top_longform_by_views": sorted(longform, key=lambda v: v["views"], reverse=True)[:10],
            "top_longform_by_engagement": sorted(longform, key=lambda v: v["engagement_rate"], reverse=True)[:10],
        }

    def _analyze_posting_patterns(self, videos: List[Dict]) -> Dict:
        """Analyze when videos are posted and their performance."""
        hour_views = defaultdict(list)
        day_views = defaultdict(list)
        hour_engagement = defaultdict(list)

        for v in videos:
            if v["publish_hour"] is not None:
                hour_views[v["publish_hour"]].append(v["views"])
                hour_engagement[v["publish_hour"]].append(v["engagement_rate"])
            if v["publish_day"] is not None:
                day_views[v["publish_day"]].append(v["views"])

        # Average views per hour
        avg_by_hour = {}
        for hour, views_list in hour_views.items():
            avg_by_hour[hour] = {
                "avg_views": round(sum(views_list) / len(views_list)),
                "count": len(views_list),
                "avg_engagement": round(
                    sum(hour_engagement.get(hour, [0])) / max(len(hour_engagement.get(hour, [1])), 1), 2
                ),
            }

        # Average views per day
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        avg_by_day = {}
        for day, views_list in day_views.items():
            avg_by_day[day_names[day] if day < 7 else str(day)] = {
                "avg_views": round(sum(views_list) / len(views_list)),
                "count": len(views_list),
            }

        return {
            "by_hour": dict(sorted(avg_by_hour.items())),
            "by_day": avg_by_day,
        }

    def _find_optimal_times(self, videos: List[Dict]) -> Dict:
        """Determine optimal posting times based on channel data + algorithm research."""
        patterns = self._analyze_posting_patterns(videos)

        # Find best hours
        hour_data = patterns.get("by_hour", {})
        best_hours = sorted(
            hour_data.items(),
            key=lambda x: x[1]["avg_views"],
            reverse=True,
        )[:5]

        # Find best days
        day_data = patterns.get("by_day", {})
        best_days = sorted(
            day_data.items(),
            key=lambda x: x[1]["avg_views"],
            reverse=True,
        )[:3]

        return {
            "best_hours_utc": [{"hour": h, **data} for h, data in best_hours],
            "best_days": [{"day": d, **data} for d, data in best_days],
            "algorithm_recommended": {
                "shorts": {
                    "best_days": ["Wednesday", "Thursday", "Monday"],
                    "best_times": ["16:00", "18:00-22:00"],
                    "note": "Tuesday 4PM has highest engagement globally",
                },
                "longform": {
                    "best_days": ["Wednesday", "Monday", "Thursday"],
                    "best_times": ["15:00-17:00"],
                    "note": "Wednesday 4PM is the golden hour",
                },
            },
        }

    def _find_content_gaps(self, videos: List[Dict]) -> List[str]:
        """Identify potential content gaps or opportunities."""
        titles_combined = " ".join(v["title"].lower() for v in videos)
        tags_combined = []
        for v in videos:
            tags_combined.extend(v.get("tags", []))

        tag_counts = Counter(t.lower() for t in tags_combined)

        gaps = []

        # Check posting frequency
        if videos:
            recent = [v for v in videos if v["days_since_publish"] < 30]
            if len(recent) < 10:
                gaps.append(
                    f"Low posting frequency: only {len(recent)} videos in last 30 days. "
                    "Algorithm rewards consistent uploading."
                )

        # Check content diversity
        shorts_count = sum(1 for v in videos if v["is_shorts"])
        longform_count = len(videos) - shorts_count
        if shorts_count > 0 and longform_count == 0:
            gaps.append(
                "No long-form content. Shorts drive discovery but long-form builds loyalty. "
                "Consider adding 10-15 min documentaries."
            )
        if longform_count > 0 and shorts_count == 0:
            gaps.append(
                "No Shorts content. 74% of Shorts views come from non-subscribers. "
                "Great for channel discovery."
            )

        return gaps

    # ──────────────────────────────────────────────────────
    # VIDEO MANAGEMENT (delete underperformers)
    # ──────────────────────────────────────────────────────

    def delete_video(self, video_id: str) -> bool:
        """Delete a video from the channel."""
        if not self.youtube or not self.youtube.youtube:
            logger.error("YouTube service not available")
            return False

        try:
            self.youtube.youtube.videos().delete(id=video_id).execute()
            logger.info(f"🗑️ Video deleted: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed for {video_id}: {e}")
            return False

    def batch_delete_underperformers(
        self, videos: List[Dict], min_severity: int = -3, dry_run: bool = True
    ) -> List[Dict]:
        """
        Delete underperforming videos.
        Args:
            videos: List of underperformer dicts from analysis
            min_severity: Only delete videos with severity <= this value
            dry_run: If True, only report what would be deleted
        """
        to_delete = [
            v for v in videos
            if v.get("severity_score", 0) <= min_severity
            and v.get("recommendation") == "DELETE"
        ]

        results = []
        for v in to_delete:
            if dry_run:
                logger.info(
                    f"  [DRY RUN] Would delete: {v['title'][:50]} | "
                    f"Views: {v['views']} | Reasons: {', '.join(v['reasons'])}"
                )
                results.append({**v, "action": "WOULD_DELETE"})
            else:
                success = self.delete_video(v["id"])
                results.append({**v, "action": "DELETED" if success else "FAILED"})

        return results

    # ──────────────────────────────────────────────────────
    # AI-POWERED STRATEGY REPORT
    # ──────────────────────────────────────────────────────

    def generate_strategy_report(self, videos: List[Dict], analysis: Dict) -> str:
        """Generate a comprehensive strategy report using Gemini AI."""
        channel_info = self.get_channel_info() or {}

        # Prepare data summary for Gemini
        data_summary = f"""
## Channel Overview
- Channel: {channel_info.get('title', 'Unknown')}
- Subscribers: {channel_info.get('subscriber_count', 0):,}
- Total Views: {analysis.get('total_views', 0):,}
- Total Videos: {analysis.get('total_videos', 0)}
- Shorts: {analysis.get('total_shorts', 0)} | Long-form: {analysis.get('total_longform', 0)}

## Performance Metrics
- Shorts Avg Views: {analysis.get('shorts_avg_views', 'N/A')}
- Shorts Avg Engagement: {analysis.get('shorts_avg_engagement', 'N/A')}%
- Shorts Median Views: {analysis.get('shorts_median_views', 'N/A')}
- Longform Avg Views: {analysis.get('longform_avg_views', 'N/A')}
- Longform Avg Engagement: {analysis.get('longform_avg_engagement', 'N/A')}%

## Underperforming Videos: {len(analysis.get('underperformers', []))}
{self._format_underperformers_summary(analysis.get('underperformers', []))}

## Duplicate/Similar Videos: {len(analysis.get('duplicates', []))}
{self._format_duplicates_summary(analysis.get('duplicates', []))}

## Top 5 Most Viewed Shorts:
{self._format_top_videos(analysis.get('top_performers', {}).get('top_shorts_by_views', [])[:5])}

## Top 5 Most Viewed Long-form:
{self._format_top_videos(analysis.get('top_performers', {}).get('top_longform_by_views', [])[:5])}

## Posting Pattern Analysis:
Best hours (UTC): {json.dumps(analysis.get('optimal_times', {}).get('best_hours_utc', [])[:3], indent=2)}
Best days: {json.dumps(analysis.get('optimal_times', {}).get('best_days', [])[:3], indent=2)}

## Content Gaps:
{chr(10).join(f'- {g}' for g in analysis.get('content_gaps', []))}
"""

        if not self.gemini:
            # No AI available, return data-only report
            return f"# YouTube Analytics Report\n\n{data_summary}"

        try:
            prompt = f"""Sen bir YouTube stratejisti ve algoritma uzmanısın. Aşağıdaki kanal verilerini 
analiz et ve TÜRKÇE olarak kapsamlı bir strateji raporu hazırla.

{YOUTUBE_ALGORITHM_KNOWLEDGE}

{data_summary}

Raporun şu bölümleri içersin:

1. 📊 **KANAL GENEL DURUMU**
   - Kanalın güçlü ve zayıf yönleri
   
2. 🗑️ **SİLİNMESİ GEREKEN VİDEOLAR**
   - Hangi videoların silinmesi gerektiği ve neden
   - Benzer/tekrar videolar

3. ⏰ **OPTİMAL YAYINLAMA SAATLERİ**
   - Kanal verilerine göre en iyi saatler
   - YouTube algoritması önerileri
   - Shorts vs Long-form için ayrı öneriler

4. 🎯 **İÇERİK STRATEJİSİ**
   - Hangi tür içerikler daha çok izleniyor
   - Hangi konulara ağırlık verilmeli
   - Shorts/Long-form dengesi

5. 📈 **BÜYÜME ÖNERİLERİ**
   - Kısa vadeli (1 ay) aksiyon planı
   - Orta vadeli (3 ay) hedefler
   - Algoritma optimizasyonu önerileri

6. ⚠️ **YAPILMAMASI GEREKENLER**
   - Aynı içeriği tekrar yayınlamamak
   - Düşük kalite içerik üretmemek
   - Algoritma cezalarından kaçınmak

Raporu markdown formatında, detaylı ve actionable önerilerle yaz.
"""
            response = self.gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            report = response.text
            logger.info("✅ AI Strategy Report generated")
            return report

        except Exception as e:
            logger.error(f"Gemini report generation failed: {e}")
            return f"# YouTube Analytics Report\n\n{data_summary}"

    # ──────────────────────────────────────────────────────
    # FULL PIPELINE
    # ──────────────────────────────────────────────────────

    def run_full_analysis(self, auto_delete: bool = False) -> Dict:
        """
        Run the complete analytics pipeline:
        1. Fetch all videos
        2. Analyze performance
        3. Generate AI strategy report
        4. Optionally delete underperformers

        Returns analysis results.
        """
        logger.info("=" * 60)
        logger.info("📊 YOUTUBE ANALYTICS & STRATEGY TOOL")
        logger.info("=" * 60)

        # Step 1: Fetch data
        logger.info("\n📥 Step 1: Fetching all videos...")
        videos = self.get_all_videos()
        if not videos:
            logger.error("No videos found. Check YouTube credentials.")
            return {"error": "No videos"}

        # Step 2: Analyze
        logger.info("\n🔍 Step 2: Analyzing performance...")
        analysis = self.analyze_channel(videos)

        # Step 3: Print summary
        self._print_summary(analysis)

        # Step 4: Generate AI report
        logger.info("\n🤖 Step 4: Generating AI Strategy Report...")
        report = self.generate_strategy_report(videos, analysis)

        # Step 5: Save report
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.reports_dir, f"strategy_report_{timestamp}.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"💾 Report saved: {report_path}")

        # Save raw data
        data_path = os.path.join(self.reports_dir, f"channel_data_{timestamp}.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(
                {"analysis": analysis, "videos": videos},
                f, indent=2, ensure_ascii=False, default=str,
            )
        logger.info(f"💾 Data saved: {data_path}")

        # Step 6: Handle deletions
        underperformers = analysis.get("underperformers", [])
        if underperformers:
            logger.info(f"\n🗑️ Found {len(underperformers)} underperforming videos")
            delete_results = self.batch_delete_underperformers(
                underperformers, dry_run=not auto_delete
            )
            analysis["delete_results"] = delete_results

        # Print report excerpt
        print("\n" + "=" * 60)
        print("📋 STRATEGY REPORT")
        print("=" * 60)
        print(report[:3000])
        if len(report) > 3000:
            print(f"\n... (Full report: {report_path})")
        print("=" * 60)

        return {
            "analysis": analysis,
            "report_path": report_path,
            "data_path": data_path,
            "video_count": len(videos),
        }

    # ──────────────────────────────────────────────────────
    # UTILITY METHODS
    # ──────────────────────────────────────────────────────

    def _print_summary(self, analysis: Dict):
        """Print a quick summary to terminal."""
        print("\n" + "=" * 60)
        print("📊 CHANNEL ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"  Total Videos: {analysis.get('total_videos', 0)}")
        print(f"  Shorts: {analysis.get('total_shorts', 0)} | Long-form: {analysis.get('total_longform', 0)}")
        print(f"  Total Views: {analysis.get('total_views', 0):,}")
        print(f"  Total Likes: {analysis.get('total_likes', 0):,}")
        print()

        if analysis.get("shorts_avg_views"):
            print(f"  📹 Shorts Avg Views: {analysis['shorts_avg_views']:,}")
            print(f"  📹 Shorts Avg Engagement: {analysis['shorts_avg_engagement']}%")
            print(f"  📹 Shorts Median Views: {analysis['shorts_median_views']:,}")

        if analysis.get("longform_avg_views"):
            print(f"  🎬 Longform Avg Views: {analysis['longform_avg_views']:,}")
            print(f"  🎬 Longform Avg Engagement: {analysis['longform_avg_engagement']}%")

        underperformers = analysis.get("underperformers", [])
        duplicates = analysis.get("duplicates", [])
        print(f"\n  ⚠️ Underperformers: {len(underperformers)}")
        print(f"  🔁 Duplicates/Similar: {len(duplicates)}")

        # Optimal times
        optimal = analysis.get("optimal_times", {})
        best_hours = optimal.get("best_hours_utc", [])
        if best_hours:
            print(f"\n  ⏰ Best posting hours (UTC): ", end="")
            print(", ".join(f"{h['hour']}:00" for h in best_hours[:3]))

        best_days = optimal.get("best_days", [])
        if best_days:
            print(f"  📅 Best posting days: ", end="")
            print(", ".join(d["day"] for d in best_days[:3]))

        print("=" * 60)

    def _parse_iso_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    def _days_since(self, published_at: str) -> int:
        """Calculate days since a video was published."""
        try:
            pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now = datetime.now(pub_date.tzinfo)
            return max((now - pub_date).days, 0)
        except Exception:
            return 0

    def _get_hour(self, published_at: str) -> Optional[int]:
        """Extract hour from ISO datetime."""
        try:
            return datetime.fromisoformat(published_at.replace("Z", "+00:00")).hour
        except Exception:
            return None

    def _get_day_of_week(self, published_at: str) -> Optional[int]:
        """Extract day of week (0=Mon, 6=Sun)."""
        try:
            return datetime.fromisoformat(published_at.replace("Z", "+00:00")).weekday()
        except Exception:
            return None

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        title = title.lower().strip()
        title = re.sub(r'[#@]\w+', '', title)  # Remove hashtags/mentions
        title = re.sub(r'[^\w\s]', '', title)  # Remove punctuation
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def _title_similarity(self, t1: str, t2: str) -> float:
        """Calculate similarity between two titles using word overlap."""
        words1 = set(t1.split())
        words2 = set(t2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def _format_underperformers_summary(self, underperformers: List[Dict]) -> str:
        """Format underperformers for report."""
        if not underperformers:
            return "None found."
        lines = []
        for v in underperformers[:15]:
            lines.append(
                f"- [{v.get('recommendation', '?')}] {v['title'][:50]} | "
                f"Views: {v['views']} | {', '.join(v.get('reasons', []))}"
            )
        return "\n".join(lines)

    def _format_duplicates_summary(self, duplicates: List[Dict]) -> str:
        """Format duplicates for report."""
        if not duplicates:
            return "None found."
        lines = []
        for d in duplicates[:10]:
            lines.append(
                f"- {d['similarity']}% similar: "
                f"'{d['video_1']['title'][:30]}' ({d['video_1']['views']} views) vs "
                f"'{d['video_2']['title'][:30]}' ({d['video_2']['views']} views) → {d['recommendation']}"
            )
        return "\n".join(lines)

    def _format_top_videos(self, videos: List[Dict]) -> str:
        """Format top videos for report."""
        if not videos:
            return "None."
        lines = []
        for i, v in enumerate(videos, 1):
            lines.append(f"  {i}. {v['title'][:50]} | Views: {v['views']:,} | Eng: {v['engagement_rate']}%")
        return "\n".join(lines)
