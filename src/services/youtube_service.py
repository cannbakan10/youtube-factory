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
            with open(self.token_file, "rb") as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_file, "wb") as token:
                pickle.dump(creds, token)
        return creds

    def upload_video(self, file_path, title, description, tags=None):
        """
        Uploads a video to YouTube.
        """
        print(f"🚀 [YouTube]: Starting upload for {title}...")
        
        body = {
            "snippet": {
                "title": f"{title} #Shorts",
                "description": f"{description}\n\n#Shorts #Viral #Knowledge",
                "tags": tags or ["shorts", "viral", "knowledge"],
                "categoryId": "27" # Education
            },
            "status": {
                "privacyStatus": "public", # Now directly Public!
                "selfDeclaredMadeForKids": False
            }
        }

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
