import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    print("Testing Nano Banana (gemini-2.5-flash-image)...")
    response = client.models.generate_images(
        model='gemini-2.5-flash-image',
        prompt='A high-contrast cinematic YouTube thumbnail for a mystery video about islands.',
        config={
            'number_of_images': 1,
            'aspect_ratio': '9:16'
        }
    )
    
    if response.generated_images:
        with open("test_nano_banana.png", "wb") as f:
            f.write(response.generated_images[0].image.image_bytes)
        print("✅ Success! Nano Banana Image generated.")
    else:
        print("❌ No images returned.")
except Exception as e:
    print(f"❌ Nano Banana Failed: {e}")
