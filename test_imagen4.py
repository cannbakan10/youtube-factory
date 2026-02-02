import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print("Testing Imagen 4 (imagen-4.0-generate-001)...")
    response = client.models.generate_images(
        model='imagen-4.0-generate-001',
        prompt='A high-contrast cinematic YouTube thumbnail for a mystery video about islands.',
        config={
            'number_of_images': 1,
            'aspect_ratio': '9:16'
        }
    )
    
    if response.generated_images:
        with open("test_imagen4.png", "wb") as f:
            f.write(response.generated_images[0].image.image_bytes)
        print("✅ Success! Imagen 4 Image generated.")
except Exception as e:
    print(f"❌ Imagen 4 Failed: {e}")
