from src.services.branding_service import BrandingService
from dotenv import load_dotenv
import os

def main():
    load_dotenv()
    branding = BrandingService()
    
    # 1. Logo
    branding.generate_logo("Stream Global")
    
    # 2. Banner
    branding.generate_banner("Stream Global")
    
    # 3. Intro Background
    bg_path = branding.generate_intro_asset()
    
    print("\n🚀 [Branding]: Base assets generated in assets/branding/")
    print("Next step: We will use these to create a fixed intro video.")

if __name__ == "__main__":
    main()
