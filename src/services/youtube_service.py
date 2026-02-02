import os
import pickle
import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class YouTubeService:
    def __init__(self):
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        # Determine project root relative to this file
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.client_secrets_file = os.path.join(self.project_root, "client_secrets.json")
        self.token_file = os.path.join(self.project_root, "token.pickle")
        self.credentials = self._authenticate()
        self.youtube = build("youtube", "v3", credentials=self.credentials)

    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_file):
            print(f"   🔑 [YouTube]: Loading credentials from {self.token_file}")
            with open(self.token_file, "rb") as token:
                creds = pickle.load(token)
        
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
                if os.getenv("GITHUB_ACTIONS"):
                    print("   ❌ [YouTube ERROR]: Valid 'token.pickle' not found in GitHub Actions environment.")
                    print("      Authentication cannot be performed interactively in CI/CD.")
                    print("      Please generate a fresh 'token.pickle' locally and update the GITHUB SECRET.")
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

    def upload_video(self, file_path, title, description, tags=None):
        """
        Uploads a video to YouTube with error handling for quota and limits.
        """
        if not self.credentials:
            print("   ⚠️ [YouTube]: Upload skipped (No credentials).")
            return None

        print(f"🚀 [YouTube]: Starting upload for {title}...")
        
        body = {
            "snippet": {
                "title": f"{title} #Shorts",
                "description": f"{description}\n\n#Shorts #Viral #Knowledge",
                "tags": tags or ["shorts", "viral", "knowledge"],
                "categoryId": "27" # Education
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        try:
            # Call the API's videos.insert method to create and upload the video.
            insert_request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
            )

            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    print(f"   📊 Upload Progress: {int(status.progress() * 100)}%")

            video_id = response.get("id")
            print(f"✅ [YouTube]: Video uploaded successfully! ID: {video_id}")
            return video_id

        except Exception as e:
            print(f"\n❌ [YouTube ERROR]: Upload failed.")
            error_str = str(e)
            if "uploadLimitExceeded" in error_str:
                print("   ⚠️ DURUM: YouTube günlük video yükleme sınırına takıldınız.")
                print("   💡 NEDEN: Yeni veya doğrulanmamış kanalların günlük Shorts yükleme limiti düşüktür.")
                print("   ✅ ÇÖZÜM: 24 saat beklemeniz veya kanalınızı telefonla doğrulamanız gerekir.")
            elif "quotaExceeded" in error_str:
                print("   ⚠️ DURUM: Google Cloud API kotası doldu.")
                print("   ✅ ÇÖZÜM: Yarın tekrar deneyin veya Google Cloud Console'dan ek kota isteyin.")
            else:
                print(f"   ⚠️ HATA DETAYI: {error_str}")
            return None
