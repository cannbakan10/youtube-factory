#!/usr/bin/env python3
"""
Freepik Ambient Video Producer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Search Freepik for high-quality ambient clips (fireplace, forest, rain etc.),
download them, loop to target duration (1h-16h), and upload to YouTube.

Usage:
    python produce_ambient.py --type fireplace --hours 8
    python produce_ambient.py --type forest --hours 1 --upload
    python produce_ambient.py --list                          # list all types
    python produce_ambient.py --type rain --hours 12 --upload --retry
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.services.freepik_service import FreepikService
from src.services.youtube_service import YouTubeService
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AMBIENT CATEGORIES — Freepik search terms + YouTube SEO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMBIENT_TYPES: Dict[str, Dict] = {
    "fireplace": {
        "search_queries": [
            "fireplace burning", "cozy fireplace", "crackling fire",
            "fireplace close up", "wood fire burning",
        ],
        "title": "🔥 {hours} Hours Cozy Fireplace Ambience | Crackling Fire Sounds for Sleep, Study & Relaxation",
        "description": (
            "🔥 {hours} Hours of Cozy Fireplace Ambience with Crackling Fire Sounds\n\n"
            "Enjoy this ultra-relaxing fireplace video with the soothing sound of crackling logs. "
            "Perfect for creating a warm, cozy atmosphere in your home.\n\n"
            "✨ Perfect for:\n"
            "🛏️ Deep Sleep & Insomnia Relief\n"
            "📚 Studying & Homework Focus\n"
            "🧘 Meditation & Yoga\n"
            "💻 Work From Home Background\n"
            "🎄 Cozy Winter Nights\n"
            "👶 Baby Sleep Aid\n"
            "🐱 Pet Relaxation\n\n"
            "⏱️ Duration: {hours} Hours (No interruptions)\n"
            "🎧 Audio: Natural crackling fire sounds\n"
            "📺 Video: Seamless looping fireplace\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔔 Subscribe for more ambient content!\n"
            "👍 Like this video if it helps you relax!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "#fireplace #ambience #sleep #relax #study #cozy #crackling #fire "
            "#{hours}hours #sleepsounds #relaxation #whitenoise #ASMR #ambient #focus"
        ),
        "tags": [
            "fireplace", "fireplace ambience", "crackling fire",
            "fireplace for sleep", "sleep sounds", "study music",
            "relaxation", "cozy fireplace", "fire sounds",
            "ambient sounds", "fireplace ASMR", "cozy ambience",
            "winter fireplace", "relaxing fire", "white noise",
            "deep sleep", "focus music", "meditation",
            "crackling fire sounds", "cozy fire", "sleep aid",
            "background noise", "fireplace loop",
        ],
    },
    "forest": {
        "search_queries": [
            "forest nature", "green forest", "forest path",
            "woodland trees", "forest sunlight",
        ],
        "title": "🌲 {hours} Hours Forest Ambience | Birds Singing, Nature Sounds for Relaxation & Focus",
        "description": (
            "🌲 {hours} Hours of Peaceful Forest Ambience\n\n"
            "Immerse yourself in the beautiful sounds of nature — birds singing, "
            "gentle wind through the trees, and the peaceful stillness of the forest.\n\n"
            "✨ Perfect for:\n"
            "🧘 Meditation & Mindfulness\n"
            "📚 Studying & Deep Focus\n"
            "🛏️ Sleep & Relaxation\n"
            "💻 Work Background\n\n"
            "⏱️ Duration: {hours} Hours\n"
            "🎧 Audio: Natural forest sounds\n\n"
            "#forest #nature #birdsinging #relaxation #sleep #study #ambient "
            "#{hours}hours #naturessounds #meditation #focus"
        ),
        "tags": [
            "forest ambience", "nature sounds", "birds singing",
            "forest sounds", "relaxation", "sleep", "study",
            "meditation", "peaceful nature", "green forest",
            "woodland sounds", "deep focus", "ambient",
        ],
    },
    "rain": {
        "search_queries": [
            "heavy rain", "rain window", "rain drops",
            "rain night", "pouring rain",
        ],
        "title": "🌧️ {hours} Hours Heavy Rain Sounds | Rain for Sleep, Study & Relaxation",
        "description": (
            "🌧️ {hours} Hours of Heavy Rain Sounds\n\n"
            "Fall asleep fast with the soothing sound of heavy rain. "
            "Perfect white noise for deep sleep, studying, and relaxation.\n\n"
            "✨ Perfect for:\n"
            "🛏️ Deep Sleep & Insomnia Relief\n"
            "📚 Studying & Focus\n"
            "🧘 Meditation\n"
            "🏠 Cozy Rainy Day Vibes\n\n"
            "⏱️ Duration: {hours} Hours\n"
            "🎧 Audio: Natural rain sounds\n\n"
            "#rain #rainsounds #sleep #deepsleep #relaxation #study "
            "#{hours}hours #whitenoise #ambient #ASMR"
        ),
        "tags": [
            "rain sounds", "rain for sleeping", "heavy rain",
            "rain ambience", "sleep sounds", "white noise",
            "deep sleep rain", "relaxing rain", "rain ASMR",
            "rain no music", "insomnia relief", "study rain",
        ],
    },
    "ocean": {
        "search_queries": [
            "ocean waves", "sea waves beach", "calm ocean",
            "ocean horizon", "waves crashing",
        ],
        "title": "🌊 {hours} Hours Ocean Waves | Relaxing Sea Sounds for Deep Sleep & Meditation",
        "description": (
            "🌊 {hours} Hours of Calming Ocean Waves\n\n"
            "Let the rhythmic sound of ocean waves wash away your stress. "
            "Perfect for deep sleep, meditation, and total relaxation.\n\n"
            "⏱️ Duration: {hours} Hours\n"
            "🎧 Audio: Natural ocean wave sounds\n\n"
            "#ocean #waves #sleep #meditation #relaxation "
            "#{hours}hours #seasounds #ambient #ASMR"
        ),
        "tags": [
            "ocean waves", "sea sounds", "waves for sleep",
            "ocean ambience", "beach sounds", "deep sleep",
            "meditation", "relaxation", "ocean ASMR",
            "white noise ocean", "calm waves",
        ],
    },
    "thunderstorm": {
        "search_queries": [
            "thunderstorm", "lightning storm", "thunder rain",
            "storm night", "thunder clouds",
        ],
        "title": "⛈️ {hours} Hours Thunderstorm Sounds | Heavy Rain & Thunder for Deep Sleep",
        "description": (
            "⛈️ {hours} Hours of Powerful Thunderstorm\n\n"
            "Experience the raw power of nature with heavy rain and rolling thunder. "
            "The ultimate white noise for the deepest sleep.\n\n"
            "⏱️ Duration: {hours} Hours\n\n"
            "#thunderstorm #rain #thunder #sleep #deepsleep "
            "#{hours}hours #stormsounds #ambient #whitenoise"
        ),
        "tags": [
            "thunderstorm", "thunder sounds", "heavy rain",
            "storm for sleep", "lightning", "thunder rain",
            "deep sleep", "white noise", "storm ambience",
        ],
    },
    "waterfall": {
        "search_queries": [
            "waterfall nature", "waterfall close up", "cascade water",
            "jungle waterfall", "mountain waterfall",
        ],
        "title": "💧 {hours} Hours Waterfall Sounds | Nature White Noise for Sleep & Focus",
        "description": (
            "💧 {hours} Hours of Soothing Waterfall Sounds\n\n"
            "Natural white noise from a beautiful waterfall. "
            "Perfect for blocking distractions and deep relaxation.\n\n"
            "⏱️ Duration: {hours} Hours\n\n"
            "#waterfall #nature #whitenoise #sleep #focus "
            "#{hours}hours #ambient #relaxation"
        ),
        "tags": [
            "waterfall sounds", "waterfall ambience", "nature",
            "white noise", "sleep", "focus", "relaxation",
            "waterfall ASMR", "cascade sounds",
        ],
    },
    "snow": {
        "search_queries": [
            "snowfall", "winter snow", "snowy landscape",
            "blizzard snow", "snow forest",
        ],
        "title": "❄️ {hours} Hours Snowfall & Winter Ambience | Cozy Blizzard Sounds for Sleep",
        "description": (
            "❄️ {hours} Hours of Peaceful Snowfall\n\n"
            "Watch the snow gently falling while you relax, sleep, or study. "
            "The ultimate cozy winter ambience.\n\n"
            "⏱️ Duration: {hours} Hours\n\n"
            "#snow #winter #snowfall #blizzard #cozy #sleep "
            "#{hours}hours #ambient #relaxation"
        ),
        "tags": [
            "snowfall", "winter ambience", "snow sounds",
            "blizzard", "cozy winter", "sleep", "relaxation",
            "snow ASMR", "winter storm",
        ],
    },
    "campfire": {
        "search_queries": [
            "campfire night", "campfire burning", "bonfire",
            "outdoor fire camping", "campfire close up",
        ],
        "title": "🏕️ {hours} Hours Campfire at Night | Crackling Fire & Cricket Sounds for Sleep",
        "description": (
            "🏕️ {hours} Hours of Campfire Under the Stars\n\n"
            "Relax by a peaceful campfire with crackling wood and night sounds. "
            "Perfect for unwinding after a long day.\n\n"
            "⏱️ Duration: {hours} Hours\n\n"
            "#campfire #fire #night #crackling #sleep "
            "#{hours}hours #ambient #nature #relaxation"
        ),
        "tags": [
            "campfire", "campfire sounds", "crackling fire",
            "bonfire", "night sounds", "sleep", "camping",
            "fire ambience", "outdoor fire",
        ],
    },
    "candle": {
        "search_queries": [
            "candle flame", "candle burning", "candlelight",
            "candle close up", "candle flickering",
        ],
        "title": "🕯️ {hours} Hours Candle Flickering | Peaceful Ambience for Sleep & Meditation",
        "description": (
            "🕯️ {hours} Hours of Gentle Candle Flickering\n\n"
            "Watch the mesmerizing dance of a candle flame. "
            "Calming and peaceful — perfect for meditation and sleep.\n\n"
            "⏱️ Duration: {hours} Hours\n\n"
            "#candle #candlelight #meditation #sleep #peaceful "
            "#{hours}hours #ambient #relaxation"
        ),
        "tags": [
            "candle", "candle flickering", "candlelight",
            "meditation", "sleep", "peaceful", "relaxation",
            "candle ASMR", "ambient candle",
        ],
    },
    "underwater": {
        "search_queries": [
            "underwater ocean", "coral reef", "deep sea",
            "fish underwater", "underwater bubbles",
        ],
        "title": "🐠 {hours} Hours Underwater World | Deep Ocean Ambience for Sleep & Relaxation",
        "description": (
            "🐠 {hours} Hours of Mesmerizing Underwater World\n\n"
            "Explore the calming depths of the ocean with beautiful coral reefs "
            "and marine life. Deep relaxation guaranteed.\n\n"
            "⏱️ Duration: {hours} Hours\n\n"
            "#underwater #ocean #deepsea #coralreef #sleep "
            "#{hours}hours #ambient #relaxation #marine"
        ),
        "tags": [
            "underwater", "deep sea", "coral reef",
            "ocean ambience", "marine life", "sleep",
            "relaxation", "underwater ASMR", "ocean sounds",
        ],
    },
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def probe_video(path: str) -> Optional[Dict]:
    """Get video file info."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        for s in data.get("streams", []):
            if s["codec_type"] == "video":
                return {
                    "width": int(s.get("width", 0)),
                    "height": int(s.get("height", 0)),
                    "codec": s.get("codec_name", ""),
                    "duration": float(s.get("duration", 0)),
                    "fps": s.get("r_frame_rate", ""),
                    "has_audio": any(st["codec_type"] == "audio" for st in data["streams"]),
                }
    except Exception as e:
        log(f"Probe failed: {e}")
    return None


