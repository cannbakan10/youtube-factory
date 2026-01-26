import os
import google.generativeai as genai
from dotenv import load_dotenv
from src.services.tts_service import TTSService

def test_gemini_elevenlabs_pipeline():
    # 1. Ortam değişkenlerini yükle
    load_dotenv()
    
    # 2. Gemini Kurulumu
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("❌ HATA: GEMINI_API_KEY bulunamadı!")
        return

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-2.0-flash-lite')

    # 3. Gemini ile Metin Üretme
    topic = "Yapay zekanın insanlık üzerindeki etkisi"
    prompt = f"Görevin, '{topic}' hakkında 20 kelimeyi geçmeyen, çok vurucu ve profesyonel bir YouTube Shorts giriş cümlesi yazmak. Sadece metni döndür."
    
    print(f"🤖 Gemini metin üretiyor... (Konu: {topic})")
    try:
        response = model.generate_content(prompt)
        generated_text = response.text.strip()
        print(f"✅ Gemini Yanıtı: {generated_text}")
    except Exception as e:
        print(f"❌ Gemini Hatası: {e}")
        return

    # 4. ElevenLabs (TTSService) ile Seslendirme
    print(f"🎙️ ElevenLabs seslendirmeye başlıyor...")
    tts = TTSService()
    
    try:
        audio_path, subs_path, duration = tts.generate_audio_with_subtitles(generated_text)
        
        if audio_path and os.path.exists(audio_path):
            size = os.path.getsize(audio_path)
            print(f"🚀 BAŞARILI!")
            print(f"📍 Ses dosyası: {audio_path}")
            print(f"📊 Boyut: {size} byte")
            print(f"⏱️ Süre: {duration} saniye")
            print(f"\nLütfen bu dosyayı dinleyin: {os.path.abspath(audio_path)}")
        else:
            print("❌ HATA: Ses dosyası oluşturulamadı.")
    except Exception as e:
        print(f"❌ ElevenLabs Hatası: {e}")

if __name__ == "__main__":
    test_gemini_elevenlabs_pipeline()
