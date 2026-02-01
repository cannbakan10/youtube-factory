from pytubefix import YouTube, Search
import os
import time

def download_youtube_music_themed_v2():
    output_dir = "/Users/sergenbakan/Youtuber/youtube-factory/assets/templates/music"
    os.makedirs(output_dir, exist_ok=True)
    
    themes = {
        "cinematic": "Epic Cinematic No Copyright Music",
        "tension": "Dark Tension Suspense No Copyright Music",
        "mystery": "Mysterious Mystery Background No Copyright",
        "documentary": "Professional Documentary Background No Copyright",
        "inspiring": "Inspirational Soft Piano No Copyright",
        "upbeat": "Happy Upbeat Corporate No Copyright Music",
        "horror": "Terrifying Horror Ambient No Copyright Music",
        "lofi": "Lofi Hip Hop Chill No Copyright Music",
        "cyberpunk": "Cyberpunk Synthwave No Copyright Music",
        "emotional": "Sad Emotional Piano No Copyright Music",
        "nature": "Nature Wildlife Background Music No Copyright",
        "retro": "80s Retro Synthwave No Copyright",
        "jazz": "Cafe Jazz Background Music No Copyright",
        "epic": "Powerful Battle Epic Music No Copyright",
        "natgeo": "National Geographic Style Music No Copyright"
    }
    
    downloaded_total = 0
    tracks_per_theme = 5
    max_duration_sec = 600 # Skip anything longer than 10 minutes
    
    for base_name, query in themes.items():
        print(f"\n🎧 Theme: {base_name.upper()}")
        try:
            s = Search(query)
            if not s.results:
                print(f"⚠️ No results for {query}")
                continue
            
            # Filter and take N results
            valid_results = []
            for v in s.results:
                if v.length and v.length < max_duration_sec:
                    valid_results.append(v)
                if len(valid_results) >= tracks_per_theme:
                    break
            
            if not valid_results:
                print(f"⚠️ No short tracks found for {query}")
                valid_results = s.results[:tracks_per_theme] # Fallback if none found
            
            for idx, video in enumerate(valid_results):
                target_filename = f"{base_name}_{idx + 1}.mp3"
                target_path = os.path.join(output_dir, target_filename)
                
                if os.path.exists(target_path):
                    print(f"   ⏭️ Skipping {target_filename} (exists)")
                    continue
                
                try:
                    print(f"   📥 [{idx+1}/{tracks_per_theme}] {video.title[:50]}...")
                    stream = video.streams.get_audio_only()
                    if stream:
                        stream.download(output_path=output_dir, filename=target_filename)
                        print(f"      ✅ Success: {target_filename}")
                        downloaded_total += 1
                        time.sleep(2) # Polite delay
                    else:
                        print(f"      ⚠️ No audio stream.")
                except Exception as e:
                    print(f"      ❌ Skip: {e}")
            
        except Exception as e:
            print(f"❌ Error with theme {base_name}: {e}")

    print(f"\n🏁 Finished! Total new tracks: {downloaded_total}")

if __name__ == "__main__":
    download_youtube_music_themed_v2()
