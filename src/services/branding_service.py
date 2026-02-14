import os
import subprocess
import textwrap
import time
import random
import requests
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BrandingService:
    def __init__(self, output_dir="assets/branding"):
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.output_dir = output_dir
        if not os.path.isabs(self.output_dir):
            self.output_dir = os.path.join(self.project_root, self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.pexels_key = os.getenv("PEXELS_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

    def _font(self, size):
        for font_name in ["Arial Bold.ttf", "Arial.ttf", "Helvetica.ttc", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(font_name, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _draw_wrapped(self, draw, text, box, font, fill, shadow=False):
        x, y, w, h = box
        lines = textwrap.wrap(text, width=max(10, int(w / max(8, font.size * 0.55))))
        line_h = font.size + 8
        max_lines = max(1, h // line_h)
        lines = lines[:max_lines]
        for i, line in enumerate(lines):
            tx, ty = x, y + i * line_h
            if shadow:
                # Drop shadow for better readability
                draw.text((tx + 3, ty + 3), line, font=font, fill=(0, 0, 0, 180))
            draw.text((tx, ty), line, font=font, fill=fill)

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

    # ──────────────────────────────────────────────────────
    # PROFESSIONAL THUMBNAIL GENERATOR (3-Layer System)
    # ──────────────────────────────────────────────────────

    def generate_thumbnail(self, topic, title, video_type="shorts", output_path=None):
        """
        Generate a professional, eye-catching thumbnail.
        
        3-Layer approach:
        1. Background: Stock photo from Pexels (topic-related)
        2. Overlay: Dark gradient for text readability  
        3. Text: Bold title + emoji accent
        
        Fallback: Solid gradient background with text.
        """
        width, height = (1080, 1920) if video_type == "shorts" else (1920, 1080)
        if not output_path:
            output_path = os.path.join(self.output_dir, f"thumbnail_{int(time.time())}.png")

        # ─── Layer 1: Background ───
        bg_image = self._fetch_background_image(topic, width, height)
        
        if bg_image:
            img = bg_image
        else:
            # Fallback: Premium gradient background
            img = self._create_gradient_background(width, height, topic)

        # ─── Layer 2: Dark overlay for readability ───
        img = self._apply_cinematic_overlay(img, width, height)

        # ─── Layer 3: Bold text + styling ───
        draw = ImageDraw.Draw(img)
        self._draw_thumbnail_text(draw, title, topic, width, height, video_type)

        img.save(output_path, quality=95)
        logger.info(f"🎨 Thumbnail generated: {output_path}")
        return output_path

    def _fetch_background_image(self, topic, width, height):
        """Fetch a relevant background image from Pexels."""
        if not self.pexels_key:
            return None
            
        try:
            headers = {"Authorization": self.pexels_key}
            # Clean topic for better search
            search_term = topic.replace("_", " ").split("-")[0].strip()[:50]
            
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": search_term, "per_page": 5, "orientation": "landscape" if width > height else "portrait"},
                timeout=10,
            )
            
            if resp.status_code != 200:
                return None
                
            data = resp.json()
            photos = data.get("photos", [])
            if not photos:
                return None
            
            # Pick a random photo from top results
            photo = random.choice(photos[:3])
            img_url = photo["src"]["large2x"]  # High quality
            
            img_resp = requests.get(img_url, timeout=15)
            if img_resp.status_code != 200:
                return None
            
            # Save temporarily and open
            tmp_path = os.path.join(self.output_dir, "thumb_bg_temp.jpg")
            with open(tmp_path, "wb") as f:
                f.write(img_resp.content)
            
            img = Image.open(tmp_path).convert("RGB")
            img = img.resize((width, height), Image.LANCZOS)
            
            # Apply slight blur for background effect
            img = img.filter(ImageFilter.GaussianBlur(radius=2))
            
            # Boost contrast slightly
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            
            # Clean up temp file
            try:
                os.remove(tmp_path)
            except:
                pass
                
            return img
            
        except Exception as e:
            logger.warning(f"Background image fetch failed: {e}")
            return None

    def _create_gradient_background(self, width, height, topic):
        """Create a premium gradient background."""
        # Color palettes based on topic keywords
        topic_lower = topic.lower()
        
        palettes = {
            "space": [(10, 5, 40), (30, 10, 80)],
            "ocean": [(5, 20, 50), (10, 50, 80)],
            "fire": [(40, 10, 5), (80, 30, 5)],
            "nature": [(5, 30, 15), (10, 60, 25)],
            "science": [(15, 10, 40), (40, 15, 70)],
            "history": [(30, 15, 5), (60, 30, 10)],
            "tech": [(5, 15, 30), (10, 30, 60)],
        }
        
        colors = None
        for keyword, palette in palettes.items():
            if keyword in topic_lower:
                colors = palette
                break
        
        if not colors:
            # Default: deep blue-purple
            colors = [(10, 8, 30), (25, 15, 55)]
        
        img = Image.new("RGB", (width, height))
        for y in range(height):
            ratio = y / height
            r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ratio)
            g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ratio)
            b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ratio)
            for x in range(width):
                img.putpixel((x, y), (r, g, b))
        
        return img

    def _apply_cinematic_overlay(self, img, width, height):
        """Apply a cinematic dark overlay with vignette for text readability."""
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Top gradient (darker)
        for y in range(height // 3):
            alpha = int(180 * (1 - y / (height // 3)))
            draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
        
        # Bottom gradient (darker)
        for y in range(height * 2 // 3, height):
            alpha = int(200 * ((y - height * 2 // 3) / (height // 3)))
            draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
        
        # Center area: light overlay for text
        center_y = height // 3
        center_h = height // 3
        draw.rectangle(
            [(0, center_y), (width, center_y + center_h)],
            fill=(0, 0, 0, 100)
        )
        
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        return img.convert("RGB")

    def _draw_thumbnail_text(self, draw, title, topic, width, height, video_type):
        """Draw bold, eye-catching text on the thumbnail."""
        if video_type == "shorts":
            title_size = 72
            emoji_size = 90
            margin = 50
        else:
            title_size = 82
            emoji_size = 100
            margin = 80
        
        title_font = self._font(title_size)
        
        # Split title into wrapped lines
        clean_title = (title or topic or "").upper()
        # Remove any existing emoji from title for cleaner rendering
        max_chars = 20 if video_type == "shorts" else 25
        lines = textwrap.wrap(clean_title, width=max_chars)[:3]
        
        # Calculate total text height
        line_height = title_size + 12
        total_height = len(lines) * line_height
        
        # Center vertically
        start_y = (height - total_height) // 2
        
        for i, line in enumerate(lines):
            y = start_y + i * line_height
            
            # Text shadow (multiple layers for glow effect)
            for offset in [4, 3, 2]:
                draw.text(
                    (margin + offset, y + offset),
                    line, font=title_font,
                    fill=(0, 0, 0)
                )
            
            # Main text (bright yellow-white)
            draw.text(
                (margin, y),
                line, font=title_font,
                fill=(255, 245, 200)
            )
        
        # Bottom accent bar
        bar_y = height - 80 if video_type != "shorts" else height - 120
        draw.rectangle(
            [(margin, bar_y), (width - margin, bar_y + 6)],
            fill=(255, 200, 50)
        )
        
        # Channel name at bottom
        small_font = self._font(28)
        draw.text(
            (margin, bar_y + 15),
            "STREAM GLOBAL",
            font=small_font,
            fill=(200, 200, 200)
        )
