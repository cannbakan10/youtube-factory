"""
TikTok Content Posting API Service

Handles OAuth2 authentication and video upload to TikTok
using the official Content Posting API.

Flow:
  1. Authenticate → client access token (client_credentials)
  2. User auth → user access token (authorization_code with video.publish scope)
  3. Query creator info → get max duration, privacy options
  4. Init video upload → get upload_url + publish_id
  5. Upload video chunks → PUT to upload_url
  6. Check status → poll publish_id until done

API Reference: https://developers.tiktok.com/doc/content-posting-api-get-started
"""

import os
import json
import time
import requests
from typing import Optional, Dict, List

from src.utils.logger import get_logger

logger = get_logger(__name__)

# TikTok API endpoints
TIKTOK_AUTH_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
TIKTOK_VIDEO_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_PUBLISH_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

# Token storage
TOKEN_FILE = "tiktok_tokens.json"


class TikTokService:
    """Service for uploading videos to TikTok via Content Posting API."""

    def __init__(self):
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.token_file = os.path.join(self.project_root, "data", TOKEN_FILE)

        # Load credentials from environment
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "")

        # User tokens (loaded from file or env)
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "")
        self.refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN", "")
        self.open_id = os.getenv("TIKTOK_OPEN_ID", "")

        # Try loading stored tokens
        if not self.access_token:
            self._load_tokens()

        self.authenticated = bool(self.access_token)

        if self.authenticated:
            logger.info("✅ TikTok Service authenticated")
        else:
            logger.info("ℹ️ TikTok Service: No access token. (Set up via --tiktok-auth if needed)")

    # ──────────────────────────────────────────────────────
    # TOKEN MANAGEMENT
    # ──────────────────────────────────────────────────────

    def _load_tokens(self):
        """Load stored tokens from file."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                self.access_token = data.get("access_token", "")
                self.refresh_token = data.get("refresh_token", "")
                self.open_id = data.get("open_id", "")
                logger.info("🔑 TikTok tokens loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load TikTok tokens: {e}")

    def _save_tokens(self):
        """Save tokens to file."""
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "open_id": self.open_id,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(self.token_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("💾 TikTok tokens saved")

    # ──────────────────────────────────────────────────────
    # OAUTH2 AUTHENTICATION
    # ──────────────────────────────────────────────────────

    def get_auth_url(self, redirect_uri: str = "http://localhost:8080/callback") -> str:
        """
        Generate the TikTok OAuth2 authorization URL.
        User must visit this URL to grant video.publish permission.
        """
        params = {
            "client_key": self.client_key,
            "scope": "video.publish",
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": "tiktok_auth_state",
        }
        base_url = "https://www.tiktok.com/v2/auth/authorize/"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        auth_url = f"{base_url}?{query}"
        return auth_url

    def exchange_code_for_token(
        self, code: str, redirect_uri: str = "http://localhost:8080/callback"
    ) -> bool:
        """
        Exchange authorization code for access token.
        Called after user authorizes the app.
        """
        payload = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        try:
            resp = requests.post(TIKTOK_AUTH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if "access_token" in data:
                self.access_token = data["access_token"]
                self.refresh_token = data.get("refresh_token", "")
                self.open_id = data.get("open_id", "")
                self.authenticated = True
                self._save_tokens()
                logger.info("✅ TikTok OAuth2 token obtained successfully")
                return True

            # TikTok wraps in data object sometimes
            if "data" in data and "access_token" in data["data"]:
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"].get("refresh_token", "")
                self.open_id = data["data"].get("open_id", "")
                self.authenticated = True
                self._save_tokens()
                logger.info("✅ TikTok OAuth2 token obtained successfully")
                return True

            logger.error(f"TikTok token exchange failed: {data}")
            return False

        except Exception as e:
            logger.error(f"TikTok token exchange error: {e}")
            return False

    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            logger.error("No refresh token available")
            return False

        payload = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }

        try:
            resp = requests.post(TIKTOK_AUTH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            token_data = data.get("data", data)
            if "access_token" in token_data:
                self.access_token = token_data["access_token"]
                self.refresh_token = token_data.get("refresh_token", self.refresh_token)
                self.open_id = token_data.get("open_id", self.open_id)
                self._save_tokens()
                logger.info("🔄 TikTok access token refreshed")
                return True

            logger.error(f"Token refresh failed: {data}")
            return False

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False

    # ──────────────────────────────────────────────────────
    # CREATOR INFO
    # ──────────────────────────────────────────────────────

    def get_creator_info(self) -> Optional[Dict]:
        """Query creator info to get posting capabilities."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        try:
            resp = requests.post(TIKTOK_CREATOR_INFO_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if data.get("error", {}).get("code") == "ok":
                creator = data.get("data", {})
                logger.info(
                    f"👤 TikTok Creator: @{creator.get('creator_username', '?')} | "
                    f"Max duration: {creator.get('max_video_post_duration_sec', '?')}s"
                )
                return creator

            # Token might be expired, try refresh
            if data.get("error", {}).get("code") in ("access_token_invalid", "token_expired"):
                logger.info("🔄 Token expired, refreshing...")
                if self.refresh_access_token():
                    return self.get_creator_info()

            logger.error(f"Creator info failed: {data}")
            return None

        except Exception as e:
            logger.error(f"Creator info error: {e}")
            return None

    # ──────────────────────────────────────────────────────
    # VIDEO UPLOAD
    # ──────────────────────────────────────────────────────

    def upload_video(
        self,
        file_path: str,
        title: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        disable_comment: bool = False,
        disable_duet: bool = False,
        disable_stitch: bool = False,
        video_cover_timestamp_ms: int = 1000,
    ) -> Optional[str]:
        """
        Upload a video to TikTok.

        Args:
            file_path: Path to the video file (MP4)
            title: Video title/caption with hashtags
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, or SELF_ONLY
            disable_comment: Disable comments
            disable_duet: Disable duets
            disable_stitch: Disable stitches
            video_cover_timestamp_ms: Cover image timestamp in milliseconds

        Returns:
            publish_id if successful, None otherwise
        """
        if not self.authenticated:
            logger.error("TikTok not authenticated. Run --tiktok-auth first.")
            return None

        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            return None

        # Get file size
        file_size = os.path.getsize(file_path)
        if file_size > 4 * 1024 * 1024 * 1024:  # 4GB limit
            logger.error(f"Video too large: {file_size / (1024**3):.1f}GB (max 4GB)")
            return None

        logger.info(f"🎬 TikTok: Uploading '{title[:50]}...' ({file_size / (1024**2):.1f}MB)")

        # Determine chunk strategy
        chunk_size = min(file_size, 64 * 1024 * 1024)  # 64MB chunks max
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        # Step 1: Initialize upload
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        init_payload = {
            "post_info": {
                "title": title[:150],  # TikTok title limit
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_comment": disable_comment,
                "disable_stitch": disable_stitch,
                "video_cover_timestamp_ms": video_cover_timestamp_ms,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

        try:
            resp = requests.post(TIKTOK_VIDEO_INIT_URL, headers=headers, json=init_payload)
            resp.raise_for_status()
            data = resp.json()

            # Check for token expiry
            if data.get("error", {}).get("code") in ("access_token_invalid", "token_expired"):
                logger.info("🔄 Token expired, refreshing...")
                if self.refresh_access_token():
                    return self.upload_video(
                        file_path, title, privacy_level,
                        disable_comment, disable_duet, disable_stitch,
                        video_cover_timestamp_ms
                    )
                return None

            if data.get("error", {}).get("code") != "ok":
                logger.error(f"TikTok init failed: {data}")
                return None

            publish_id = data["data"]["publish_id"]
            upload_url = data["data"]["upload_url"]
            logger.info(f"📤 Upload initialized: {publish_id}")

        except Exception as e:
            logger.error(f"TikTok init error: {e}")
            return None

        # Step 2: Upload video chunks
        try:
            with open(file_path, "rb") as f:
                for chunk_idx in range(total_chunks):
                    chunk_data = f.read(chunk_size)
                    offset = chunk_idx * chunk_size
                    end_byte = offset + len(chunk_data) - 1

                    chunk_headers = {
                        "Content-Range": f"bytes {offset}-{end_byte}/{file_size}",
                        "Content-Type": "video/mp4",
                    }

                    upload_resp = requests.put(
                        upload_url, headers=chunk_headers, data=chunk_data
                    )

                    if upload_resp.status_code not in (200, 201):
                        logger.error(
                            f"Chunk {chunk_idx + 1}/{total_chunks} upload failed: "
                            f"{upload_resp.status_code} {upload_resp.text}"
                        )
                        return None

                    progress = int((chunk_idx + 1) / total_chunks * 100)
                    logger.info(f"   📊 Upload progress: {progress}%")

        except Exception as e:
            logger.error(f"Video upload error: {e}")
            return None

        # Step 3: Check publish status
        logger.info("⏳ Waiting for TikTok to process...")
        final_status = self._wait_for_publish(publish_id)

        if final_status == "PUBLISH_COMPLETE":
            logger.info(f"✅ TikTok: Video published successfully! ID: {publish_id}")
            return publish_id
        else:
            logger.warning(f"⚠️ TikTok publish status: {final_status}")
            return publish_id  # Still return ID, might still be processing

    def _wait_for_publish(self, publish_id: str, max_wait: int = 120) -> str:
        """Poll publish status until complete or timeout."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                resp = requests.post(
                    TIKTOK_PUBLISH_STATUS_URL,
                    headers=headers,
                    json={"publish_id": publish_id},
                )
                data = resp.json()
                status = data.get("data", {}).get("status", "UNKNOWN")

                if status == "PUBLISH_COMPLETE":
                    return status
                elif status in ("FAILED", "PUBLISH_FAILED"):
                    fail_reason = data.get("data", {}).get("fail_reason", "unknown")
                    logger.error(f"TikTok publish failed: {fail_reason}")
                    return status

                # Still processing...
                time.sleep(5)

            except Exception as e:
                logger.warning(f"Status check error: {e}")
                time.sleep(5)

        return "TIMEOUT"

    # ──────────────────────────────────────────────────────
    # LOCAL AUTH SERVER (for initial OAuth setup)
    # ──────────────────────────────────────────────────────

    def start_auth_flow(self):
        """
        Start the OAuth2 flow with a local callback server.
        Used for initial authentication setup.
        """
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse, parse_qs

        redirect_uri = "http://localhost:8080/callback"
        auth_url = self.get_auth_url(redirect_uri)

        print("\n" + "=" * 60)
        print("🔐 TikTok Authentication")
        print("=" * 60)
        print(f"\n1. Open this URL in your browser:\n\n{auth_url}\n")
        print("2. Log in and authorize the app")
        print("3. You'll be redirected back here automatically")
        print("=" * 60)

        # Capture the authorization code
        auth_code = [None]

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" in params:
                    auth_code[0] = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>&#10004; TikTok Authorization Successful!</h1>"
                        b"<p>You can close this window now.</p></body></html>"
                    )
                else:
                    error = params.get("error", ["unknown"])[0]
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        f"<html><body><h1>&#10060; Authorization Failed: {error}</h1></body></html>".encode()
                    )

            def log_message(self, format, *args):
                pass  # Suppress server logs

        server = HTTPServer(("localhost", 8080), CallbackHandler)
        server.timeout = 120  # 2 minute timeout

        try:
            server.handle_request()  # Handle one request
        finally:
            server.server_close()

        if auth_code[0]:
            print(f"\n✅ Authorization code received!")
            success = self.exchange_code_for_token(auth_code[0], redirect_uri)
            if success:
                print("✅ TikTok authentication complete! Tokens saved.")
            else:
                print("❌ Failed to exchange code for token.")
            return success
        else:
            print("❌ No authorization code received.")
            return False
