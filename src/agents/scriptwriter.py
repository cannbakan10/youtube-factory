from google import genai
import os
import json
import time
from pydantic import BaseModel, Field
from typing import List, Union

class SceneBlueprint(BaseModel):
    text: str
    keywords: Union[str, List[str]]
    duration: float = 10.0
    language: str = "en"
    video_path: str = ""
    audio_path: str = ""
    subs_path: str = ""

class VideoBlueprint(BaseModel):
    video_id: str
    metadata: dict
    scenes: List[SceneBlueprint]

class ScriptWriter:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.0-flash-lite"

    def generate_narrative(self, research_data, topic) -> str:
        """
        Stage 1: Viral Scripting. Stream Global 3-Bar Brand Logic.
        Ultra-clean text for TTS (No stage directions).
        """
        prompt = f"""
        KONU: {topic}
        VERİLER:
        {research_data}

        GÖREV: "Stream Global" için 3 maddelik, vuruşu yüksek bir Shorts senaryosu yaz.

        YOL HARİTASI (VİRAL KANCA VE YAPI):
        1. KANCA (İLK CÜMLE): Aşağıdaki kalıplardan en uygun olanıyla başla:
           - "Herkes yanlış yapıyor, doğrusu aslında şu..."
           - "Eğer {topic} ile ilgileniyorsanız, bunu görmeniz şart."
           - "Kimse size söylemedi ama gerçek aslında çok farklı..."
        
        2. GÖVDE (3 ÖNEMLİ MADDE): Marka kimliğimiz olan "3 yatay bar"ı temsilen, konuyu tam olarak 3 net maddeye böl. Her maddeyi "Birincisi...", "İkincisi..." diye belirt.

        3. KAPANIŞ: "Stream Global ile keşfetmeye devam et!" cümlesiyle bitir.

        KRİTİK TTS KURALLARI (SESLENDİRME HATALARINI ÖNLEME):
        - SADECE OKUNACAK METNİ YAZ. Parantez içinde notlar [Ses Efekti], *Gülümser* gibi ifadeleri ASLA ekleme.
        - Türkiye örneği (konu değilse) verme. 
        - Rakamları yuvarla ve yazıyla yaz. 
        - Maksimum 90 kelime.

        YALNIZCA anlatıcı metnini döndür.
        """
        response = self.client.models.generate_content(model=self.model, contents=prompt)
        text = response.text.strip()
        
        # Viral purity cleanup (Remove all non-speech artifacts)
        import re
        text = re.sub(r'\[.*?\]', '', text) # Remove [stage directions]
        text = re.sub(r'\(.*?\)', '', text) # Remove (notes)
        
        forbidden_phrases = [
            "2024 verilerine göre", "Tahminlere göre", "Verilere göre",
            "Bunu biliyor muydunuz", "Siz ne düşünüyorsunuz", "Yorumlarda buluşalım"
        ]
        
        lower_topic = topic.lower()
        for phrase in forbidden_phrases:
            text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
            
        if "türkiye" not in lower_topic:
            text = text.replace("Türkiye", "").replace("türkiye", "")

        return text.replace("  ", " ").replace(" ,", ",").replace(" .", ".").strip()

    def generate_blueprint(self, narrative, topic, language="tr") -> VideoBlueprint:
        """
        Stage 2: Blueprint with full SEO optimization (Roadmap compliant).
        """
        prompt = f"""
        ANA METİN:
        {narrative}

        GÖREV: Yukarıdaki metni 4-6 sahneye böl ve SEO uyumlu YouTube Shorts metadatasını hazırla.
        
        SEO VE KURGU KURALLARI (YOL HARİTASI):
        1. BAŞLIK: Maksimum 40-50 karakter. Merak uyandırıcı, içinde sayı geçen vuruşu yüksek başlık. (Örn: "En Kalabalık 5 Dev Ülke!")
        2. AÇIKLAMA: İlk 2 satır videonun en can alıcı özetini içermeli. Mutlaka #shorts ve konuyla ilgili 3 hashtag ekle. Sonuna "Daha fazlası için abone ol!" ekle.
        3. ETİKETLER: Konuyla ilgili 5-6 adet anahtar kelime.
        4. SAHNE DÜZENİ: Metni normal cümle düzeninde tut (Asla all-caps değil).

        JSON FORMATI:
        {{
          "video_id": "shorts_{int(time.time())}",
          "metadata": {{
            "title": "SEO Uyumlu Başlık",
            "description": "Özet ve #shorts #bilgi #etiketler. Daha fazlası için abone ol!",
            "tags": ["shorts", "konu", "bilgi"]
          }},
          "scenes": [
            {{
              "text": "Normal cümle düzeninde metin",
              "keywords": ["visual match terms"],
              "duration": 9.0,
              "language": "{language}"
            }}
          ]
        }}
        
        SADECE ham JSON döndür.
        """
        response = self.client.models.generate_content(model=self.model, contents=prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        # Code-level safeguard: Convert all-caps text to natural casing if Gemini fails
        for scene in data.get('scenes', []):
            if scene['text'].isupper():
                scene['text'] = scene['text'].capitalize()
                
        return VideoBlueprint(**data)
