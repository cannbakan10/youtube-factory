import json
import os
import subprocess
import time
import tempfile
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AmbientVideoService:
    """Create long ambient videos like fireplace and sleep sounds."""

    AMBIENT_PRESETS: Dict[str, Dict[str, object]] = {
        "fireplace": {
            "title": "1 Hour Cozy Fireplace Ambience",
            "description": (
                "Relax with one hour of cozy fireplace visuals and calm ambience. "
                "Perfect for reading, focus, and sleep."
            ),
            "tags": ["fireplace", "cozy ambience", "relaxing", "sleep", "study"],
            "video_keywords": ["steady fireplace burning", "static fireplace long take", "calm fire burning", "fireplace no people"],
            "audio_queries": ["fireplace crackling ambience", "fire crackling slow", "cinematic fire sounds"],
            "fallback_audio": [
                "assets/templates/music/nature_1.mp3",
                "assets/templates/music/documentary_1.mp3",
                "assets/templates/bg_music.mp3",
            ],
            "fallback_video": [
                "assets/templates/fireplace.mp4",
                "assets/templates/fireplace_loop.mp4",
            ],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x2B1208",
        },
        "sleep": {
            "title": "1 Hour Deep Sleep Soundscape",
            "description": (
                "One hour of soft sleep ambience to help you relax and fall asleep faster. "
                "No narration, no interruptions."
            ),
            "tags": ["sleep sounds", "deep sleep", "white noise", "rain", "relax"],
            "video_keywords": ["night sky stars timelapse", "moon clouds", "calm night ocean"],
            "audio_queries": ["sleep rain ambience", "deep sleep white noise", "ocean sleep sound"],
            "fallback_audio": [
                "assets/templates/music/emotional_1.mp3",
                "assets/templates/music/nature_2.mp3",
            ],
            "fallback_video": [],
            "fallback_noise_color": "pink",
            "fallback_bg_color": "0x04080F",
        },
        "rain": {
            "title": "1 Hour Rainy Night Ambience",
            "description": (
                "Steady rain ambience for sleep, deep focus, and relaxation."
            ),
            "tags": ["rain sounds", "sleep rain", "focus ambience", "night rain", "relax"],
            "video_keywords": ["rain window night", "rainy city night", "rain drops glass"],
            "audio_queries": ["rain ambience sleep", "night rain sound", "rain white noise"],
            "fallback_audio": [
                "assets/templates/music/nature_3.mp3",
                "assets/templates/music/nature_4.mp3",
            ],
            "fallback_video": [],
            "fallback_noise_color": "pink",
            "fallback_bg_color": "0x0A1421",
        },
        "ocean_sleep": {
            "title": "1 Hour Ocean Waves for Deep Sleep",
            "description": (
                "Calm ocean waves and relaxing visuals to help you fall asleep."
            ),
            "tags": ["ocean waves", "deep sleep", "night ocean", "relaxing sounds", "sleep ambience"],
            "video_keywords": ["calm ocean night", "moonlight sea", "gentle waves beach"],
            "audio_queries": ["ocean waves sleep", "calm sea ambience", "night beach sound"],
            "fallback_audio": [
                "assets/templates/music/nature_5.mp3",
                "assets/templates/music/emotional_2.mp3",
            ],
            "fallback_video": [],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x061328",
        },
        "brown_noise": {
            "title": "1 Hour Brown Noise for Sleep",
            "description": (
                "Consistent low-frequency brown noise for better sleep and relaxation."
            ),
            "tags": ["brown noise", "sleep sound", "noise therapy", "deep sleep", "focus"],
            "video_keywords": ["dark relaxing gradient", "abstract calm background", "night ambience"],
            "audio_queries": [],
            "fallback_audio": [],
            "fallback_video": [],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x050505",
        },
        "white_noise": {
            "title": "1 Hour White Noise for Better Sleep",
            "description": (
                "Smooth white noise to mask distractions and help with sleep."
            ),
            "tags": ["white noise", "sleep aid", "noise blocker", "calm", "study"],
            "video_keywords": ["minimal ambient background", "calm abstract texture", "night minimal"],
            "audio_queries": [],
            "fallback_audio": [],
            "fallback_video": [],
            "fallback_noise_color": "white",
            "fallback_bg_color": "0x0A0A0A",
        },
        "cozy_library": {
            "title": "1 Hour Cozy Library & Rain Ambience",
            "description": "Imagine studying or relaxing in a quiet, cozy library with soft rain outside.",
            "tags": ["library ambience", "study music", "cozy library", "rain on window", "dark academia"],
            "video_keywords": ["cozy library interior", "old books fireplace", "library rain window"],
            "audio_queries": ["library ambience rain", "soft study background sound", "pages turning fireplace"],
            "fallback_audio": ["assets/templates/music/lofi_1.mp3"],
            "fallback_video": [],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x1A0F0A",
        },
        "space_ambience": {
            "title": "1 Hour Deep Space Travel Ambience",
            "description": "Embark on a journey through the stars with deep space drones and celestial visuals.",
            "tags": ["space ambience", "starship engine", "deep space", "sci-fi sleep", "cosmic"],
            "video_keywords": ["starship window", "deep space nebula", "planet view from space"],
            "audio_queries": ["spaceship engine drone", "deep space frequency", "cosmic white noise"],
            "fallback_audio": ["assets/templates/music/cinematic_1.mp3"],
            "fallback_video": [],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x00020A",
        },
        "cyberpunk_city": {
            "title": "1 Hour Cyberpunk City Rain Ambience",
            "description": "Neon lights, rainy streets, and the hum of a futuristic city.",
            "tags": ["cyberpunk ambience", "lofi city", "rainy neon city", "blade runner vibe", "futuristic sleep"],
            "video_keywords": ["neon city rain night", "cyberpunk street lo-fi", "futuristic city window"],
            "audio_queries": ["cyberpunk city rain ambience", "futuristic street hum", "neon city lo-fi loop"],
            "fallback_audio": ["assets/templates/music/lofi_2.mp3"],
            "fallback_video": [],
            "fallback_noise_color": "pink",
            "fallback_bg_color": "0x0B001F",
        },
        "forest_walk": {
            "title": "1 Hour Peaceful Forest & River Ambience",
            "description": "Relaxing sounds of a deep forest, chirping birds, and a gentle river flow.",
            "tags": ["forest ambience", "nature sounds", "river flow sleep", "birds chirping", "meditation"],
            "video_keywords": ["sunlight forest stream", "gentle river flow forest", "wind in trees 4k"],
            "audio_queries": ["deep forest ambience birds", "gentle river sound", "forest wind sleep"],
            "fallback_audio": ["assets/templates/music/nature_1.mp3"],
            "fallback_video": [],
            "fallback_noise_color": "brown",
            "fallback_bg_color": "0x0E2410",
        },
    }

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.cache_dir = os.path.join(self.project_root, "assets", "cache")
        self.productions_dir = os.path.join(self.project_root, "assets", "productions")

        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.productions_dir, exist_ok=True)

        self.pexels = PexelsService(output_dir=self.cache_dir)
        self.pixabay = PixabayService(output_dir=self.cache_dir)

    def create_video(
        self,
        ambient_type: str = "sleep",
        duration_minutes: int = 60,
        video_type: str = "long",
        language: str = "en",
        source_mode: str = "auto",
    ) -> Optional[Dict[str, object]]:
        preset = self.AMBIENT_PRESETS.get(ambient_type)
        if not preset:
            logger.error(f"Unknown ambient type: {ambient_type}")
            return None

        duration_minutes = max(1, int(duration_minutes))
        duration_seconds = duration_minutes * 60
        timestamp = int(time.time())
        production_id = f"{ambient_type}_{duration_minutes}min_{timestamp}"

        lang = (language or "en").strip().lower()
        out_dir = os.path.join(self.productions_dir, production_id, lang)
        os.makedirs(out_dir, exist_ok=True)

        output_path = os.path.join(out_dir, f"{production_id}_{lang}.mp4")
        metadata_path = os.path.join(out_dir, "metadata.json")

        is_long = video_type == "long"
        width, height = (1280, 720) if is_long else (1080, 1920)
        orientation = "landscape" if is_long else "portrait"

        logger.info(
            f"Creating ambient video type={ambient_type} duration={duration_minutes}m format={video_type}"
        )

        video_source = self._resolve_video_source(
            ambient_type=ambient_type,
            keywords=list(preset["video_keywords"]),  # type: ignore[arg-type]
            fallback_video_paths=list(preset.get("fallback_video", [])),  # type: ignore[arg-type]
            orientation=orientation,
            source_mode=source_mode,
        )
        if source_mode == "api" and not video_source:
            logger.error(
                f"No valid API video found for ambient_type={ambient_type}. "
                "Try different keywords or ensure Pexels/Pixabay keys are valid."
            )
            return None

        if not video_source:
            video_source = self._generate_procedural_loop_clip(
                ambient_type=ambient_type,
                width=width,
                height=height,
                bg_color=str(preset["fallback_bg_color"]),
            )
        audio_source, audio_mode = self._resolve_audio_source(
            preset=preset,
            duration_seconds=duration_seconds,
        )

        render_ok = self._render_ambient(
            output_path=output_path,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            bg_color=str(preset["fallback_bg_color"]),
            video_source=video_source,
            audio_source=audio_source,
            audio_mode=audio_mode,
            ambient_type=ambient_type,
        )
        if not render_ok:
            return None

        title = f"{preset['title']} ({duration_minutes} Minutes)"
        description = (
            f"{preset['description']}\n\n"
            f"Duration: {duration_minutes} minutes\n"
            "Generated by YouTube Factory Ambient Engine"
        )
        tags = list(preset["tags"]) + ["1 hour ambience" if duration_minutes >= 60 else "ambient loop"]  # type: ignore[arg-type]

        metadata = {
            "title": title,
            "description": description,
            "tags": tags,
            "file_path": output_path,
            "ambient_type": ambient_type,
            "duration_minutes": duration_minutes,
            "video_type": video_type,
            "language": lang,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Ambient video ready: {output_path}")
        return metadata

    def _resolve_video_source(
        self,
        ambient_type: str,
        keywords,
        fallback_video_paths,
        orientation: str,
        source_mode: str,
    ) -> Optional[str]:
        if os.getenv("AMBIENT_OFFLINE") == "1":
            logger.info("AMBIENT_OFFLINE=1, skipping remote video lookup.")
        else:
            if keywords:
                try:
                    video = self.pexels.get_video(keywords, orientation=orientation)
                    if video and self._is_valid_ambient_video(video, ambient_type):
                        return video
                    if video:
                        logger.warning(f"Rejected non-matching ambient clip (Pexels): {video}")
                except Exception as e:
                    logger.warning(f"Pexels ambient fetch failed: {e}")

                try:
                    video = self.pixabay.get_video(keywords, orientation=orientation)
                    if video and self._is_valid_ambient_video(video, ambient_type):
                        return video
                    if video:
                        logger.warning(f"Rejected non-matching ambient clip (Pixabay): {video}")
                except Exception as e:
                    logger.warning(f"Pixabay ambient fetch failed: {e}")

        if source_mode == "api":
            return None

        for rel_path in fallback_video_paths or []:
            abs_path = os.path.join(self.project_root, str(rel_path))
            if os.path.exists(abs_path):
                logger.info(f"Using local fallback ambient video: {abs_path}")
                return abs_path

        logger.warning("Ambient video source not found, using color background fallback")
        return None

    def _resolve_audio_source(
        self,
        preset: Dict[str, object],
        duration_seconds: int,
    ) -> Tuple[Optional[str], str]:
        if os.getenv("AMBIENT_OFFLINE") != "1":
            for query in preset.get("audio_queries", []):
                try:
                    audio = self.pixabay.get_audio(str(query), category="ambient")
                    if audio and os.path.exists(audio):
                        logger.info(f"Ambient audio found from Pixabay: {query}")
                        return audio, "file"
                except Exception as e:
                    logger.warning(f"Ambient audio fetch failed for '{query}': {e}")
        else:
            logger.info("AMBIENT_OFFLINE=1, skipping remote audio lookup.")

        for rel_path in preset.get("fallback_audio", []):
            abs_path = os.path.join(self.project_root, str(rel_path))
            if os.path.exists(abs_path):
                logger.info(f"Using local fallback ambient audio: {abs_path}")
                return abs_path, "file"

        noise_color = str(preset.get("fallback_noise_color", "pink"))
        logger.warning(
            f"No ambient audio file found. Falling back to ffmpeg noise source ({noise_color})."
        )
        return noise_color, "noise"

    def _render_ambient(
        self,
        output_path: str,
        duration_seconds: int,
        width: int,
        height: int,
        bg_color: str,
        video_source: Optional[str],
        audio_source: Optional[str],
        audio_mode: str,
        ambient_type: str,
    ) -> bool:
        # Fast path: if both streams are file-based, remux/copy video first for much faster long exports.
        if (
            video_source
            and audio_source
            and audio_mode == "file"
            and os.path.exists(video_source)
            and os.path.exists(audio_source)
        ):
            if self._try_fast_mux_render(output_path, duration_seconds, video_source, audio_source):
                return True

        input_args = []
        video_input_idx = 0
        audio_input_idx = 1

        if video_source and os.path.exists(video_source):
            input_args.extend(["-stream_loop", "-1", "-i", video_source])
        else:
            fallback_lavfi = self._fallback_video_lavfi(
                ambient_type=ambient_type,
                width=width,
                height=height,
                bg_color=bg_color,
            )
            input_args.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    fallback_lavfi,
                ]
            )

        if audio_mode == "file" and audio_source and os.path.exists(audio_source):
            input_args.extend(["-stream_loop", "-1", "-i", audio_source])
        elif audio_mode == "noise" and audio_source:
            input_args.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"anoisesrc=color={audio_source}:sample_rate=44100:amplitude=0.08",
                ]
            )
        else:
            input_args.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                ]
            )

        filter_complex = (
            f"[{video_input_idx}:v]fps=15,"
            f"scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,format=yuv420p[vout];"
            f"[{audio_input_idx}:a]atrim=duration={duration_seconds},"
            "asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.0[aout]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            *input_args,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            str(duration_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Ambient render failed: {result.stderr[:500]}")
                return False
            return True
        except Exception as e:
            logger.error(f"Ambient render crashed: {e}")
            return False

    def _fallback_video_lavfi(self, ambient_type: str, width: int, height: int, bg_color: str) -> str:
        if ambient_type == "fireplace":
            return (
                f"life=s={width}x{height}:rate=15:ratio=0.62:mold=14,"
                "format=gray,"
                "boxblur=2:1,"
                "lutrgb="
                "r='if(gt(val,18),min(255,val*2.2),0)':"
                "g='if(gt(val,18),min(255,val*1.2),0)':"
                "b='if(gt(val,18),min(255,val*0.25),0)',"
                "vignette=angle=0.35"
            )
        if ambient_type in {"sleep", "rain", "ocean_sleep"}:
            return (
                f"color=c={bg_color}:s={width}x{height}:r=15,"
                "noise=alls=10:allf=t+u,eq=brightness=-0.02:contrast=1.05:saturation=0.85"
            )
        return f"color=c={bg_color}:s={width}x{height}:r=15"

    def _is_valid_ambient_video(self, video_path: str, ambient_type: str) -> bool:
        if ambient_type != "fireplace":
            return True
        return self._looks_like_fire(video_path)

    def _looks_like_fire(self, video_path: str) -> bool:
        """Heuristic fire detection to avoid unrelated clips in fireplace mode."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                frame_path = tmp.name

            cmd = [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                "1.5",
                "-i",
                video_path,
                "-frames:v",
                "1",
                frame_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0 or not os.path.exists(frame_path):
                return False

            img = Image.open(frame_path).convert("RGB").resize((320, 180))
            arr = np.array(img).astype(np.float32)
            rch, gch, bch = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            lum = 0.2126 * rch + 0.7152 * gch + 0.0722 * bch

            warm_mask = (rch > 120) & (gch > 45) & (bch < 130) & (rch > gch * 1.05)
            warm_ratio = float(warm_mask.mean())
            dark_ratio = float((lum < 55).mean())
            lum_var = float(lum.var())

            return warm_ratio >= 0.03 and dark_ratio >= 0.12 and lum_var >= 400.0
        except Exception:
            return False
        finally:
            try:
                if "frame_path" in locals() and os.path.exists(frame_path):
                    os.remove(frame_path)
            except Exception:
                pass

    def _generate_procedural_loop_clip(
        self,
        ambient_type: str,
        width: int,
        height: int,
        bg_color: str,
    ) -> Optional[str]:
        """
        Generates a short procedural ambient loop clip locally.
        This enables very fast 1-hour output via stream copy looping.
        """
        output_path = os.path.join(self.cache_dir, f"ambient_loop_{ambient_type}_{width}x{height}_v3.mp4")
        if os.path.exists(output_path):
            return output_path

        lavfi_src = self._fallback_video_lavfi(ambient_type=ambient_type, width=width, height=height, bg_color=bg_color)
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            lavfi_src,
            "-t",
            "20",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "32",
            "-b:v",
            "1200k",
            "-maxrate",
            "1200k",
            "-bufsize",
            "2400k",
            "-g",
            "60",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Generated procedural loop clip: {output_path}")
                return output_path
            logger.warning(f"Procedural loop generation failed: {result.stderr[:200]}")
            return None
        except Exception as e:
            logger.warning(f"Procedural loop generation crashed: {e}")
            return None

    def _try_fast_mux_render(
        self,
        output_path: str,
        duration_seconds: int,
        video_source: str,
        audio_source: str,
    ) -> bool:
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-stream_loop",
            "-1",
            "-i",
            video_source,
            "-stream_loop",
            "-1",
            "-i",
            audio_source,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            str(duration_seconds),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("Ambient fast mux render succeeded.")
                return True
            logger.warning(f"Ambient fast mux failed, falling back to full render: {result.stderr[:200]}")
            return False
        except Exception as e:
            logger.warning(f"Ambient fast mux crashed, falling back to full render: {e}")
            return False
