import os
import json
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

class SceneBlueprint(BaseModel):
    text: str
    keywords: List[str]
    sfx_prompt: str = ""
    sfx_path: str = ""
    audio_path: str = ""
    subs_path: str = ""
    video_path: str = ""
    duration: float = 0.0

class VideoBlueprint(BaseModel):
    video_id: str
    metadata: dict
    music_prompt: str = ""
    music_path: str = ""
    scenes: List[SceneBlueprint]

class ScriptWriter:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash-exp"

    def generate_narrative(self, research_data, topic):
        """
        AŞAMA 1: DRAMATİK VE SÜRÜKLEYİCİ BİR ANLATIM OLUŞTURMA
        """
        prompt = f"""
        Aşağıdaki araştırma verilerini kullanarak, YouTube Shorts için heyecan verici, merak uyandıran ve 
        insanları saniyeler içinde yakalayan bir anlatım metni yaz.
        
        ARAŞTIRMA VERİSİ: {research_data}
        KONU: {topic}
        
        KURALLAR:
        - Metin samimi, enerjik ve 'storytelling' tarzında olmalı.
        - Shorts süresine uygun (yaklaşık 50-60 saniye, 150-180 kelime) olmalı.
        - Dikkat çekici bir giriş (Hook) ile başlamalı.
        - Mutlaka Türkçe olmalı.
        """
        
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return response.text.strip()

    def generate_blueprint(self, narrative, topic, language="tr") -> VideoBlueprint:
        """
        AŞAMA 2: SAHNELEŞTİRME VE GÖRSEL ZEKA
        """
        prompt = f"""
        Verilen anlatım metnini (narrative) kullanarak bir video prodüksiyon planı (blueprint) oluştur.
        
        ANLATIM METNİ: {narrative}
        KONU: {topic}
        DİL: {language}

        Senden beklenenler:
        1. Metni anlamlı sahnelere böl (her sahne 3-5 saniye sürmeli).
        2. Her sahne için Pexels'te aranabilecek İngilizce görsel anahtar kelimeler (keywords) belirle.
        3. Her sahne için ElevenLabs SFX üretimine uygun bir ses efekti açıklaması (sfx_prompt) yaz.
        4. Tüm video için uygun bir arka plan müziği talimatı (music_prompt) yaz.
        5. YouTube için başlık, açıklama ve etiketler üret.

        JSON FORMATI DETAYI:
        {{
          "video_id": "unique_id",
          "metadata": {{
            "title": "Shorts Başlığı",
            "description": "Açıklama ve hashtagler",
            "tags": ["etiket1", "etiket2"]
          }},
          "music_prompt": "cinematic epic suspenseful background music",
          "scenes": [
            {{
              "text": "Sahnede söylenecek metin",
              "keywords": ["scenic", "landscape", "drone shot"],
              "sfx_prompt": "cinematic boom sound",
              "language": "{language}"
            }}
          ]
        }}
        """
        
        response = self.client.models.generate_content(
            model=self.model, 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        data = json.loads(response.text.strip())
        return VideoBlueprint(**data)
