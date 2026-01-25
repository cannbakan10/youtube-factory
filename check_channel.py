import os
import pickle
from googleapiclient.discovery import build

def check_channel():
    token_path = os.path.dirname(os.path.abspath(__file__)) + "/token.pickle"
    if not os.path.exists(token_path):
        print("Token bulunamadı, giriş yapılmamış.")
        return

    with open(token_path, "rb") as token:
        creds = pickle.load(token)
    
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.channels().list(part="snippet", mine=True)
    response = request.execute()
    
    if "items" in response:
        channel = response["items"][0]["snippet"]
        print(f"\n📺 Yükleme Yapılan Kanal: {channel['title']}")
        print(f"🔗 Kanal Linki: https://youtube.com/channel/{response['items'][0]['id']}")
    else:
        print("Kanal bilgisi alınamadı.")

if __name__ == "__main__":
    check_channel()
