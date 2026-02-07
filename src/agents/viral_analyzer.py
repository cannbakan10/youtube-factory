"""
Viral Analyzer Agent - Analyzes top performing YouTube Shorts to generate winning ideas.
"""
import os
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from google import genai
from googleapiclient.discovery import build
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff, APIRateLimiters

logger = get_logger(__name__)


@dataclass
class ViralVideo:
    """Represents a viral video with its metadata."""
    video_id: str
    title: str
    channel: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    published_at: str
    thumbnail_url: str
    tags: List[str]
    description: str

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (likes + comments) / views."""
        if self.view_count == 0:
            return 0.0
        return ((self.like_count + self.comment_count) / self.view_count) * 100

    @property
    def view_count_formatted(self) -> str:
        """Format view count for display."""
        if self.view_count >= 1_000_000:
            return f"{self.view_count / 1_000_000:.1f}M"
        elif self.view_count >= 1_000:
            return f"{self.view_count / 1_000:.1f}K"
        return str(self.view_count)


@dataclass
class VideoIdea:
    """A generated video idea based on viral analysis."""
    original_video: ViralVideo
    suggested_topic: str
    twist: str
    why_it_works: str
    target_audience: str
    recommended_hook: str
    estimated_potential: str  # "High", "Medium", "Low"
    style_context: str = ""


class ViralAnalyzer:
    """
    Analyzes viral YouTube Shorts and generates winning video ideas.

    Features:
    - Fetches trending Shorts from YouTube
    - Analyzes patterns in successful videos
    - Generates localized video ideas with unique twists
    """

    # Popular Shorts categories/search terms
    VIRAL_CATEGORIES = {
        "facts": ["shocking facts", "rare facts", "did you know", "unbelievable clips"],
        "science": ["science experiments", "space mysteries", "quantum physics facts", "future world"],
        "history": ["unfiltered history", "ancient mysteries", "historical secrets", "war stories"],
        "psychology": ["dark psychology", "mind tricks", "social engineering", "human behavior"],
        "nature": ["nature documentary", "animal facts", "terrifying nature", "deep sea"],
        "tech": ["future tech", "AI breakthrough", "hidden gadgets", "tech news"],
        "mystery": ["unsolved mysteries", "missing people", "paranormal investigation", "true crime shorts"],
        "lifestyle": ["productivity", "millionaire mindset", "life hacks", "satisfying"],
    }

    def __init__(self):
        # YouTube Data API
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.youtube = None
        if self.youtube_api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
                logger.info("YouTube Data API initialized")
            except Exception as e:
                logger.warning(f"YouTube API initialization failed: {e}")

        # Gemini for analysis
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip().replace('"', '').replace("'", "")
        self.gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        self.model = "gemini-2.0-flash"

    def _extract_json(self, text: str):
        """Resilient JSON extraction from AI response."""
        if not text:
            return None

        # Try direct parse first (handles both objects and arrays)
        try:
            return json.loads(text.strip())
        except Exception:
            pass

        # Try to find json block
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try to find anything between [ and ] (JSON array)
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try to find anything between { and } (JSON object)
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        return None

    def analyze_trending(
        self,
        category: str = "facts",
        region: str = "US",
        max_results: int = 10,
        language: str = "en"
    ) -> List[VideoIdea]:
        """
        Analyze trending Shorts in a category and generate video ideas.

        Args:
            category: Category to search (facts, science, history, etc.)
            region: Region code for trending (US, TR, GB, etc.)
            max_results: Number of videos to analyze
            language: Target language for generated ideas (en, tr)

        Returns:
            List of VideoIdea objects with suggestions
        """
        logger.info(f"Analyzing viral {category} Shorts from {region}...")

        # Step 1: Fetch viral videos
        viral_videos = self._fetch_viral_videos(category, region, max_results)

        if not viral_videos:
            logger.warning("No viral videos found. Using AI-based trend analysis.")
            return self._generate_ideas_from_ai(category, language)

        # Step 2: Analyze and generate ideas
        ideas = self._analyze_and_generate_ideas(viral_videos, language)

        return ideas

    def _fetch_viral_videos(
        self,
        category: str,
        region: str,
        max_results: int
    ) -> List[ViralVideo]:
        """Fetch viral Shorts from YouTube."""
        if not self.youtube:
            logger.warning("YouTube API not configured. Skipping video fetch.")
            return []

        search_terms = self.VIRAL_CATEGORIES.get(category, ["viral shorts"])
        all_videos = []
        per_term = max(1, max_results // 2)

        for term in search_terms[:2]:  # Limit to 2 terms to save quota
            try:
                videos = self._search_youtube(f"{term} #shorts", region, per_term)
                all_videos.extend(videos)
            except Exception as e:
                logger.warning(f"YouTube search failed for '{term}': {e}")

        # De-duplicate by video id
        deduped = {}
        for video in all_videos:
            deduped[video.video_id] = video

        # Sort by view count and return top results
        sorted_videos = sorted(deduped.values(), key=lambda v: v.view_count, reverse=True)
        return sorted_videos[:max_results]

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _search_youtube(self, query: str, region: str, max_results: int) -> List[ViralVideo]:
        """Search YouTube for Shorts."""
        if not self.youtube:
            logger.warning("YouTube API client not initialized. Cannot fetch viral videos.")
            return []
            
        logger.info(f"Searching YouTube: '{query}' in {region}")

        # Search for videos
        search_response = self.youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            videoDuration="short",  # Shorts are short duration
            order="viewCount",
            regionCode=region,
            maxResults=max_results,
            publishedAfter="2025-06-01T00:00:00Z"  # Focus on very recent/trending videos
        ).execute()

        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

        if not video_ids:
            return []

        # Get detailed stats
        stats_response = self.youtube.videos().list(
            part="statistics,contentDetails,snippet",
            id=",".join(video_ids)
        ).execute()

        videos = []
        for item in stats_response.get('items', []):
            try:
                stats = item.get('statistics', {})
                snippet = item.get('snippet', {})
                content = item.get('contentDetails', {})

                video = ViralVideo(
                    video_id=item['id'],
                    title=snippet.get('title', ''),
                    channel=snippet.get('channelTitle', ''),
                    view_count=int(stats.get('viewCount', 0)),
                    like_count=int(stats.get('likeCount', 0)),
                    comment_count=int(stats.get('commentCount', 0)),
                    duration=content.get('duration', 'PT0S'),
                    published_at=snippet.get('publishedAt', ''),
                    thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                    tags=snippet.get('tags', []),
                    description=snippet.get('description', '')[:500]
                )
                videos.append(video)
            except Exception as e:
                logger.warning(f"Failed to parse video data: {e}")

        logger.info(f"Found {len(videos)} viral videos")
        return videos

    def _analyze_and_generate_ideas(
        self,
        videos: List[ViralVideo],
        language: str
    ) -> List[VideoIdea]:
        """Analyze videos and generate ideas using AI."""
        if not self.gemini_client:
            logger.error("Gemini API not configured")
            return []

        ideas = []
        for video in videos[:5]:  # Analyze top 5
            try:
                idea = self._generate_idea_for_video(video, language)
                if idea:
                    ideas.append(idea)
            except Exception as e:
                logger.warning(f"Failed to generate idea for '{video.title}': {e}")

        return ideas

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _generate_idea_for_video(self, video: ViralVideo, language: str) -> Optional[VideoIdea]:
        """Generate a video idea based on a viral video."""
        APIRateLimiters.gemini.wait()

        lang_name = "Turkish" if language == "tr" else "English"

        prompt = f"""
        Analyze this viral YouTube Short and suggest a UNIQUE video idea inspired by it.

        VIRAL VIDEO INFO:
        - Title: {video.title}
        - Views: {video.view_count_formatted} ({video.view_count:,} exact)
        - Likes: {video.like_count:,}
        - Engagement Rate: {video.engagement_rate:.2f}%
        - Channel: {video.channel}
        - Tags: {', '.join(video.tags[:10]) if video.tags else 'None'}
        - Description excerpt: {video.description[:200]}

        YOUR TASK:
        1. Identify WHY this video went viral (hook, topic, format, emotion)
        2. Suggest a UNIQUE twist on this concept for a {lang_name} audience
        3. The new idea should NOT be a copy - it should be inspired but DIFFERENT
        4. Focus on educational/fact-based content

        OUTPUT FORMAT (JSON):
        {{
            "suggested_topic": "The specific topic for the new video",
            "twist": "What makes this different from the original",
            "why_it_works": "Why the original went viral and why yours will too",
            "target_audience": "Who will watch this",
            "recommended_hook": "The first 3 seconds hook in {lang_name}",
            "estimated_potential": "High/Medium/Low based on topic freshness",
            "style_context": "Describe the vibe, pacing, and narrative style to replicate"
        }}
        """

        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        data = self._extract_json(response.text)
        if not data:
            return None

        try:
            return VideoIdea(
                original_video=video,
                suggested_topic=data.get('suggested_topic', ''),
                twist=data.get('twist', ''),
                why_it_works=data.get('why_it_works', ''),
                target_audience=data.get('target_audience', ''),
                recommended_hook=data.get('recommended_hook', ''),
                estimated_potential=data.get('estimated_potential', 'Medium'),
                style_context=data.get('style_context', '')
            )
        except Exception as e:
            logger.error(f"Failed to create VideoIdea: {e}")
            return None

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _generate_ideas_from_ai(self, category: str, language: str) -> List[VideoIdea]:
        """Generate ideas purely from AI when YouTube API is not available."""
        if not self.gemini_client:
            logger.error("Gemini API not configured")
            return []

        APIRateLimiters.gemini.wait()

        lang_name = "Turkish" if language == "tr" else "English"

        prompt = f"""
        You are a viral video strategist. Generate 5 YouTube Shorts ideas for the "{category}" category.

        REQUIREMENTS:
        1. Each idea should be based on REAL viral trends you know about
        2. Include specific view count estimates based on similar viral videos
        3. Focus on {lang_name} audience
        4. Ideas should be fact-based, educational, and highly engaging

        OUTPUT FORMAT (JSON array):
        [
            {{
                "suggested_topic": "Specific topic",
                "twist": "What makes this unique",
                "why_it_works": "Why this will go viral",
                "target_audience": "Who will watch",
                "recommended_hook": "First 3 seconds hook in {lang_name}",
                "estimated_potential": "High/Medium/Low",
                "inspired_by": "What viral trend/video inspired this",
                "estimated_views": "e.g., 500K-1M"
            }}
        ]
        """

        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        try:
            data = self._extract_json(response.text)
            if not data or not isinstance(data, list):
                logger.error("AI response did not return a valid JSON array")
                return []
            ideas = []

            for item in data:
                # Create a placeholder viral video
                placeholder = ViralVideo(
                    video_id="ai_generated",
                    title=item.get('inspired_by', 'AI Trend Analysis'),
                    channel="Trend Analysis",
                    view_count=0,
                    like_count=0,
                    comment_count=0,
                    duration="PT60S",
                    published_at="",
                    thumbnail_url="",
                    tags=[],
                    description=f"Estimated views: {item.get('estimated_views', 'Unknown')}"
                )

                idea = VideoIdea(
                    original_video=placeholder,
                    suggested_topic=item.get('suggested_topic', ''),
                    twist=item.get('twist', ''),
                    why_it_works=item.get('why_it_works', ''),
                    target_audience=item.get('target_audience', ''),
                    recommended_hook=item.get('recommended_hook', ''),
                    estimated_potential=item.get('estimated_potential', 'Medium'),
                    style_context=item.get('style_context', '')
                )
                ideas.append(idea)

            logger.info(f"Generated {len(ideas)} AI-based ideas")
            return ideas

        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return []

    def print_ideas(self, ideas: List[VideoIdea]):
        """Pretty print the generated ideas."""
        if not ideas:
            print("\n❌ No ideas generated.")
            return

        print("\n" + "=" * 60)
        print("🔥 VIRAL VIDEO IDEAS")
        print("=" * 60)

        for i, idea in enumerate(ideas, 1):
            potential_emoji = {"High": "🚀", "Medium": "📈", "Low": "📊"}.get(
                idea.estimated_potential, "📊"
            )

            print(f"\n{'─' * 60}")
            print(f"💡 IDEA #{i}: {idea.suggested_topic}")
            print(f"{'─' * 60}")

            if idea.original_video.video_id != "ai_generated":
                print(f"📺 Inspired by: {idea.original_video.title}")
                print(f"   👁️  {idea.original_video.view_count_formatted} views | "
                      f"❤️  {idea.original_video.like_count:,} likes | "
                      f"📊 {idea.original_video.engagement_rate:.2f}% engagement")

            print(f"\n🎯 Twist: {idea.twist}")
            print(f"\n✨ Why it works: {idea.why_it_works}")
            print(f"\n👥 Target: {idea.target_audience}")
            print(f"\n🎬 Hook: \"{idea.recommended_hook}\"")
            print(f"\n{potential_emoji} Potential: {idea.estimated_potential}")

        print("\n" + "=" * 60)
        print(f"✅ Generated {len(ideas)} video ideas!")
        print("=" * 60 + "\n")

    def get_idea_as_topic(self, idea: VideoIdea) -> str:
        """Convert an idea to a topic string for video production."""
        return idea.suggested_topic

    def get_remix_candidates(
        self,
        category: str = "facts",
        region: str = "US",
        max_results: int = 10
    ) -> List[Dict[str, object]]:
        """
        Get viral English Shorts and provide editable "1-2 word changed" remix topics.
        """
        videos = self._fetch_viral_videos(category=category, region=region, max_results=max_results)
        if not videos:
            return self._generate_remix_without_youtube(category=category, max_results=max_results)
        candidates = []

        for video in videos:
            editable_topic, swap_hint, style_context = self._build_editable_topic(video.title)
            candidates.append(
                {
                    "video_id": video.video_id,
                    "youtube_url": f"https://www.youtube.com/watch?v={video.video_id}",
                    "original_title": video.title,
                    "editable_topic": editable_topic,
                    "swap_hint": swap_hint,
                    "style_context": style_context,
                    "channel": video.channel,
                    "view_count": video.view_count,
                    "view_count_formatted": video.view_count_formatted,
                    "engagement_rate": round(video.engagement_rate, 2),
                    "published_at": video.published_at,
                }
            )

        return candidates

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _generate_remix_without_youtube(self, category: str, max_results: int) -> List[Dict[str, object]]:
        if not self.gemini_client:
            logger.warning("No YouTube API and no Gemini API. Remix candidates cannot be generated.")
            return []

        APIRateLimiters.gemini.wait()
        prompt = f"""
        Generate {max_results} realistic viral English YouTube Shorts titles for the '{category}' category.
        For each title, provide an editable topic with only 1-2 words changed AND a style context.
        Return strict JSON array:
        [
          {{
            "original_title": "...",
            "editable_topic": "...",
            "swap_hint": "word1 -> word2",
            "style_context": "Describe the pacing and tone"
          }}
        ]
        """
        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = self._extract_json(response.text)
        if not data:
            return []
            
        candidates = []
        for idx, item in enumerate(data, 1):
            candidates.append(
                {
                    "video_id": f"ai_generated_{idx}",
                    "youtube_url": "",
                    "original_title": item.get("original_title", ""),
                    "editable_topic": item.get("editable_topic", ""),
                    "swap_hint": item.get("swap_hint", "Manual swap"),
                    "style_context": item.get("style_context", ""),
                    "channel": "AI Trend Simulation",
                    "view_count": 0,
                    "view_count_formatted": "-",
                    "engagement_rate": 0.0,
                    "published_at": "",
                }
            )
        return candidates

    def print_remix_candidates(self, candidates: List[Dict[str, object]]):
        """Pretty print remix candidates."""
        if not candidates:
            print("\n❌ No remix candidates found.")
            return

        print("\n" + "=" * 80)
        print("🧪 VIRAL REMIX CANDIDATES (ENGLISH SHORTS)")
        print("=" * 80)
        print("Edit only 1-2 words in the suggested line and produce directly.\n")

        for i, item in enumerate(candidates, 1):
            print(f"{i}. {item['original_title']}")
            print(f"   Channel: {item['channel']} | Views: {item['view_count_formatted']} | ER: {item['engagement_rate']}%")
            print(f"   Suggested editable topic: {item['editable_topic']}")
            print(f"   Swap hint: {item['swap_hint']}")
            print(f"   URL: {item['youtube_url']}\n")

    def _build_editable_topic(self, title: str) -> Tuple[str, str, str]:
        if self.gemini_client:
            try:
                return self._ai_remix_title(title)
            except Exception as e:
                logger.warning(f"AI remix title failed, using fallback: {e}")
        topic, hint = self._simple_remix_title(title)
        return topic, hint, ""

    @retry_with_backoff(max_retries=2, base_delay=2.0)
    def _ai_remix_title(self, title: str) -> Tuple[str, str, str]:
        APIRateLimiters.gemini.wait()

        prompt = f"""
        You are creating a legal-safe remix topic idea.
        Original title: "{title}"

        Rules:
        1. Keep structure similar, but change exactly 1 or 2 important words.
        2. Keep it in English.
        3. Do not copy exactly.

        Return JSON:
        {{
          "editable_topic": "new title",
          "swap_hint": "word1 -> new1, word2 -> new2",
          "style_context": "Describe the pacing, tone, and hook style based on the original title"
        }}
        """

        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        data = self._extract_json(response.text)
        if not data:
            raise ValueError("Failed to extract JSON from Gemini remix response")
            
        editable = data.get("editable_topic", "").strip()
        hint = data.get("swap_hint", "").strip()
        style = data.get("style_context", "").strip()
        
        if not editable:
            raise ValueError("Empty editable_topic from Gemini")
        return editable, hint or "Manual 1-2 word swap", style

    def _simple_remix_title(self, title: str) -> Tuple[str, str]:
        replacements = {
            "amazing": "hidden",
            "unbelievable": "unexpected",
            "shocking": "surprising",
            "secret": "untold",
            "facts": "truths",
            "fact": "truth",
            "history": "past",
            "science": "research",
            "space": "cosmos",
            "future": "next era",
            "money": "wealth",
            "success": "growth",
            "brain": "mind",
            "psychology": "behavior",
            "mystery": "enigma",
            "tech": "technology",
        }

        words = title.split()
        changed = []
        out_words = []

        for w in words:
            cleaned = re.sub(r"[^A-Za-z]", "", w).lower()
            replacement = replacements.get(cleaned)
            if replacement and len(changed) < 2:
                new_word = re.sub(cleaned, replacement, w, flags=re.IGNORECASE)
                out_words.append(new_word)
                changed.append(f"{w} -> {new_word}")
            else:
                out_words.append(w)

        if not changed and words:
            out_words[0] = f"New {words[0]}"
            changed.append(f"{words[0]} -> {out_words[0]}")

        return " ".join(out_words), ", ".join(changed)


if __name__ == "__main__":
    # Test the analyzer
    analyzer = ViralAnalyzer()
    ideas = analyzer.analyze_trending(category="facts", region="US", language="tr")
    analyzer.print_ideas(ideas)
