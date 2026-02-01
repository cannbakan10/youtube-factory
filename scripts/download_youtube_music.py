import subprocess
import os

def download_youtube_music():
    output_dir = "/Users/sergenbakan/Youtuber/youtube-factory/assets/templates/music"
    os.makedirs(output_dir, exist_ok=True)
    
    ytdlp_path = "/Users/sergenbakan/Library/Python/3.9/bin/yt-dlp"
    
    search_queries = [
        "ytsearch1:NCS Cinematic No Copyright Music",
        "ytsearch1:NCS Tension No Copyright Music",
        "ytsearch1:NCS Mystery No Copyright Music",
        "ytsearch1:NCS Documentary Background Music",
        "ytsearch1:NCS Inspiring Background Music",
        "ytsearch1:Breaking Copyright Tension Music",
        "ytsearch1:Infraction No Copyright Music Documentary",
        "ytsearch1:Audio Library No Copyright Music Cinematic",
        "ytsearch1:Upbeat No Copyright Background Music",
        "ytsearch1:Dark Ambient No Copyright Music"
    ]
    
    import time
    import random
    
    for i, query in enumerate(search_queries):
        print(f"🔍 Searching and downloading: {query}...")
        try:
            # yt-dlp command with ios client
            filename = f"bgm_yt_{i+1}"
            output_template = os.path.join(output_dir, f"{filename}.%(ext)s")
            
            cmd = [
                ytdlp_path,
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--extractor-args", "youtube:player_client=ios",
                "-o", output_template,
                query
            ]
            
            subprocess.run(cmd, check=True)
            print(f"✅ Success: {filename}.mp3 created.")
            
            time.sleep(random.uniform(5, 10)) # Longer sleep
            
        except Exception as e:
            print(f"❌ Error downloading {query}: {e}")
            time.sleep(2)

if __name__ == "__main__":
    download_youtube_music()