def find_and_download(ambient_type: str, freepik: FreepikService) -> Optional[str]:
    """Search Freepik and download the best clip for this ambient type."""
    config = AMBIENT_TYPES[ambient_type]
    queries = config["search_queries"]

    for query in queries:
        log(f"🔍 Searching Freepik: '{query}'")
        videos = freepik.search_videos(query, limit=10, aspect_ratio="16:9")

        if not videos:
            log(f"   No results, trying next query...")
            continue

        # Sort by duration (prefer longer clips = fewer loop seams)
        videos.sort(key=lambda v: v["duration_seconds"], reverse=True)

        for video in videos:
            dur = video["duration_seconds"]
            if dur < 5:
                continue

            log(f"   ✅ Found: id={video['id']} | {video['quality']} | {dur}s | {video['name'][:50]}")

            path = freepik.download_video(video["id"])
            if path:
                # Scale down 4K → 1080p for reasonable file sizes
                path = _ensure_1080p(path)
                return path

        time.sleep(1)  # Rate limit between queries

    return None


def _ensure_1080p(video_path: str) -> str:
    """
    If video is larger than 1080p, re-encode to 1080p H.264.
    This is a one-time cost that makes looping output much smaller:
    - 4K 30s clip = ~180 MB → 1080p = ~15 MB
    - 8h loop: 4K = 130 GB vs 1080p = 8 GB
    """
    probe = probe_video(video_path)
    if not probe:
        return video_path

    if probe["height"] <= 1080:
        log(f"   📐 Already ≤1080p, no scaling needed")
        return video_path

    # Scale to 1080p
    scaled_path = video_path.rsplit(".", 1)[0] + "_1080p.mp4"
    if os.path.exists(scaled_path) and os.path.getsize(scaled_path) > 1000:
        log(f"   📐 1080p version already cached")
        return scaled_path

    log(f"   📐 Scaling {probe['width']}x{probe['height']} → 1920x1080...")
    cmd = [
        "ffmpeg", "-y", "-v", "warning",
        "-i", video_path,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        scaled_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"   ⚠️ Scaling failed: {result.stderr[:200]}")
            return video_path

        orig_mb = os.path.getsize(video_path) / (1024 * 1024)
        scaled_mb = os.path.getsize(scaled_path) / (1024 * 1024)
        log(f"   ✅ Scaled: {orig_mb:.1f} MB → {scaled_mb:.1f} MB ({100*scaled_mb/orig_mb:.0f}%)")

        return scaled_path

    except Exception as e:
        log(f"   ⚠️ Scaling error: {e}")
        return video_path


