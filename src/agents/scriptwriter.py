from google import genai
import os
import json
import re
from pydantic import BaseModel
from typing import List, Union

class SceneBlueprint(BaseModel):
    text: str
    keywords: Union[str, List[str]]
    duration: float = 0.0 # TTS servisi bunu güncelleyecek
    language: str = "en"
    video_path: str = ""
    audio_path: str = ""
    sfx_path: str = "" # New: Path to the generated sound effect
    sfx_prompt: str = "" # New: Prompt for ElevenLabs SFX
    subs_path: str = ""

class VideoBlueprint(BaseModel):
    video_id: str
    metadata: dict
    music_prompt: str = "" # New: Prompt for background music
    music_path: str = "" # New: Path to generated music
    scenes: List[SceneBlueprint]

class ScriptWriter:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "").strip())
        self.model = "gemini-2.0-flash-lite"

    def generate_narrative(self, research_data, topic) -> str:
        """
        AŞAMA 1: İLK TASLAK (VIRAL NARRATIVE)
        Burada amaç, sıkıcı ansiklopedik bilgi değil, "Tiktok/Shorts Akışı"na uygun,
        ritmi yüksek ve merak uyandırıcı bir metin oluşturmaktır.
        """
        prompt = f"""
        ROL: Sen dünyanın en iyi YouTube Shorts senaristisin. Görevin "Stream Global" kanalı için milyonlarca izlenecek viral bir metin yazmak.

        KONU: {topic}
        
        ARAŞTIRMA VERİLERİ (BUNLARI KULLAN):
        {research_data}

        YAZIM KURALLARI (KESİN UYULACAK):
        1. TON: "Belgesel sunucusu" ile "Teknoloji gurusu" karışımı. Ciddi ama heyecanlı.
        2. YAPI:
           - 0-3. Sn: (KANCA) İzleyiciyi durduran ters köşe bir cümle.
           - 3-50. Sn: (BİLGİ AKIŞI) Konuyu tam olarak konuda belirtilen SAYI KADAR maddeye böl (Örn: Eğer konuda 10 özellik yazıyorsa 10 özellik anlat). "Birincisi...", "İkincisi..." kalıplarını kullan.
           - 50-60. Sn: (KAPANIŞ) Abone ol çağrısı ile bitir.
        
        3. DİL VE ÜSLUP:
           - Otoriter konuş. Cümleler kısa ve net olsun.
           - Rakamları yazıyla yaz.
           - Toplam kelime sayısı metnin akıcılığını bozmayacak şekilde, her maddeyi 1-2 kısa cümleyle anlatacak şekilde olmalı.
        
        ÇIKTI FORMATI:
        Sadece seslendirilecek metni ver. Başlık, sahne notu vs. yazma.
        """
        
        response = self.client.models.generate_content(model=self.model, contents=prompt)
        text = response.text.strip()
        
        # Temizlik (AI bazen parantez içinde yönetmen notu ekler, onları siliyoruz)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = text.replace("*", "").strip()
        
        # Yasaklı kelime temizliği
        forbidden = ["Merhaba", "Hoşgeldiniz", "Bugünkü videomuzda", "Arkadaşlar"]
        for f in forbidden:
            text = text.replace(f, "")

        return text

    def generate_blueprint(self, narrative, topic, language="tr") -> VideoBlueprint:
        """
        AŞAMA 2: SAHNELEŞTİRME VE GÖRSEL ZEKA
        Metni sahnelere bölerken Pexels için EN İYİ görsel arama terimlerini (İngilizce) üretir.
        """
        prompt = f"""
        GÖREV: Aşağıdaki YouTube Shorts metnini sahnelere böl ve her sahne için stok video arama terimleri (keywords) oluştur.

        SENARYO METNİ:
        {narrative}

        ÖNEMLİ KURALLAR:
        1. SAHNE BÖLÜMLEMESİ: Metni her 1-2 cümlede bir yeni sahneye böl. Sahne süresi kısa olmalı (max 5-6 saniye) ki video akıcı olsun.
        2. KEYWORDS (KRİTİK): 
           - "keywords" alanı Pexels.com'da video aramak için kullanılacak.
           - Senaryo dili ne olursa olsun, **KEYWORDS KESİNLİKLE İNGİLİZCE OLMALI**. Çünkü Pexels İngilizce'de en iyi sonucu verir.
           - Soyut kelimeler kullanma (Örn: "Başarı" yerine "Man standing on mountain top", "Mutluluk" yerine "Smiling friends at beach").
           - Görsel, metindeki konuyu tam yansıtmalı.
        
        3. METADATA (DİL KRİTİK):
           - Başlık (title): Clickbait (Tık tuzağı) ama dürüst, emoji içeren, kısa başlık. **KESİNLİKLE {language.upper()} DİLİNDE OLMALI**.
           - Açıklama (description): Videonun özeti ve #shorts etiketi. **KESİNLİKLE {language.upper()} DİLİNDE OLMALI**.

        JSON FORMATI (Sadece bunu döndür):
        {{
          "video_id": "auto_gen",
          "metadata": {{
            "title": "Başlık Buraya",
            "description": "Açıklama buraya...",
            "tags": ["tag1", "tag2"]
          }},
          "music_prompt": "dark ambient suspenseful cinematic background music",
          "scenes": [
            {{
              "text": "Buraya seslendirilecek Türkçe cümle.",
              "keywords": ["futuristic city", "neon lights", "4k"],
              "sfx_prompt": "cinematic riser with digital glitch",
              "language": "{language}"
            }}
          ]
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model, 
                contents=prompt,
                config={'response_mime_type': 'application/json'} # Gemini JSON Mode
            )
            
            # JSON Temizliği
            json_str = response.text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:-3]
            
            data = json.loads(json_str)
            
            # Güvenlik Kontrolü: Keywords listesi string gelirse listeye çevir
            for scene in data.get("scenes", []):
                if isinstance(scene["keywords"], str):
                    scene["keywords"] = [scene["keywords"]]
            
            return VideoBlueprint(**data)

        except Exception as e:
            print(f"ScriptWriter Hatası: {e}")
            # Hata durumunda boş bir blueprint dönmek yerine basit bir fallback yapılabilir
            # Şimdilik hatayı fırlatalım
            raise e
