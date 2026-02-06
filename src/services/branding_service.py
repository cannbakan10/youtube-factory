import os
import subprocess
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BrandingService:
    def __init__(self, output_dir="assets/branding"):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = output_dir
        if not os.path.isabs(self.output_dir):
            self.output_dir = os.path.join(self.project_root, self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def _font(self, size):
        for font_name in ["Arial.ttf", "Helvetica.ttc", "DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(font_name, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _draw_wrapped(self, draw, text, box, font, fill):
        x, y, w, h = box
        lines = textwrap.wrap(text, width=max(10, int(w / max(8, font.size * 0.55))))
        line_h = font.size + 8
        max_lines = max(1, h // line_h)
        lines = lines[:max_lines]
        for i, line in enumerate(lines):
            draw.text((x, y + i * line_h), line, font=font, fill=fill)

    def generate_logo(self, channel_name="Stream Global"):
        output = os.path.join(self.output_dir, "logo.png")
        img = Image.new("RGB", (1024, 1024), (10, 12, 18))
        draw = ImageDraw.Draw(img)
        draw.rectangle((80, 80, 944, 944), outline=(255, 180, 70), width=8)
        font = self._font(110)
        subtitle_font = self._font(44)
        draw.text((130, 350), channel_name.upper(), font=font, fill=(255, 220, 150))
        draw.text((130, 500), "YOUTUBE FACTORY", font=subtitle_font, fill=(180, 200, 255))
        img.save(output)
        return output

    def generate_banner(self, channel_name="Stream Global"):
        output = os.path.join(self.output_dir, "banner.png")
        img = Image.new("RGB", (2560, 1440), (8, 12, 20))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 2560, 360), fill=(22, 35, 58))
        draw.rectangle((0, 360, 2560, 1440), fill=(10, 16, 28))
        title_font = self._font(170)
        sub_font = self._font(64)
        draw.text((120, 470), channel_name.upper(), font=title_font, fill=(255, 224, 168))
        draw.text((120, 700), "AI VIDEO PRODUCTION", font=sub_font, fill=(170, 195, 255))
        img.save(output)
        return output

    def generate_cinematic_clip(self, prompt, orientation="landscape"):
        width, height = (1920, 1080) if orientation == "landscape" else (1080, 1920)
        output = os.path.join(self.output_dir, "cinematic_clip.mp4")
        safe_prompt = (prompt or "cinematic background").replace("'", "")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x101A2A:s={width}x{height}:r=30",
            "-vf",
            (
                "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.15:t=fill,"
                "drawtext=text='Stream Global':x=(w-text_w)/2:y=(h/2)-40:fontsize=72:fontcolor=white,"
                f"drawtext=text='{safe_prompt}':x=(w-text_w)/2:y=(h/2)+45:fontsize=36:fontcolor=0xFFDFA5"
            ),
            "-t",
            "6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            output,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output):
                return output
            logger.warning(f"generate_cinematic_clip failed: {result.stderr[:250]}")
            return None
        except Exception as e:
            logger.warning(f"generate_cinematic_clip crashed: {e}")
            return None

    def generate_intro_asset(self):
        preferred = os.path.join(self.output_dir, "fixed_intro2.mp4")
        if os.path.exists(preferred):
            return preferred

        logo_path = os.path.join(self.output_dir, "logo.png")
        if not os.path.exists(logo_path):
            self.generate_logo()

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            logo_path,
            "-t",
            "3",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            preferred,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(preferred):
                return preferred
            logger.warning(f"generate_intro_asset failed: {result.stderr[:250]}")
            return None
        except Exception as e:
            logger.warning(f"generate_intro_asset crashed: {e}")
            return None

    def generate_thumbnail(self, topic, title, video_type="shorts", output_path=None):
        width, height = (1080, 1920) if video_type == "shorts" else (1920, 1080)
        if not output_path:
            output_path = os.path.join(self.output_dir, f"thumbnail_{int(time.time())}.png")

        img = Image.new("RGB", (width, height), (8, 10, 18))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, width, int(height * 0.23)), fill=(25, 36, 60))
        draw.rectangle((0, int(height * 0.23), width, height), fill=(12, 18, 30))

        title_font = self._font(74 if video_type == "shorts" else 82)
        topic_font = self._font(42 if video_type == "shorts" else 50)

        self._draw_wrapped(
            draw=draw,
            text=(title or "").upper(),
            box=(60, int(height * 0.08), width - 120, int(height * 0.45)),
            font=title_font,
            fill=(255, 228, 170),
        )
        self._draw_wrapped(
            draw=draw,
            text=f"Topic: {topic}",
            box=(60, int(height * 0.65), width - 120, int(height * 0.28)),
            font=topic_font,
            fill=(196, 210, 255),
        )

        img.save(output_path)
        return output_path
