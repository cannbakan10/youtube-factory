import os
import pickle
import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class YouTubeService:
    def __init__(self):
        self.scopes = [
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
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
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file, self.scopes)
                    creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            if creds:
                with open(self.token_file, "wb") as token:
                    pickle.dump(creds, token)
        return creds

    def upload_video(self, file_path, title, description, tags=None, video_type="shorts"):
        """
        Uploads a video to YouTube with chunked resumable upload.
        Handles large files (10+ GB) with proper chunk sizes and retry logic.
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
        upload_description = (
            f"{description}\n\n#Shorts #Viral #Knowledge"
            if is_shorts
            else description
        )
        upload_tags = tags or (["shorts", "viral", "knowledge"] if is_shorts else ["longform", "ambient", "education"])
        
        body = {
            "snippet": {
                "title": upload_title,
                "description": upload_description,
                "tags": upload_tags,
                "categoryId": "27" # Education
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
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
