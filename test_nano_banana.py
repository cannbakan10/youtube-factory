import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.services.branding_service import BrandingService

load_dotenv()

def test_thumbnails():
    branding = BrandingService()
    
    test_cases = [
        {"topic": "Dünyanın En Gizemli Adaları", "title": "DİKKAT! Bu Adalara Giden Bir Daha Dönemedi!", "type": "shorts"},
        {"topic": "2050'de Haritadan Silinecek 5 Ülke", "title": "ŞOK EDİCİ! Maldivler Tamamen Yok mu Oluyor?", "type": "shorts"},
        {"topic": "Japonya'nın Bilinmeyen Kuralları", "title": "SAKIN! Japonya'da Bunları Yapmayın!", "type": "long"}
    ]
    
    print("🚀 Starting Nano Banana (Gemini) Thumbnail Production Test...")
    
    for i, case in enumerate(test_cases):
        output_name = f"test_thumb_{i}_{case['type']}.png"
        output_path = os.path.join(os.getcwd(), output_name)
        
        print(f"\n🎬 Test {i+1}: {case['topic']} ({case['type']})")
        path = branding.generate_thumbnail(
            topic=case['topic'],
            title=case['title'],
            video_type=case['type'],
            output_path=output_path
        )
        
        if path:
            print(f"✅ Created: {path}")
        else:
            print(f"❌ Failed Test {i+1}")

if __name__ == "__main__":
    test_thumbnails()