def loop_to_duration(input_video: str, hours: float, ambient_type: str) -> Optional[Dict]:
    """Loop a short clip to target hours using stream copy (blazing fast)."""
    probe = probe_video(input_video)
    if not probe:
        log("❌ Cannot probe video")
        return None

    duration_seconds = int(hours * 3600)
    loops_needed = int(duration_seconds / max(probe["duration"], 1)) + 1

    log(f"📹 Source: {probe['width']}x{probe['height']} {probe['codec']} ({probe['duration']:.1f}s)")
    log(f"🎯 Target: {hours}h = {duration_seconds}s")
    log(f"🔄 Loops needed: ~{loops_needed}")

    # Output path
    timestamp = int(time.time())
    hours_str = f"{hours:.0f}" if hours == int(hours) else f"{hours:.1f}"
    production_id = f"ambient_{ambient_type}_{hours_str}h_{timestamp}"
    project_root = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(project_root, "assets", "productions", production_id, "en")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{production_id}.mp4")

    # FFmpeg command — stream copy = no re-encoding
    cmd = [
        "ffmpeg", "-y", "-v", "warning", "-stats",
        "-stream_loop", "-1",           # loop video infinitely
        "-i", input_video,
        "-map", "0:v:0",               # video
        "-t", str(duration_seconds),    # limit duration
        "-c:v", "copy",                # NO re-encoding
    ]

    # Audio: use source audio if available, otherwise add silent
    if probe.get("has_audio"):
        cmd.extend(["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"])
    else:
        # Generate white noise as background
        cmd_alt = [
            "ffmpeg", "-y", "-v", "warning", "-stats",
            "-stream_loop", "-1", "-i", input_video,
            "-f", "lavfi", "-i", f"anoisesrc=color=brown:sample_rate=44100:amplitude=0.04",
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(duration_seconds),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        cmd = cmd_alt

    if cmd[-1] != output_path:
        cmd.append(output_path)

    log(f"⚡ Rendering {hours_str}h video (stream copy, no re-encoding)...")

    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            log(f"❌ Render failed: {result.stderr[:500]}")
            return None

        elapsed = time.time() - start_time
        file_size = os.path.getsize(output_path)
        size_gb = file_size / (1024 ** 3)

        log(f"✅ Done in {elapsed:.1f}s!")
        log(f"📦 Output: {size_gb:.2f} GB")
        log(f"📂 File: {output_path}")

    except Exception as e:
        log(f"❌ Render crashed: {e}")
        return None

    # Generate metadata
    config = AMBIENT_TYPES[ambient_type]
    # Fix grammar: "1 Hour" vs "8 Hours"
    hours_label = f"{hours_str} Hour" if hours == 1 else f"{hours_str} Hours"
    title = config["title"].format(hours=hours_str).replace(f"{hours_str} Hours", hours_label)
    description = config["description"].format(hours=hours_str)
    tags = list(config["tags"]) + [f"{hours_str} hours", f"{hours_str} hour ambient"]

    metadata = {
        "title": title,
        "description": description,
        "tags": tags,
        "file_path": output_path,
        "ambient_type": ambient_type,
        "duration_hours": hours,
        "duration_seconds": duration_seconds,
        "resolution": f"{probe['width']}x{probe['height']}",
        "file_size_gb": round(size_gb, 2),
        "render_time_seconds": round(elapsed, 1),
        "source_video": input_video,
    }

    meta_path = os.path.join(out_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata


def upload_to_youtube(metadata: Dict, retry: bool = False) -> Optional[str]:
    """Upload video to YouTube with retry support."""
    max_retries = 12 if retry else 1
    retry_interval = 1800  # 30 min

    for attempt in range(1, max_retries + 1):
        log(f"📤 Upload attempt {attempt}/{max_retries}")

        try:
            yt = YouTubeService()
            if not yt.youtube:
                log("❌ YouTube auth failed")
                if attempt < max_retries:
                    time.sleep(retry_interval)
                continue

            video_id = yt.upload_video(
                file_path=metadata["file_path"],
                title=metadata["title"],
                description=metadata["description"],
                tags=metadata["tags"],
                video_type="long",
            )

            if video_id:
                log(f"✅ UPLOADED: https://youtube.com/watch?v={video_id}")
                return video_id
            else:
                log("⚠️ Upload returned None (quota?)")

        except Exception as e:
            log(f"⚠️ Upload error: {e}")

        if attempt < max_retries:
            next_time = datetime.fromtimestamp(time.time() + retry_interval).strftime("%H:%M")
            log(f"⏰ Retrying at {next_time}...")
            time.sleep(retry_interval)

    return None


def main():
    parser = argparse.ArgumentParser(description="Freepik Ambient Video Producer")
    parser.add_argument("--type", type=str, help="Ambient type (fireplace, forest, rain, etc.)")
    parser.add_argument("--hours", type=float, default=8, help="Duration in hours (default: 8)")
    parser.add_argument("--upload", action="store_true", help="Upload to YouTube after rendering")
    parser.add_argument("--retry", action="store_true", help="Retry upload on quota errors")
    parser.add_argument("--list", action="store_true", help="List available ambient types")
    parser.add_argument("--clip", type=str, help="Use existing local clip instead of downloading")

    args = parser.parse_args()

    if args.list:
        print("\n📋 Available Ambient Types:\n")
        for name, config in AMBIENT_TYPES.items():
            emoji = config["title"].split(" ")[0]
            print(f"  {emoji} {name:20s} — {config['search_queries'][0]}")
        print(f"\n  Total: {len(AMBIENT_TYPES)} types")
        print("\n  Usage: python produce_ambient.py --type fireplace --hours 8 --upload")
        return

    if not args.type:
        parser.print_help()
        return

    if args.type not in AMBIENT_TYPES:
        log(f"❌ Unknown type: '{args.type}'")
        log(f"   Available: {', '.join(AMBIENT_TYPES.keys())}")
        return

    log("=" * 60)
    log(f"🎬 AMBIENT VIDEO PRODUCER")
    log(f"   Type: {args.type}")
    log(f"   Duration: {args.hours}h")
    log(f"   Upload: {'Yes' if args.upload else 'No'}")
    log("=" * 60)

    # Step 1: Get video clip
    if args.clip:
        if not os.path.exists(args.clip):
            log(f"❌ Clip not found: {args.clip}")
            return
        clip_path = args.clip
        log(f"📎 Using local clip: {clip_path}")
    else:
        freepik = FreepikService()
        if not os.getenv("FREEPIK_API_KEY"):
            log("❌ FREEPIK_API_KEY not set!")
            log("   💡 Get your free account at https://developer.freepik.com and add FREEPIK_API_KEY to your .env file.")
            sys.exit(1)

        clip_path = find_and_download(args.type, freepik)
        if not clip_path:
            log(f"❌ No suitable clip found for '{args.type}'")
            return

    # Step 2: Loop to target duration
    metadata = loop_to_duration(clip_path, args.hours, args.type)
    if not metadata:
        log("❌ Rendering failed")
        return

    log(f"\n{'='*60}")
    log(f"✅ VIDEO READY!")
    log(f"   Title: {metadata['title']}")
    log(f"   File:  {metadata['file_path']}")
    log(f"   Size:  {metadata['file_size_gb']:.2f} GB")
    log(f"   Render: {metadata['render_time_seconds']:.0f}s")
    log(f"{'='*60}")

    # Step 3: Upload
    if args.upload:
        video_id = upload_to_youtube(metadata, retry=args.retry)
        if video_id:
            metadata["youtube_id"] = video_id
            metadata["youtube_url"] = f"https://youtube.com/watch?v={video_id}"
            # Update metadata file
            meta_path = os.path.join(os.path.dirname(metadata["file_path"]), "metadata.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
