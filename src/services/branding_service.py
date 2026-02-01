import json
import sys

# Python 3.9 Compatibility Fix for google-genai
if sys.version_info < (3, 10):
    try:
        import importlib_metadata
        if not hasattr(sys.modules['importlib.metadata'], 'packages_distributions'):
            sys.modules['importlib.metadata'].packages_distributions = importlib_metadata.packages_distributions
    except ImportError:
        pass

# Silence common SSL/NotOpenSSLWarning that confuses users on Mac
import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

from dotenv import load_dotenv

import os
import fal_client
import requests
import uuid
import logging

class BrandingService:
    def __init__(self, output_dir="assets/branding"):
        self.api_key = os.getenv("FAL_KEY", "").strip().replace('"', '').replace("'", "")
        os.environ["FAL_KEY"] = self.api_key
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_logo(self, channel_name="Stream Global"):
        """Generates a premium, minimalist logo using Fal.ai Flux Pro v1.1 Ultra."""
        print(f"🎨 [Branding]: Generating Ultra-Pro Logo for '{channel_name}'...")
        prompt = (
            f"A masterfully designed, minimalist, modern logo for a YouTube channel named '{channel_name}'. "
            "The design should be cinematic, professional, high-tech documentary style. "
            "Clean vector style, centered on a neutral dark background, 4k, sharp details, "
            "ultra-high resolution, professional branding quality."
        )
        
        try:
            # Using Flux Pro v1.1 Ultra as per flawless documentation
            result = fal_client.run(
                "fal-ai/flux-pro/v1.1-ultra",
                arguments={"prompt": prompt, "aspect_ratio": "1:1"}
            )
            image_url = result['images'][0]['url']
            
            path = os.path.join(self.output_dir, "logo.png")
            self._download(image_url, path)
            print(f"✅ [Branding]: Ultra Logo saved to {path}")
            return path
        except Exception as e:
            logging.error(f"❌ Ultra Logo generation failed: {e}")
            return None

    def generate_banner(self, channel_name="Stream Global"):
        """Generates a cinematic YouTube banner (Ultra High Res)."""
        print(f"🎬 [Branding]: Generating Ultra-Pro Banner...")
        prompt = (
            f"A wide cinematic YouTube banner for '{channel_name}'. Strategic, deep-dive documentary theme. "
            "World maps, digital data streams, elegant dark aesthetics, gold and deep blue accents. "
            "High resolution, professional lighting, cinematic depth, 2560x1440 ratio feel."
        )
        
        try:
            result = fal_client.run(
                "fal-ai/flux-pro/v1.1-ultra",
                arguments={"prompt": prompt, "aspect_ratio": "21:9"}
            )
            image_url = result['images'][0]['url']
            
            path = os.path.join(self.output_dir, "banner.png")
            self._download(image_url, path)
            print(f"✅ [Branding]: Ultra Banner saved to {path}")
            return path
        except Exception as e:
            logging.error(f"❌ Ultra Banner generation failed: {e}")
            return None

    def generate_cinematic_clip(self, prompt, orientation="landscape"):
        """
        Generates a high-end cinematic clip using Kling Video v1.5.
        Perfect for Fragman (Trailer) hooks.
        """
        print(f"🎬 [fal.ai Kling]: Generating cinematic clip: {prompt[:50]}...")
        aspect_ratio = "16:9" if orientation == "landscape" else "9:16"
        
        try:
            # Using subscribe with log updates for transparency
            handler = fal_client.submit(
                "fal-ai/kling-video/v1/standard/text-to-video",
                arguments={
                    "prompt": f"Cinematic, high quality documentary style: {prompt}",
                    "aspect_ratio": aspect_ratio
                }
            )
            
            # Print queue updates so user knows it's not "errored"
            print("   ⏳ [Kling]: In queue (Video generation takes 60-90 seconds)...")
            result = handler.get()
            
            video_url = result['video']['url']
            
            filename = f"cinematic_{uuid.uuid4()}.mp4"
            path = os.path.join(self.output_dir, "..", "cache", filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            self._download(video_url, path)
            print(f"✅ [fal.ai Kling]: Cinematic clip saved to {path}")
            return os.path.abspath(path)
        except Exception as e:
            print(f"   ❌ [Branding] Fal.ai Error: {e}")
            logging.error(f"❌ Kling generation failed: {e}")
            return None

    def generate_intro_asset(self):
        """Generates a high-end background for the intro video."""
        print(f"🎥 [Branding]: Generating Intro Background Asset...")
        prompt = (
            "A cinematic, dark, abstract background with moving particles and light leaks. "
            "Documentary style, professional, sleek, minimalist. No text. 4k resolution."
        )
        
        try:
            handler = fal_client.submit(
                "fal-ai/flux-pro/v1.1",
                arguments={"prompt": prompt, "image_size": "landscape_16_9"}
            )
            result = handler.get()
            image_url = result['images'][0]['url']
            
            path = os.path.join(self.output_dir, "intro_bg.png")
            self._download(image_url, path)
            return path
        except Exception as e:
            logging.error(f"❌ Intro asset failed: {e}")
            return None

    def _download(self, url, path):
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
