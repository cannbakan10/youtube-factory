import os
import json
import random
import pickle
import requests
from datetime import datetime, timedelta
import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── Playlist Category Mapping ─────────────────────────────────
PLAYLIST_MAP = {
    "animal": "Amazing Animal Facts 🐾",
    "animals": "Amazing Animal Facts 🐾",
    "cat": "Amazing Animal Facts 🐾",
    "dog": "Amazing Animal Facts 🐾",
    "wildlife": "Amazing Animal Facts 🐾",
    "space": "Mind-Blowing Space Facts 🌌",
    "planet": "Mind-Blowing Space Facts 🌌",
    "galaxy": "Mind-Blowing Space Facts 🌌",
    "universe": "Mind-Blowing Space Facts 🌌",
    "star": "Mind-Blowing Space Facts 🌌",
    "black hole": "Mind-Blowing Space Facts 🌌",
    "country": "Country Deep Dives 🌍",
    "geography": "Country Deep Dives 🌍",
    "city": "Country Deep Dives 🌍",
    "nation": "Country Deep Dives 🌍",
    "history": "Incredible History 📚",
    "ancient": "Incredible History 📚",
    "war": "Incredible History 📚",
    "civilization": "Incredible History 📚",
    "empire": "Incredible History 📚",
    "nature": "Nature & Relaxation 🌿",
    "forest": "Nature & Relaxation 🌿",
    "mountain": "Nature & Relaxation 🌿",
    "ambient": "Sleep & Study Sounds 🎧",
    "sleep": "Sleep & Study Sounds 🎧",
    "rain": "Sleep & Study Sounds 🎧",
    "asmr": "Sleep & Study Sounds 🎧",
    "study": "Sleep & Study Sounds 🎧",
    "fireplace": "Cozy Fireplace Collection 🔥",
    "fire": "Cozy Fireplace Collection 🔥",
    "cozy": "Cozy Fireplace Collection 🔥",
    "science": "Science Explained 🔬",
    "physics": "Science Explained 🔬",
    "chemistry": "Science Explained 🔬",
    "biology": "Science Explained 🔬",
    "brain": "Science Explained 🔬",
    "human body": "Science Explained 🔬",
    "technology": "Tech & Future 🤖",
    "ai": "Tech & Future 🤖",
    "robot": "Tech & Future 🤖",
    "tech": "Tech & Future 🤖",
    "ocean": "Ocean & Deep Sea 🌊",
    "sea": "Ocean & Deep Sea 🌊",
    "underwater": "Ocean & Deep Sea 🌊",
    "marine": "Ocean & Deep Sea 🌊",
    "mystery": "Unsolved Mysteries 🔮",
    "horror": "Unsolved Mysteries 🔮",
    "psychology": "Mind & Psychology 🧠",
    "mind": "Mind & Psychology 🧠",
}

# ─── Engagement Comments Pool ──────────────────────────────────
ENGAGEMENT_COMMENTS = {
    "facts": [
        "What fact surprised you the most? 🤯 Comment below!",
        "Did you know this? Drop a 🔥 if you learned something new!",
        "Which one was the most mind-blowing? Let me know! 👇",
        "I bet you didn't know #3! 😱 Comment your reaction!",
        "Share this with someone who needs to see this! 🧠",
    ],
    "nature": [
        "Where would you love to visit? 🌍 Comment below!",
        "Nature is incredible 🌿 Double tap if you agree!",
        "Would you visit this place? Drop a ❤️ if yes!",
    ],
    "ambient": [
        "Use this for sleep or study? 🎧 Let me know in the comments!",
        "Turn up the volume and relax 😌 What are you doing while listening?",
        "Perfect for: 📚 Study | 😴 Sleep | 🧘 Meditation — Which one? 👇",
    ],
    "default": [
        "What do you think about this? 🤔 Comment below!",
        "Drop a 🔥 if you enjoyed this! Subscribe for more!",
        "Did this blow your mind? 🧠 Let me know! 👇",
        "Share this with a friend who would love it! 🚀",
        "Which part was your favorite? Comment below! 💬",
    ],
}


