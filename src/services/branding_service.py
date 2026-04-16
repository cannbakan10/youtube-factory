import os
import re
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
        # Professional font search Order: User provided -> Mac System -> Linux System -> Fallback
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Avenir.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        
        # Add basic names for OS lookup
        font_names = ["Arial Bold.ttf", "Arial.ttf", "Helvetica.ttc", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]
        
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size=size)
                except:
                    continue
                    
        for font_name in font_names:
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
    # PROFESSIONAL THUMBNAIL GENERATOR v2 (High-CTR System)
    # ──────────────────────────────────────────────────────

    # Topic → Emoji badge mapping (large emoji in corner)
    TOPIC_EMOJI_MAP = {
        "space": "🚀", "universe": "🌌", "planet": "🪐", "star": "⭐", "galaxy": "🌠",
        "ocean": "🌊", "sea": "🌊", "underwater": "🐙", "shark": "🦈",
        "fire": "🔥", "volcano": "🌋", "burn": "🔥",
        "forest": "🌲", "nature": "🌿", "jungle": "🌴", "tree": "🌳",
        "animal": "🦁", "wildlife": "🐾", "wolf": "🐺", "tiger": "🐯",
        "history": "🏛️", "ancient": "⚔️", "war": "⚔️", "egypt": "🔺", "rome": "🏛️",
        "science": "🧪", "chemistry": "⚗️", "physics": "⚛️",
        "tech": "💻", "ai": "🤖", "robot": "🤖", "future": "🚀",
        "mystery": "❓", "creepy": "👻", "scary": "💀", "horror": "😱",
        "money": "💰", "rich": "💎", "business": "📈",
        "food": "🍔", "cooking": "🍳",
        "brain": "🧠", "psychology": "🧠", "mind": "🧠",
        "fact": "⚡", "shocking": "😱", "crazy": "🤯", "amazing": "✨",
        "world": "🌍", "country": "🗺️", "city": "🏙️",
        "dinosaur": "🦖", "extinct": "🦴",
        "sport": "⚽", "game": "🎮",
        "music": "🎵", "art": "🎨",
        "health": "💪", "medicine": "💊",
    }

    # 3 color variant schemes (high-contrast YouTube-proven palettes)
    COLOR_VARIANTS = [
        {
            "name": "YELLOW_RED",
            "main_fill": (255, 255, 255),      # White main text
            "accent_fill": (255, 220, 50),      # Bright yellow keyword
            "stroke": (200, 30, 30),            # Red stroke for pop
            "bar": (255, 60, 60),
        },
        {
            "name": "NEON_CYAN",
            "main_fill": (255, 255, 255),
            "accent_fill": (0, 240, 255),       # Electric cyan
            "stroke": (20, 20, 40),             # Near-black stroke
            "bar": (0, 200, 255),
        },
        {
            "name": "GOLD_BLACK",
            "main_fill": (255, 240, 200),
            "accent_fill": (255, 200, 50),      # Gold accent
            "stroke": (0, 0, 0),                # Pure black stroke
            "bar": (255, 180, 40),
        },
    ]

    def generate_thumbnail(self, topic, title, video_type="shorts", output_path=None, generate_variants=True):
        """
        Generate eye-catching high-CTR thumbnails (v2).

        Improvements over v1:
        - 2.5x bigger text (160-180px for Shorts)
        - Keyword highlighting (1-2 power words in accent color)
        - Thick stroke outline (readable on any background)
        - Big emoji badge in corner (topic-aware)
        - 3 color variants generated, best one auto-selected
        - Bottom power-bar with CTA

        Args:
            generate_variants: If True, creates 3 variants and picks best.
                               If False, uses just the first variant (faster).
        """
        width, height = (1080, 1920) if video_type == "shorts" else (1920, 1080)
        if not output_path:
            output_path = os.path.join(self.output_dir, f"thumbnail_{int(time.time())}.png")

        # ─── Layer 1: Background ───
        bg_image = self._fetch_background_image(topic, width, height)
        if bg_image:
            base_bg = bg_image
        else:
            base_bg = self._create_gradient_background(width, height, topic)

        # ─── Layer 2: Strong dark overlay (text must be readable) ───
        base_bg = self._apply_cinematic_overlay(base_bg, width, height)

        # Detect emoji for this topic
        emoji = self._pick_topic_emoji(topic, title)

        variants = self.COLOR_VARIANTS if generate_variants else self.COLOR_VARIANTS[:1]
        variant_paths = []
        variant_scores = []

        for i, variant in enumerate(variants):
            img = base_bg.copy()
            draw = ImageDraw.Draw(img)
            self._draw_thumbnail_text_v2(
                img, draw, title, topic, width, height, video_type,
                variant, emoji
            )

            variant_out = output_path if i == 0 else output_path.replace(
                ".jpg", f"_v{i+1}_{variant['name']}.jpg"
            ).replace(".png", f"_v{i+1}_{variant['name']}.png")

            img.convert("RGB").save(variant_out, quality=95)
            variant_paths.append(variant_out)
            variant_scores.append(self._score_thumbnail(img))

        # Pick highest-scoring variant as main output
        if len(variants) > 1:
            best_idx = max(range(len(variant_scores)), key=lambda i: variant_scores[i])
            if best_idx != 0:
                # Copy best variant to primary output path
                from shutil import copyfile
                copyfile(variant_paths[best_idx], output_path)
            logger.info(
                f"🎨 Thumbnail v2: {len(variants)} variants | "
                f"best='{variants[best_idx]['name']}' (score={variant_scores[best_idx]:.1f})"
            )
        else:
            logger.info(f"🎨 Thumbnail generated: {output_path}")

        return output_path

    def _pick_topic_emoji(self, topic, title):
        """Pick the most relevant emoji based on topic/title keywords."""
        text = f"{topic} {title}".lower()
        for keyword, emoji in self.TOPIC_EMOJI_MAP.items():
            if keyword in text:
                return emoji
        return "⚡"  # Default: lightning (attention-grabbing)

    def _extract_power_words(self, title, max_words=2):
        """
        Extract 1-2 most impactful words from title for accent coloring.
        Priority: numbers, all-caps words, power words, longest non-stop word.
        """
        POWER_WORDS = {
            "secret", "hidden", "shocking", "never", "impossible", "craziest",
            "forbidden", "unbelievable", "amazing", "incredible", "truth",
            "reveal", "exposed", "banned", "mystery", "biggest", "smallest",
            "fastest", "deadliest", "oldest", "ancient", "insane", "strange",
            "weird", "rare", "unique", "extreme", "ultimate", "perfect",
            "dark", "scary", "terrifying", "horrifying", "chilling",
            "sır", "gizli", "şok", "asla", "inanılmaz", "gerçek", "yasak",
            "ölümcül", "korkunç", "tüyler", "secreto", "increíble", "terror",
        }
        STOP = {
            "the", "a", "an", "is", "are", "was", "of", "to", "in", "on",
            "and", "or", "but", "for", "with", "this", "that", "these",
            "you", "your", "my", "we", "they", "it", "its", "ile", "bir",
            "bu", "şu", "ve", "en", "da", "de", "un", "una", "el", "los",
        }

        words = re.findall(r"\b[\wÇĞİÖŞÜçğıöşüñÑáéíóú]+\b", title)
        if not words:
            return []

        scored = []
        for w in words:
            w_clean = w.strip()
            if not w_clean:
                continue
            lw = w_clean.lower()
            score = 0
            # Number = high priority
            if re.match(r"^\d+$", w_clean):
                score += 50
            # ALL CAPS = intentional emphasis
            if len(w_clean) > 2 and w_clean.isupper():
                score += 30
            # Power words
            if lw in POWER_WORDS:
                score += 40
            # Length bonus (meaningful words)
            if len(w_clean) >= 5:
                score += len(w_clean)
            # Stop word penalty
            if lw in STOP:
                score -= 100
            scored.append((w_clean, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [w for w, s in scored[:max_words] if s > 0]

    def _draw_thumbnail_text_v2(self, img, draw, title, topic, width, height, video_type, variant, emoji):
        """
        Draw HIGH-IMPACT text layout:
        - Massive title text (auto-scaled to fit width)
        - Keyword highlighting (accent color)
        - Thick stroke outline for any-background readability
        - Emoji badge in top corner (Pilmoji if available, else icon glyph)
        - Power bar at bottom
        """
        if video_type == "shorts":
            target_title_size = 180
            emoji_size = 180
            margin = 70
            max_lines = 4
            stroke_width = 12
        else:
            target_title_size = 140
            emoji_size = 140
            margin = 100
            max_lines = 3
            stroke_width = 10

        # Detect power words to highlight
        power_words = self._extract_power_words(title, max_words=2)
        power_words_lower = {w.lower() for w in power_words}

        # Clean title
        clean_title = (title or topic or "").strip().upper()
        clean_title = re.sub(r"#\w+", "", clean_title).strip()

        # Feature detect stroke support
        title_font_probe = self._font(target_title_size)
        try:
            draw.textbbox((0, 0), "A", font=title_font_probe, stroke_width=1)
            has_stroke_support = True
        except TypeError:
            has_stroke_support = False

        # ── AUTO-FIT: find font size + wrap that fits inside safe area ──
        safe_width = width - (margin * 2)
        title_size, lines = self._autofit_title(
            draw, clean_title, target_title_size,
            safe_width, max_lines, stroke_width
        )
        title_font = self._font(title_size)
        line_height = int(title_size * 1.15)
        total_height = len(lines) * line_height

        # Vertical center (slightly above to leave room for power bar)
        start_y = (height - total_height) // 2 - int(height * 0.03)

        # ─── Draw each line ───
        for i, line in enumerate(lines):
            y = start_y + i * line_height

            try:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                line_w = bbox[2] - bbox[0]
            except Exception:
                line_w = len(line) * title_size * 0.55

            x = (width - line_w) // 2

            # Highlight line if it contains a power word
            has_accent = any(pw in line.lower() for pw in power_words_lower)
            fill = variant["accent_fill"] if has_accent else variant["main_fill"]
            stroke_col = variant["stroke"]

            if has_stroke_support:
                draw.text(
                    (x, y), line, font=title_font,
                    fill=fill, stroke_width=stroke_width, stroke_fill=stroke_col,
                )
            else:
                for dx in range(-stroke_width, stroke_width + 1, 2):
                    for dy in range(-stroke_width, stroke_width + 1, 2):
                        if dx * dx + dy * dy <= stroke_width * stroke_width:
                            draw.text((x + dx, y + dy), line, font=title_font, fill=stroke_col)
                draw.text((x, y), line, font=title_font, fill=fill)

        # ─── Emoji badge (top-right corner) ───
        self._draw_emoji_badge(img, draw, emoji, width, margin, emoji_size, variant, has_stroke_support)

        # ─── Power bar at bottom ───
        bar_h = 18
        bar_y = height - margin - 120
        draw.rectangle(
            [(margin, bar_y), (width - margin, bar_y + bar_h)],
            fill=variant["bar"]
        )

        # Channel tag
        small_font = self._font(36 if video_type == "shorts" else 42)
        if has_stroke_support:
            draw.text(
                (margin, bar_y + bar_h + 10), "STREAM GLOBAL",
                font=small_font, fill=(230, 230, 230),
                stroke_width=2, stroke_fill=(0, 0, 0),
            )
        else:
            draw.text(
                (margin, bar_y + bar_h + 10), "STREAM GLOBAL",
                font=small_font, fill=(230, 230, 230),
            )

    def _autofit_title(self, draw, title, max_size, safe_width, max_lines, stroke_width):
        """
        Auto-scale font size and word-wrap so every line fits within safe_width.
        Tries progressively smaller sizes until content fits in max_lines.
        """
        words = title.split()
        if not words:
            return max_size, [""]

        for size in range(max_size, 60, -8):
            font = self._font(size)

            # Greedy wrap: fit as many words per line as possible
            lines = []
            current = []
            for word in words:
                trial = " ".join(current + [word])
                try:
                    bbox = draw.textbbox(
                        (0, 0), trial, font=font,
                        stroke_width=stroke_width if self._has_stroke_support(draw, font) else 0
                    )
                    w = bbox[2] - bbox[0]
                except Exception:
                    w = len(trial) * size * 0.55

                if w <= safe_width or not current:
                    current.append(word)
                else:
                    lines.append(" ".join(current))
                    current = [word]
            if current:
                lines.append(" ".join(current))

            # Check single-word overflow — if one word itself is too wide, shrink
            any_overflow = False
            for line in lines:
                try:
                    bbox = draw.textbbox(
                        (0, 0), line, font=font,
                        stroke_width=stroke_width if self._has_stroke_support(draw, font) else 0
                    )
                    if (bbox[2] - bbox[0]) > safe_width:
                        any_overflow = True
                        break
                except Exception:
                    pass

            if any_overflow:
                continue
            if len(lines) <= max_lines:
                return size, lines

        # Last resort: hard wrap at small size
        return 60, textwrap.wrap(title, width=14)[:max_lines]

    def _has_stroke_support(self, draw, font):
        try:
            draw.textbbox((0, 0), "A", font=font, stroke_width=1)
            return True
        except TypeError:
            return False

    def _draw_emoji_badge(self, img, draw, emoji, width, margin, size, variant, has_stroke_support):
        """
        Render emoji on a circular badge. Falls back gracefully if the system font
        doesn't support emoji glyphs (common on Linux without noto-color-emoji).
        """
        badge_pad = 30
        badge_size = size + badge_pad * 2
        badge_x = width - margin - badge_size
        badge_y = margin

        # Background circle
        draw.ellipse(
            [(badge_x, badge_y), (badge_x + badge_size, badge_y + badge_size)],
            fill=variant["bar"], outline=variant["stroke"], width=8,
        )

        # Try Pilmoji first (renders emoji via Twemoji images)
        emoji_drawn = False
        try:
            from pilmoji import Pilmoji
            with Pilmoji(img) as pilmoji:
                emoji_font = self._font(size)
                # Measure emoji bbox so we can center it
                try:
                    bbox = emoji_font.getbbox(emoji)
                    emoji_w = bbox[2] - bbox[0]
                    emoji_h = bbox[3] - bbox[1]
                except Exception:
                    emoji_w, emoji_h = size, size
                em_x = badge_x + (badge_size - emoji_w) // 2
                em_y = badge_y + (badge_size - emoji_h) // 2
                pilmoji.text((em_x, em_y), emoji, font=emoji_font, fill=(255, 255, 255))
            emoji_drawn = True
        except Exception:
            pass

        if not emoji_drawn:
            # Fallback: draw a large "!" or "?" symbol (topic-aware)
            fallback_glyph = self._fallback_glyph_for_emoji(emoji)
            glyph_font = self._font(int(size * 1.1))
            try:
                bbox = draw.textbbox((0, 0), fallback_glyph, font=glyph_font)
                g_w = bbox[2] - bbox[0]
                g_h = bbox[3] - bbox[1]
            except Exception:
                g_w, g_h = size, size
            gx = badge_x + (badge_size - g_w) // 2
            gy = badge_y + (badge_size - g_h) // 2 - int(size * 0.1)
            if has_stroke_support:
                draw.text(
                    (gx, gy), fallback_glyph, font=glyph_font,
                    fill=(255, 255, 255), stroke_width=6, stroke_fill=variant["stroke"],
                )
            else:
                draw.text((gx, gy), fallback_glyph, font=glyph_font, fill=(255, 255, 255))

    def _fallback_glyph_for_emoji(self, emoji):
        """Map common emojis to a high-impact ASCII/unicode glyph when emoji font is missing."""
        fallback_map = {
            "🔥": "!", "⚡": "!", "😱": "!", "🤯": "!", "❓": "?", "💀": "X",
            "🚀": "★", "🌌": "★", "⭐": "★", "🌠": "★", "🪐": "★",
            "🌊": "~", "🌋": "▲", "🏛️": "■", "⚔️": "†", "🔺": "▲",
            "🧠": "?", "💰": "$", "💎": "◆", "🎮": "●", "🎵": "♪", "🎨": "◆",
        }
        return fallback_map.get(emoji, "!")

    def _score_thumbnail(self, img):
        """
        Score a thumbnail for visual impact.
        Uses contrast (standard deviation of brightness) + edge density proxy.
        Higher = more eye-catching.
        """
        try:
            from PIL import ImageStat
            # Downsample to speed up
            small = img.convert("L").resize((160, 284), Image.LANCZOS)
            stat = ImageStat.Stat(small)
            stddev = stat.stddev[0] if stat.stddev else 0
            mean = stat.mean[0] if stat.mean else 128
            # Prefer mid-brightness + high contrast
            brightness_score = 100 - abs(mean - 128) * 0.5
            return stddev + brightness_score * 0.3
        except Exception:
            return 50.0

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

