import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print("Testing Image Generation with Gemini (Nano Banana)...")
    # Using the Imagen 3 model which is part of the "Nano Banana" series
    response = client.models.generate_image(
        model='imagen-3.0-generate-001',
        prompt='A high-contrast cinematic YouTube thumbnail for a mystery video about islands.',
        config={
            'number_of_images': 1,
            'aspect_ratio': '9:16',
            'add_watermark': False
        }
    )
    
    for i, generated_image in enumerate(response.generated_images):
        with open(f"test_gemini_thumb_{i}.png", "wb") as f:
            f.write(generated_image.image.image_bytes)
    print("✅ Success! Gemini Image generated.")
except Exception as e:
    print(f"❌ Gemini Image Generation Failed: {e}")