class YouTubeService:
    def __init__(self):
        # Core scopes — MUST be present in token. Do NOT add new required scopes
        # here without coordinating a token refresh; an extra required scope
        # will invalidate existing tokens in CI and break ALL uploads.
        self.scopes = [
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]
        # Optional scopes — requested during re-auth but NOT required for uploads.
        # yt-analytics.readonly powers get_retention_insights(); if missing,
        # retention feedback is skipped gracefully instead of blocking uploads.
        self.optional_scopes = [
            "https://www.googleapis.com/auth/yt-analytics.readonly",
        ]
        # Determine project root relative to this file
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.client_secrets_file = os.path.join(self.project_root, "client_secrets.json")
        
        # Load client_secrets from env if in CI
        env_secrets = os.getenv("CLIENT_SECRETS_JSON")
        if env_secrets and not os.path.exists(self.client_secrets_file):
            with open(self.client_secrets_file, "w") as f:
                f.write(env_secrets)
                
        self.token_file = os.path.join(self.project_root, "token.pickle")
        print(f"   🔍 [YouTube]: Checking client_secrets at: {self.client_secrets_file}")
        print(f"   🔍 [YouTube]: Checking token at: {self.token_file}")
        
        self.allow_interactive = not (os.getenv("GITHUB_ACTIONS") or os.getenv("CI"))
        self.credentials = self._authenticate()
        self.youtube = build("youtube", "v3", credentials=self.credentials) if self.credentials else None
        
        # Cache for playlist IDs
        self._playlist_cache = {}
        
        if not self.youtube:
            print("   ⚠️ [YouTube]: Service initialized WITHOUT upload capability (No valid credentials).")

    def _authenticate(self):
        creds = None
        # Try loading from base64 env var first (for CI/CD)
        token_base64 = os.getenv("TOKEN_PICKLE_BASE64")
        if token_base64:
            try:
                import base64
                print("   🔑 [YouTube]: Loading credentials from TOKEN_PICKLE_BASE64 env...")
                decoded_token = base64.b64decode(token_base64)
                creds = pickle.loads(decoded_token)
            except Exception as e:
                print(f"   ⚠️ [YouTube]: Failed to load token from base64 env: {e}")

        if not creds and os.path.exists(self.token_file):
            print(f"   🔑 [YouTube]: Loading credentials from {self.token_file}")
            try:
                with open(self.token_file, "rb") as token:
                    creds = pickle.load(token)
            except Exception as e:
                print(f"   ⚠️ [YouTube]: Failed to load token.pickle: {e}")
                creds = None

        # ── SCOPE VALIDATION ──
        # If token exists but doesn't have all required scopes (e.g., youtube.force-ssl
        # was added later), force re-authentication to get the new scopes
        if creds and creds.valid:
            token_scopes = set(getattr(creds, 'scopes', []) or [])
            required_scopes = set(self.scopes)
            missing = required_scopes - token_scopes
            if missing and token_scopes:  # Only check if token has scope info
                print(f"   ⚠️ [YouTube]: Token missing scopes: {missing}")
                print(f"   🔄 [YouTube]: Re-authentication required for full permissions (comments, etc.)")
                if self.allow_interactive:
                    creds = None  # Force re-auth below
                else:
                    print(f"   ⚠️ [YouTube]: Running in CI — cannot re-auth. Some features (comments) may fail.")

        # If there are no (valid) credentials available
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("   🔄 [YouTube]: Refreshing expired token...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"   ❌ [YouTube]: Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                if not self.allow_interactive:
                    print("   ❌ [YouTube ERROR]: Valid 'token.pickle' not found or invalid in CI environment.")
                    print("      Authentication cannot be performed interactively. Skipped.")
                    return None
                else:
                    print("   🌐 [YouTube]: Starting local authentication flow...")
                    # Ask for core + optional scopes during interactive re-auth
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file,
                        self.scopes + self.optional_scopes,
                    )
                    creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            if creds:
                with open(self.token_file, "wb") as token:
                    pickle.dump(creds, token)
        return creds

    # ──────────────────────────────────────────────────────
    # VIDEO UPLOAD (Enhanced with post-upload actions)
    # ──────────────────────────────────────────────────────

    def upload_video(self, file_path, title, description, tags=None, video_type="shorts", publish_at=None):
        """
        Uploads a video to YouTube with chunked resumable upload.
        After upload, automatically:
          1. Adds to appropriate playlist
          2. Posts a pinned engagement comment
          3. Sets custom thumbnail (if available)

        Args:
          publish_at: Optional datetime (UTC). If provided, the video is uploaded
                      as private with a publishAt so YouTube auto-flips to public
                      at that time (peak-hour scheduling).
        """
        if not self.credentials or not self.youtube:
            print("   ⚠️ [YouTube]: Upload skipped (No credentials).")
            return None

        print(f"🚀 [YouTube]: Starting upload for {title}...")

        # Get file size for progress tracking
        file_size = os.path.getsize(file_path)
        file_size_gb = file_size / (1024**3)
        print(f"   📦 File size: {file_size_gb:.2f} GB")

        is_shorts = video_type == "shorts"
        upload_title = f"{title} #Shorts" if is_shorts else title
        
        # Enhanced description with cross-links
        recent_videos = self._get_recent_videos(count=3)
        upload_description = self._build_smart_description(
            description, tags or [], recent_videos, is_shorts
        )
        
        upload_tags = tags or (["shorts", "viral", "knowledge"] if is_shorts else ["longform", "ambient", "education"])
        
        # ─── STRICT SANITIZATION (Prevent HTTP 400 Errors) ───
        # 1. Title limit: 100 characters max, no angle brackets
        upload_title = upload_title.replace("<", "").replace(">", "").strip()
        if len(upload_title) > 100:
            upload_title = upload_title[:97] + "..."
            
        # 2. Description limit: 5000 characters max, no angle brackets
        upload_description = upload_description.replace("<", "").replace(">", "").strip()
        if len(upload_description) > 5000:
            upload_description = upload_description[:4996] + "..."
            
        # 3. Tags limit: 400 total chars sum, individual tag max length 30, no angle brackets
        sanitized_tags = []
        c_len = 0
        for tag in upload_tags:
            cl_tag = str(tag).replace("<", "").replace(">", "").replace('"', '').strip()
            if len(cl_tag) > 30:
                cl_tag = cl_tag[:30]
            if cl_tag and (c_len + len(cl_tag) + 1) < 450:
                sanitized_tags.append(cl_tag)
                c_len += len(cl_tag) + 1
        upload_tags = sanitized_tags
        
        # Determine privacy + scheduled publish
        privacy_status = "public"
        publish_at_iso = None
        if publish_at is not None:
            try:
                # Must be at least a few minutes in the future
                now = datetime.utcnow()
                if publish_at.tzinfo is not None:
                    publish_at_utc = publish_at.astimezone(tz=None).replace(tzinfo=None)
                else:
                    publish_at_utc = publish_at
                if publish_at_utc > now + timedelta(minutes=5):
                    privacy_status = "private"
                    publish_at_iso = publish_at_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    print(f"   ⏰ [YouTube]: Scheduled publish at {publish_at_iso} (UTC)")
                else:
                    print(f"   ⚠️ [YouTube]: publish_at is in the past, uploading publicly now")
            except Exception as e:
                print(f"   ⚠️ [YouTube]: invalid publish_at ({e}), uploading publicly now")

        status_dict = {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        }
        if publish_at_iso:
            status_dict["publishAt"] = publish_at_iso

        body = {
            "snippet": {
                "title": upload_title,
                "description": upload_description,
                "tags": upload_tags,
                "categoryId": "27" # Education
            },
            "status": status_dict
        }

        # Chunk size: 50MB for large files, -1 for small files
        chunk_size = 50 * 1024 * 1024 if file_size > 100 * 1024 * 1024 else -1

        try:
            insert_request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=MediaFileUpload(
                    file_path,
                    chunksize=chunk_size,
                    resumable=True,
                )
            )

            response = None
            retry_count = 0
            max_retries = 10

            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status:
                        pct = int(status.progress() * 100)
                        uploaded_gb = (status.progress() * file_size) / (1024**3)
                        print(f"   📊 Upload: {pct}% ({uploaded_gb:.1f}/{file_size_gb:.1f} GB)")
                    retry_count = 0  # Reset on success
                except Exception as chunk_err:
                    error_str = str(chunk_err)
                    if "quotaExceeded" in error_str or "uploadLimitExceeded" in error_str:
                        raise chunk_err  # Don't retry quota errors
                    retry_count += 1
                    if retry_count > max_retries:
                        raise chunk_err
                    import time as _time
                    wait = min(2 ** retry_count, 60)
                    print(f"   ⚠️ Chunk error, retry {retry_count}/{max_retries} in {wait}s...")
                    _time.sleep(wait)

            video_id = response.get("id")
            print(f"✅ [YouTube]: Video uploaded successfully! ID: {video_id}")

            # ─── POST-UPLOAD ACTIONS ────────────────────────
            if video_id:
                self._post_upload_actions(video_id, title, tags, video_type)

            return video_id

        except Exception as e:
            print(f"\n❌ [YouTube ERROR]: Upload failed.")
            error_str = str(e)
            if "uploadLimitExceeded" in error_str:
                print("   ⚠️ Daily upload limit reached.")
                print("   ✅ FIX: Wait 24 hours or verify your channel with phone.")
            elif "quotaExceeded" in error_str:
                print("   ⚠️ YouTube API daily quota exceeded.")
                print("   ✅ FIX: Quota resets at midnight Pacific Time (~08:00 UTC / 11:00 Turkey).")
            else:
                print(f"   ⚠️ ERROR: {error_str}")
            return None

    def _post_upload_actions(self, video_id, title, tags, video_type):
        """Run all post-upload enhancement actions."""
        # Action 1: Add to playlist
        try:
            playlist_name = self._detect_playlist(title, tags)
            if playlist_name:
                playlist_id = self.get_or_create_playlist(playlist_name)
                if playlist_id:
                    self.add_to_playlist(playlist_id, video_id)
                    print(f"   📋 [Playlist]: Added to '{playlist_name}'")
        except Exception as e:
            print(f"   ⚠️ [Playlist]: Failed - {e}")

        # Action 2: Post pinned engagement comment
        try:
            comment_category = self._detect_comment_category(title, tags)
            comment = random.choice(
                ENGAGEMENT_COMMENTS.get(comment_category, ENGAGEMENT_COMMENTS["default"])
            )
            self.post_comment(video_id, comment)
            print(f"   💬 [Comment]: Posted engagement comment")
        except Exception as e:
            print(f"   ⚠️ [Comment]: Failed - {e}")

        # Action 3: Set thumbnail (if one exists next to the video)
        try:
            thumb_path = os.path.join(
                self.project_root, "assets", "branding", f"thumb_{video_id}.jpg"
            )
            if os.path.exists(thumb_path):
                self.set_thumbnail(video_id, thumb_path)
                print(f"   🎨 [Thumbnail]: Custom thumbnail set")
        except Exception as e:
            print(f"   ⚠️ [Thumbnail]: Failed - {e}")

    # ──────────────────────────────────────────────────────
    # SMART DESCRIPTION BUILDER
    # ──────────────────────────────────────────────────────

    def _build_smart_description(self, original_desc, tags, recent_videos, is_shorts):
        """Build SEO-optimized description with cross-links."""
        parts = [original_desc.strip()]
        
        # Add subscribe CTA
        parts.append("")
        parts.append("🔔 Subscribe for more: https://youtube.com/@StreamGlobal?sub_confirmation=1")
        
        # Add recent video links
        if recent_videos:
            parts.append("")
            parts.append("📺 Watch Next:")
            for v in recent_videos[:3]:
                vtitle = v.get("title", "")[:50]
                vid = v.get("id", "")
                if vid:
                    parts.append(f"▶️ {vtitle}: https://youtu.be/{vid}")
        
        # Add hashtags
        if is_shorts:
            parts.append("")
            tag_str = " ".join(f"#{t.replace(' ', '')}" for t in tags[:5] if t)
            parts.append(f"#Shorts #Viral #Knowledge {tag_str}")
        else:
            parts.append("")
            tag_str = " ".join(f"#{t.replace(' ', '')}" for t in tags[:8] if t)
            parts.append(tag_str)
        
        return "\n".join(parts)

    def _get_recent_videos(self, count=3):
        """Get the most recent uploaded videos for cross-linking."""
        if not self.youtube:
            return []
        try:
            # Get channel's uploads playlist
            channels = self.youtube.channels().list(
                part="contentDetails", mine=True
            ).execute()
            
            if not channels.get("items"):
                return []
            
            uploads_id = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            
            response = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_id,
                maxResults=count + 1  # +1 to exclude the current upload
            ).execute()
            
            videos = []
            for item in response.get("items", []):
                videos.append({
                    "id": item["snippet"]["resourceId"]["videoId"],
                    "title": item["snippet"]["title"],
                })
            return videos
        except Exception as e:
            print(f"   ⚠️ [RecentVideos]: Could not fetch - {e}")
            return []

    # ──────────────────────────────────────────────────────
    # PLAYLIST MANAGEMENT
    # ──────────────────────────────────────────────────────

    def create_playlist(self, title, description="", privacy="public"):
        """Create a new YouTube playlist."""
        if not self.youtube:
            return None
        body = {
            "snippet": {
                "title": title,
                "description": description or f"Best {title} videos by StreamGlobal",
            },
            "status": {"privacyStatus": privacy},
        }
        result = self.youtube.playlists().insert(
            part="snippet,status", body=body
        ).execute()
        playlist_id = result.get("id")
        print(f"   📋 [Playlist]: Created '{title}' (ID: {playlist_id})")
        return playlist_id

    def add_to_playlist(self, playlist_id, video_id, position=0):
        """Add a video to a playlist."""
        if not self.youtube:
            return None
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
                "position": position,
            }
        }
        return self.youtube.playlistItems().insert(
            part="snippet", body=body
        ).execute()

    def get_or_create_playlist(self, title):
        """Get existing playlist by title or create a new one."""
        if title in self._playlist_cache:
            return self._playlist_cache[title]
            
        if not self.youtube:
            return None
            
        try:
            # Check existing playlists
            playlists = self.youtube.playlists().list(
                part="snippet", mine=True, maxResults=50
            ).execute()
            
            for p in playlists.get("items", []):
                if p["snippet"]["title"] == title:
                    self._playlist_cache[title] = p["id"]
                    return p["id"]
            
            # Create new playlist
            playlist_id = self.create_playlist(title)
            if playlist_id:
                self._playlist_cache[title] = playlist_id
            return playlist_id
        except Exception as e:
            print(f"   ⚠️ [Playlist]: get_or_create failed - {e}")
            return None

    def _detect_playlist(self, title, tags):
        """Detect which playlist a video belongs to based on title and tags."""
        combined = (title + " " + " ".join(tags or [])).lower()
        
        for keyword, playlist_name in PLAYLIST_MAP.items():
            if keyword in combined:
                return playlist_name
        
        return "Facts & Knowledge 💡"  # Default playlist

    # ──────────────────────────────────────────────────────
    # COMMENT ENGAGEMENT
    # ──────────────────────────────────────────────────────

    def post_comment(self, video_id, text):
        """Post a comment on a video."""
        if not self.youtube:
            return None
        body = {
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {"textOriginal": text}
                }
            }
        }
        try:
            result = self.youtube.commentThreads().insert(
                part="snippet", body=body
            ).execute()
            return result.get("id")
        except Exception as e:
            print(f"   ⚠️ [Comment]: Post failed - {e}")
            return None

    def _detect_comment_category(self, title, tags):
        """Detect comment category based on title/tags."""
        combined = (title + " " + " ".join(tags or [])).lower()
        
        if any(w in combined for w in ["animal", "cat", "dog", "wildlife", "nature", "forest"]):
            return "nature"
        if any(w in combined for w in ["sleep", "rain", "ambient", "asmr", "fireplace", "relax"]):
            return "ambient"
        return "facts"

    # ──────────────────────────────────────────────────────
    # THUMBNAIL MANAGEMENT
    # ──────────────────────────────────────────────────────

    def set_thumbnail(self, video_id, thumbnail_path):
        """Set a custom thumbnail for a video."""
        if not self.youtube:
            return None
        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            ).execute()
            print(f"   🎨 [Thumbnail]: Set for video {video_id}")
            return True
        except Exception as e:
            print(f"   ⚠️ [Thumbnail]: Set failed - {e}")
            return None

    # ──────────────────────────────────────────────────────
    # SEO: YouTube Search Suggestions
    # ──────────────────────────────────────────────────────

    @staticmethod
    def get_youtube_suggestions(query, language="en"):
        """
        Fetch YouTube auto-suggest keywords for SEO optimization.
        Free API, no key required.
        """
        try:
            url = "https://suggestqueries-clients6.youtube.com/complete/search"
            params = {
                "client": "youtube",
                "q": query,
                "ds": "yt",
                "hl": language,
            }
            resp = requests.get(url, params=params, timeout=5)
            text = resp.text
            start = text.index("(") + 1
            end = text.rindex(")")
            data = json.loads(text[start:end])
            suggestions = [item[0] for item in data[1] if isinstance(item, list) and item]
            return suggestions[:10]
        except Exception:
            return []

    @staticmethod
    def optimize_title_with_keywords(title, keywords):
        """
        Optimize a title by incorporating high-search-volume keywords.
        Keeps the original title's intent but makes it more discoverable.
        """
        if not keywords:
            return title
        
        # Find the most relevant keyword that's not already in the title
        title_lower = title.lower()
        for kw in keywords:
            if kw.lower() not in title_lower and len(kw) > 5:
                # Don't make title too long
                if len(title) + len(kw) < 90:
                    return f"{title} | {kw.title()}"
                break
        
        return title
