"""
AI Ambient Video Producer

Pipeline:
  1. Generate photorealistic AI image via DALL-E 3
  2. Download fire video from Pexels for overlay
  3. Apply Ken Burns effect (slow zoom/pan) to bring image to life
  4. Overlay fire glow for realistic flickering
  5. Add audio (cat purring + fire crackling or brown noise)
  6. Loop base clip to target duration (8h default)
  7. Upload to YouTube
"""

import os
import json
import time
import requests
import subprocess
from typing import Optional, Dict, List
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Presets — each has a DALL-E prompt + audio style
AI_AMBIENT_PRESETS = {
    "cat_fireplace": {
        "title": "Cozy Cat Sleeping by the Fireplace — {hours} Hours Purring & Crackling Fire",
        "description": (
            "Watch a cozy cat sleep peacefully by a warm fireplace. "
            "Perfect for relaxation, sleep, and stress relief. "
            "{hours} hours of purring and crackling fire sounds.\n\n"
            "#catsleep #fireplace #cozyvibe #asmr #relaxing"
        ),
        "tags": ["cat fireplace", "sleeping cat", "cozy cat", "purring cat",
                 "fireplace ambience", "cat asmr", "relaxing cat", "cat purring sleep",
                 "cozy night", "fireplace sounds"],
        "dalle_prompts": [
            "A photorealistic orange tabby cat sleeping peacefully curled up on a thick knitted blanket in front of a warm crackling stone fireplace. Cozy living room, dim warm lighting, candles on the mantle, firewood stacked nearby. Cinematic, 8K, ultra detailed.",
            "A cute ginger cat fast asleep on a fluffy rug in front of a roaring fireplace. Warm amber light flickering on its fur. Cozy cabin interior, wooden beams, hot cocoa on side table. Photorealistic, cinematic lighting.",
            "Sleeping orange cat nestled in a cozy blanket next to a crackling brick fireplace. Warm golden hour light, bokeh background, ultra realistic fur detail. Peaceful winter evening atmosphere.",
        ],
        "fire_keywords": ["fireplace burning", "crackling fire close up", "fire flames"],
        "audio_queries": ["cat purring fireplace", "cat purring crackling fire", "fireplace crackling cozy"],
        "fallback_noise": "brown",
        "kenburns_zoom": 1.03,   # subtle zoom in
    },
    "cozy_fireplace": {
        "title": "Cozy Fireplace — {hours} Hours Crackling Fire for Sleep & Relaxation",
        "description": (
            "Relax with a warm crackling fireplace. Perfect for sleep, study and deep relaxation.\n\n"
            "#fireplace #cozy #sleep #relaxing #fireplaceambience"
        ),
        "tags": ["fireplace", "crackling fire", "cozy ambience", "sleep sounds",
                 "fireplace sounds", "relaxing fire", "study music", "fire asmr"],
        "dalle_prompts": [
            "A beautiful stone fireplace with a warm crackling fire in a cozy living room. Comfortable armchair nearby, bookshelves, warm amber lighting. Ultra realistic, cinematic, 8K.",
            "Roaring fireplace in a rustic log cabin. Snow visible through window, warm blanket on chair, hot tea on table. Photorealistic, golden light, cozy winter atmosphere.",
        ],
        "fire_keywords": ["fireplace burning logs", "crackling fireplace", "fire burning cozy"],
        "audio_queries": ["fireplace crackling", "fire crackling ambience", "cozy fireplace sounds"],
        "fallback_noise": "brown",
        "kenburns_zoom": 1.02,
    },
    "rainy_window": {
        "title": "Rainy Window — {hours} Hours Rain Sounds for Sleep & Focus",
        "description": (
            "Watch rain fall on a cozy window. Perfect for sleep, focus and relaxation.\n\n"
            "#rainsounds #sleep #focus #rainwindow #cozy"
        ),
        "tags": ["rain sounds", "rainy window", "sleep rain", "rain ambience",
                 "focus music", "rain asmr", "cozy rain", "study rain"],
        "dalle_prompts": [
            "Raindrops falling on a window pane, cozy room inside with warm lamp light, blurred city lights outside, rain streaks on glass. Ultra realistic, cinematic, moody atmosphere.",
            "A window with heavy rain outside, cozy bedroom interior, warm bedside lamp, books on nightstand. Photorealistic, soft bokeh, peaceful rainy night.",
        ],
        "fire_keywords": [],
        "audio_queries": ["rain on window", "rain ambience sleep", "heavy rain sounds"],
        "fallback_noise": "white",
        "kenburns_zoom": 1.015,
    },
}


