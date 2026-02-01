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
        """Generates a premium, minimalist logo using Fal.ai Flux Pro."""
        print(f"🎨 [Branding]: Generating Logo for '{channel_name}'...")
        prompt = (
            f"A premium, minimalist, modern logo for a YouTube channel named '{channel_name}'. "
            "The design should be cinematic, professional, high-tech documentary style. "
            "Clean vector style, centered on a neutral dark background, 4k, sharp details."
        )
        
        try:
            handler = fal_client.submit(
                "fal-ai/flux-pro/v1.1",
                arguments={"prompt": prompt, "image_size": "square_hd"}
            )
            result = handler.get()
            image_url = result['images'][0]['url']
            
            path = os.path.join(self.output_dir, "logo.png")
            self._download(image_url, path)
            print(f"✅ [Branding]: Logo saved to {path}")
            return path
        except Exception as e:
            logging.error(f"❌ Logo generation failed: {e}")
            return None

    def generate_banner(self, channel_name="Stream Global"):
        """Generates a cinematic YouTube banner (2560x1440)."""
        print(f"🎬 [Branding]: Generating Banner...")
        prompt = (
            f"A wide cinematic YouTube banner for '{channel_name}'. Strategic, deep-dive documentary theme. "
            "World maps, digital data streams, elegant dark aesthetics, gold and deep blue accents. "
            "High resolution, 8k, professional lighting. 2560x1440 aspect ratio style."
        )
        
        try:
            handler = fal_client.submit(
                "fal-ai/flux-pro/v1.1",
                arguments={"prompt": prompt, "image_size": "landscape_16_9"}
            )
            result = handler.get()
            image_url = result['images'][0]['url']
            
            path = os.path.join(self.output_dir, "banner.png")
            self._download(image_url, path)
            print(f"✅ [Branding]: Banner saved to {path}")
            return path
        except Exception as e:
            logging.error(f"❌ Banner generation failed: {e}")
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
