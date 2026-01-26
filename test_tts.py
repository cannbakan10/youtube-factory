import os
from dotenv import load_dotenv
from src.services.tts_service import TTSService

def test_openai():
    # Load environment variables
    load_dotenv()
    
    # Initialize TTS Service
    tts = TTSService()
    
    test_text = "Merhaba! Bu bir OpenAI test seslendirmesidir. Eğer bu sesi duyuyorsanız, sistemimiz başarıyla çalışıyor demektir."
    
    print(f"🎙️ OpenAI üzerinden ses üretiliyor: '{test_text}'")
    
    audio_path, subs_path, duration = tts.generate_audio_with_subtitles(test_text)
    
    if audio_path and os.path.exists(audio_path):
        size = os.path.getsize(audio_path)
        print(f"✅ SES DOSYASI BAŞARIYLA OLUŞTU!")
        print(f"📍 Dosya Yolu: {audio_path}")
        print(f"📊 Dosya Boyutu: {size} byte")
        print(f"⏱️ Süre: {duration} saniye")
        
        if size < 500:
            print("⚠️ UYARI: Ses dosyası çok küçük, muhtemelen boş veya hata mesajı içeriyor.")
        else:
            print("🚀 Ses dosyası dolu görünüyor. Lütfen bilgisayarınızdan bu dosyayı açıp dinleyin.")
    else:
        print("❌ HATA: Ses dosyası oluşturulamadı!")

if __name__ == "__main__":
    test_openai()