class AIAmbientProducer:
    """
    Produces long ambient YouTube videos using AI-generated images
    with Ken Burns animation, fire overlay and ambient audio.
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.cache_dir = os.path.join(self.project_root, "assets", "cache", "ai_ambient")
        self.productions_dir = os.path.join(self.project_root, "assets", "productions")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.productions_dir, exist_ok=True)

        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.pexels_key = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY", "")

    # ─────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────────────────────

    def produce(
        self,
        preset_name: str = "cat_fireplace",
        duration_hours: float = 8.0,
        auto_upload: bool = False,
    ) -> Optional[Dict]:
        preset = AI_AMBIENT_PRESETS.get(preset_name)
        if not preset:
            logger.error(f"Unknown preset: {preset_name}")
            return None

        timestamp = int(time.time())
        production_id = f"ai_{preset_name}_{timestamp}"
        out_dir = os.path.join(self.productions_dir, production_id)
        os.makedirs(out_dir, exist_ok=True)

        hours_str = f"{int(duration_hours)}" if duration_hours == int(duration_hours) else f"{duration_hours:.1f}"
        duration_seconds = int(duration_hours * 3600)

        logger.info(f"🎨 AI Ambient: {preset_name} | {hours_str}h")

        # Step 1: Generate AI image
        image_path = self._generate_image(preset, out_dir, timestamp)
        if not image_path:
            logger.error("Image generation failed")
            return None

        # Step 2: Download fire overlay (optional, best-effort)
        fire_clip = self._get_fire_clip(preset) if preset.get("fire_keywords") else None

        # Step 3: Get audio
        audio_path = self._get_audio(preset, duration_seconds)

        # Step 4: Create animated base clip (30 seconds)
        base_clip = os.path.join(out_dir, "base_clip.mp4")
        if not self._create_base_clip(image_path, fire_clip, base_clip, preset):
            logger.error("Base clip creation failed")
            return None

        # Step 5: Loop base clip to target duration
        output_path = os.path.join(out_dir, f"{production_id}.mp4")
        if not self._loop_to_duration(base_clip, audio_path, output_path, duration_seconds, preset):
            logger.error("Loop render failed")
            return None

        # Build metadata
        title = preset["title"].format(hours=f"{hours_str} Hour{'s' if float(hours_str) > 1 else ''}")
        description = preset["description"].format(hours=f"{hours_str} Hour{'s' if float(hours_str) > 1 else ''}")
        metadata = {
            "title": title,
            "description": description,
            "tags": preset["tags"],
            "file_path": output_path,
            "preset": preset_name,
            "duration_hours": duration_hours,
        }

        metadata_path = os.path.join(out_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ AI Ambient ready: {output_path}")

        if auto_upload:
            self._upload_to_youtube(metadata)

        return metadata

    # ─────────────────────────────────────────────────────────
    # STEP 1: DALL-E IMAGE GENERATION
    # ─────────────────────────────────────────────────────────

    def _generate_image(self, preset: Dict, out_dir: str, timestamp: int) -> Optional[str]:
        if not self.openai_key:
            logger.error("OPENAI_API_KEY not set")
            return None

        import random
        prompts = preset.get("dalle_prompts", [])
        if not prompts:
            return None

        prompt = random.choice(prompts)
        image_path = os.path.join(out_dir, f"ai_image_{timestamp}.png")

        logger.info(f"🎨 Generating image with DALL-E 3...")
        logger.info(f"   Prompt: {prompt[:80]}...")

        try:
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1792x1024",
                "quality": "hd",
                "response_format": "url",
            }
            resp = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            image_url = data["data"][0]["url"]

            # Download image
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            with open(image_path, "wb") as f:
                f.write(img_resp.content)

            logger.info(f"✅ Image generated: {image_path}")
            return image_path

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────
    # STEP 2: FIRE OVERLAY CLIP
    # ─────────────────────────────────────────────────────────

    def _get_fire_clip(self, preset: Dict) -> Optional[str]:
        if not self.pexels_key:
            return None

        keywords = preset.get("fire_keywords", [])
        for keyword in keywords:
            try:
                headers = {"Authorization": self.pexels_key}
                params = {"query": keyword, "per_page": 5, "orientation": "landscape"}
                resp = requests.get(
                    "https://api.pexels.com/videos/search",
                    headers=headers, params=params, timeout=15
                )
                resp.raise_for_status()
                videos = resp.json().get("videos", [])
                for video in videos:
                    for vf in video.get("video_files", []):
                        if vf.get("quality") in ("hd", "sd") and vf.get("width", 0) >= 640:
                            url = vf["link"]
                            cache_path = os.path.join(self.cache_dir, f"fire_{abs(hash(url))}.mp4")
                            if not os.path.exists(cache_path):
                                r = requests.get(url, timeout=60, stream=True)
                                with open(cache_path, "wb") as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        f.write(chunk)
                            logger.info(f"🔥 Fire clip: {cache_path}")
                            return cache_path
            except Exception as e:
                logger.warning(f"Fire clip fetch failed for '{keyword}': {e}")
        return None

    # ─────────────────────────────────────────────────────────
    # STEP 3: AUDIO
    # ─────────────────────────────────────────────────────────

    def _get_audio(self, preset: Dict, duration_seconds: int) -> Optional[str]:
        if self.pixabay_key:
            for query in preset.get("audio_queries", []):
                try:
                    params = {
                        "key": self.pixabay_key,
                        "q": query,
                        "category": "music",
                        "per_page": 5,
                    }
                    resp = requests.get(
                        "https://pixabay.com/api/sounds/",
                        params=params, timeout=15
                    )
                    data = resp.json()
                    hits = data.get("hits", [])
                    if hits:
                        url = hits[0].get("audio", {}).get("mp3", "") or hits[0].get("previewURL", "")
                        if url:
                            cache_path = os.path.join(self.cache_dir, f"audio_{abs(hash(url))}.mp3")
                            if not os.path.exists(cache_path):
                                r = requests.get(url, timeout=30)
                                with open(cache_path, "wb") as f:
                                    f.write(r.content)
                            logger.info(f"🔊 Audio: {cache_path}")
                            return cache_path
                except Exception as e:
                    logger.warning(f"Audio fetch failed for '{query}': {e}")

        logger.info("Using synthesized noise audio")
        return None  # Will use brown noise in FFmpeg

    # ─────────────────────────────────────────────────────────
    # STEP 4: CREATE ANIMATED BASE CLIP (30 seconds)
    # ─────────────────────────────────────────────────────────

    def _create_base_clip(
        self,
        image_path: str,
        fire_clip: Optional[str],
        output_path: str,
        preset: Dict,
    ) -> bool:
        clip_duration = 30  # seconds for base loop clip
        zoom = preset.get("kenburns_zoom", 1.03)
        zoom_per_frame = (zoom - 1.0) / (clip_duration * 24)  # 24fps

        logger.info(f"🎬 Creating {clip_duration}s animated base clip...")

        if fire_clip and os.path.exists(fire_clip):
            # Ken Burns on image + fire overlay (screen blend)
            filter_complex = (
                # Scale image to 1920x1080, apply Ken Burns zoom
                f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,"
                f"zoompan=z='min(zoom+{zoom_per_frame:.6f},1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={clip_duration * 24}:s=1920x1080:fps=24[base];"
                # Fire clip: scale, loop, screen blend for flicker effect
                f"[1:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,format=rgba,colorchannelmixer=aa=0.18[fire];"
                f"[base][fire]overlay=0:0:format=auto[vout]"
            )
            cmd = [
                "ffmpeg", "-y", "-v", "warning",
                "-loop", "1", "-i", image_path,
                "-stream_loop", "-1", "-i", fire_clip,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-t", str(clip_duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-r", "24",
                "-an",
                output_path,
            ]
        else:
            # Ken Burns only, no fire overlay
            filter_complex = (
                f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,"
                f"zoompan=z='min(zoom+{zoom_per_frame:.6f},1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={clip_duration * 24}:s=1920x1080:fps=24[vout]"
            )
            cmd = [
                "ffmpeg", "-y", "-v", "warning",
                "-loop", "1", "-i", image_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-t", str(clip_duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-r", "24",
                "-an",
                output_path,
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Base clip failed: {result.stderr[:500]}")
                return False
            logger.info(f"✅ Base clip ready: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Base clip error: {e}")
            return False

    # ─────────────────────────────────────────────────────────
    # STEP 5: LOOP BASE CLIP TO TARGET DURATION
    # ─────────────────────────────────────────────────────────

    def _loop_to_duration(
        self,
        base_clip: str,
        audio_path: Optional[str],
        output_path: str,
        duration_seconds: int,
        preset: Dict,
    ) -> bool:
        logger.info(f"⚡ Looping to {duration_seconds}s ({duration_seconds // 3600}h)...")

        noise_color = preset.get("fallback_noise", "brown")

        if audio_path and os.path.exists(audio_path):
            audio_args = ["-stream_loop", "-1", "-i", audio_path]
            audio_map = ["-map", "1:a:0"]
            audio_encode = ["-c:a", "aac", "-b:a", "128k"]
        else:
            audio_args = ["-f", "lavfi", "-i",
                          f"anoisesrc=color={noise_color}:sample_rate=44100:amplitude=0.12"]
            audio_map = ["-map", "1:a:0"]
            audio_encode = ["-c:a", "aac", "-b:a", "96k"]

        cmd = [
            "ffmpeg", "-y", "-v", "warning", "-stats",
            "-stream_loop", "-1", "-i", base_clip,
            *audio_args,
            "-map", "0:v:0",
            *audio_map,
            "-t", str(duration_seconds),
            "-c:v", "copy",
            *audio_encode,
            output_path,
        ]

        try:
            start = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Loop failed: {result.stderr[:500]}")
                return False
            elapsed = time.time() - start
            size_gb = os.path.getsize(output_path) / (1024 ** 3)
            logger.info(f"✅ Done in {elapsed:.1f}s | Size: {size_gb:.2f} GB")
            return True
        except Exception as e:
            logger.error(f"Loop error: {e}")
            return False

    # ─────────────────────────────────────────────────────────
    # STEP 6: YOUTUBE UPLOAD
    # ─────────────────────────────────────────────────────────

    def _upload_to_youtube(self, metadata: Dict) -> Optional[str]:
        try:
            from src.services.youtube_service import YouTubeService
            yt = YouTubeService()
            video_id = yt.upload_video(
                metadata["file_path"],
                metadata["title"],
                metadata["description"],
                metadata.get("tags", []),
                video_type="long",
            )
            if video_id:
                logger.info(f"✅ YouTube upload: https://youtu.be/{video_id}")
            return video_id
        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return None
