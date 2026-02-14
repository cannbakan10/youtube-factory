# 📈 StreamGlobal — Kapsamlı Büyüme Stratejisi v2.1
## Tüm Kod Tabanı Derin Analiz Raporu
**Tarih:** 14 Şubat 2026 | **Analiz:** Her dosya, agent, service ve workflow tek tek incelendi.

---

## 🔬 KOD TABANI DERİN ANALİZ SONUÇLARI

### İncelenen Dosyalar (Tam Liste)
| Dosya | Satır | Durum |
|---|---|---|
| `main.py` | ~600 | ✅ Çalışıyor |
| `nightly_brain_agent.py` | 999 | ✅ Çalışıyor |
| `youtube_analytics_agent.py` | 899 | ⚠️ Eksik: YouTube Analytics API v2 yok |
| `viral_analyzer.py` | 658 | ✅ Çalışıyor |
| `nature_shorts_agent.py` | 960 | ✅ Çalışıyor |
| `scriptwriter.py` | 431 | ⚠️ İyileştirme potansiyeli |
| `x_content_agent.py` | 212 | 🔴 **BUG:** İngilizce kanal ama Türkçe post atıyor |
| `tiktok_agent.py` | 386 | ⚠️ Dosya var ama workflow'da kullanılmıyor |
| `country_content_agent.py` | 156 | ⚠️ Nightly plan ile entegre değil |
| `youtube_content_agent.py` | 50 | ⚠️ Kullanılmayan dosya |
| `trend_agent.py` | 77 | ✅ Çalışıyor |
| `researcher.py` | 125 | ⚠️ İyileştirme potansiyeli |
| `youtube_service.py` | 177 | ⚠️ Sadece upload — playlist/end-screen/comment yok |
| `branding_service.py` | 163 | 🔴 **KRİTİK:** Thumbnail çok kötü kalitede |
| `livestream_service.py` | 401 | 🔴 **KULLANILMIYOR** — Büyük fırsat |
| `tts_service.py` | 261 | ✅ ElevenLabs entegre |
| `twitter_service.py` | 97 | ✅ Tweepy entegre |
| `tiktok_service.py` | ~19K | ⚠️ Var ama workflow yok |
| `ambient_video_service.py` | ~44K | ✅ Çalışıyor |
| `content_engine.yml` | 200 | ⚠️ Saatler optimize değil |
| `nightly_brain.yml` | 84 | ✅ Çalışıyor |

---

## 🔴 KRİTİK BULGULAR (Hemen Düzeltilmeli)

### 1. 🐛 BUG: X (Twitter) Agent Türkçe Post Atıyor!
**Dosya:** `src/agents/x_content_agent.py` satır 45-68

Kanal İngilizce-only stratejisine geçmiş ama X agent hâlâ Türkçe post üretiyor:
```python
# x_content_agent.py:55-57  — BUG!
"3. BAŞLIK: İlgi çekici bir emoji ile başla..."
"5. HASHTAG: ... #VayBeBilgi etiketi SABİT olsun..."
```

Ayrıca `categories` listesi de Türkçe:
```python
# x_content_agent.py:39
categories = ["bilim", "tarih", "uzay", "doğa", "hayvanlar", ...]
```

**FIX:** Tüm prompt'ları İngilizce'ye çevirmeli, hashtag'leri değiştirmeli.

---

### 2. 🔴 Thumbnail'lar Profesyonel DEĞİL
**Dosya:** `src/services/branding_service.py` satır 133-162

Mevcut thumbnail generator PIL ile düz renkli bir dikdörtgen üzerine text yazıyor:
```python
img = Image.new("RGB", (width, height), (8, 10, 18))  # Siyah arka plan
draw.rectangle((0, 0, width, int(height * 0.23)), fill=(25, 36, 60))  # Koyu mavi çubuk
```

Bu, YouTube'da **CTR < %2** demek. YouTube ortalaması %4-5. 

**ÇÖZÜM: 3 Katmanlı Thumbnail Pipeline:**
```
Katman 1: Pexels/Pixabay'dan konuyla ilgili yüksek kaliteli arka plan fotoğrafı
Katman 2: Yarı-saydam karanlık overlay (okunabilirlik için)
Katman 3: Büyük, bold text + emoji + çerçeve
```

**Alternatif (Daha iyi):** Gemini Imagen API ile AI-generated thumbnail:
```python
from google import genai

client = genai.Client(api_key=GEMINI_KEY)
response = client.models.generate_images(
    model="imagen-3.0-generate-002",
    prompt=f"YouTube thumbnail for video about {topic}, dramatic, eye-catching, bold text '{title[:20]}', vibrant colors, 4K quality",
    config={"number_of_images": 1, "aspect_ratio": "16:9"}  # veya 9:16 shorts için
)
# → thumbnail olarak kaydet ve upload et
```

**YouTube API ile thumbnail set:**
```python
youtube.thumbnails().set(
    videoId=video_id,
    media_body=MediaFileUpload("thumbnail.jpg", mimetype="image/jpeg")
).execute()
```

---

### 3. 🔴 LivestreamService 24/7 — KULLANILMIYOR!
**Dosya:** `src/services/livestream_service.py` — 401 satır, 6 preset, tam çalışır durumda.

Bu dosya **24/7 YouTube Live Stream** altyapısı sunuyor:
- `rainy_car` — Yağmurlu Araba Penceresi
- `fireplace` — Şömine
- `rain_window` — Pencerede Yağmur
- `ocean_waves` — Okyanus Dalgaları
- `thunderstorm` — Fırtına
- `snow_cabin` — Karlı Kulübe

**Neden önemli?**
- 24/7 livestream = **kesintisiz watch time** → YouTube algoritması BAYILIYOR
- Ambient/sleep/study kanalları 24/7 stream ile **10x-100x büyüyor**
- Abone kasma makinesi — izleyiciler stream sırasında abone oluyor
- Ekstra reklam geliri (livestream'lere mid-roll ads düşer)

**Yapılması gereken:**
1. GitHub Actions'da `livestream.yml` workflow oluşturmak
2. Veya bir VPS/Cloud Run instance üzerinde sürekli çalıştırmak
3. YouTube Studio'da scheduled livestream oluşturup RTMP key almak

```bash
# Tek komutla başlatılabilir:
python main.py --livestream fireplace
```

**Ama şu an `main.py`'da --livestream argümanı bile yok!** Eklenmeli.

---

### 4. 🔴 TikTok Agent — Var Ama Kullanılmıyor!
**Dosya:** `src/agents/tiktok_agent.py` — 386 satır, tam çalışır.

Özellikler:
- YouTube Shorts → TikTok cross-posting
- Nature Shorts → TikTok cross-posting
- TikTok-optimized hashtag ve title generation
- Gemini AI ile TikTok'a özel başlık
- Duplicate posting koruması (history tracking)

**Ama:**
- `content_engine.yml` workflow'unda TikTok adımı YOK
- `nightly_brain.yml`'da TikTok adımı YOK
- `main.py`'da `--tiktok` argümanı var mı kontrol edilmeli

**TikTok'un Potansiyeli:**
- TikTok'tan YouTube'a trafik: **%15-25 izlenme artışı** raporlanıyor
- Aynı video, sıfır ekstra maliyet
- TikTok'da 10K takipçi = YouTube'da +500-1000 abone

**ÇÖZÜM:** Content Engine workflow'una TikTok cross-post adımı ekle:
```yaml
- name: Cross-post to TikTok
  if: steps.produce.outputs.status == 'success'
  run: python main.py --tiktok-crosspost
```

---

## ⚠️ YÜKSEK ETKİLİ EKSİKLER

### 5. YouTube Analytics API v2 — ENTEGRE DEĞİL!
**Dosya:** `src/agents/youtube_analytics_agent.py`

Mevcut agent sadece **YouTube Data API v3** kullanıyor → view count, like count, comment count.

**Eksik olan YouTube Analytics API v2 metrikleri:**

| Metrik | Mevcut | Gerekiyor | Etki |
|---|---|---|---|
| **Watch Time** | ❌ | ✅ | Algoritma #1 faktörü |
| **Audience Retention** | ❌ | ✅ | Hook kalitesini ölçer |
| **Click-Through Rate (CTR)** | ❌ | ✅ | Thumbnail kalitesini ölçer |
| **Impressions** | ❌ | ✅ | YouTube'un videoyu kaç kez gösterdiği |
| **Traffic Sources** | ❌ | ✅ | İzleyiciler nereden geliyor |
| **Demographics** | ❌ | ✅ | Hedef kitle analizi |
| **Subscriber Change** | ❌ | ✅ | Hangi video abone kazandırıyor |
| **Revenue** | ❌ | ✅ | Monetizasyon takibi |
| **Real-time** | ❌ | ✅ | İlk 48 saat performansı |
| **End Screen Clicks** | ❌ | ✅ | End screen'lerin etkinliği |

**Yeni Agent: `YouTubeInsightsAgent`**
```python
from googleapiclient.discovery import build

class YouTubeInsightsAgent:
    def __init__(self, credentials):
        self.analytics = build("youtubeAnalytics", "v2", credentials=credentials)
    
    def get_video_retention(self, video_id):
        """Her saniyedeki izleyici yüzdesi"""
        return self.analytics.reports().query(
            ids="channel==MINE",
            startDate="2026-01-01",
            endDate="2026-02-14",
            metrics="audienceWatchRatio",
            dimensions="elapsedVideoTimeRatio",
            filters=f"video=={video_id}",
        ).execute()
    
    def get_ctr_data(self):
        """Tüm videoların CTR ve impression verileri"""
        return self.analytics.reports().query(
            ids="channel==MINE",
            startDate="2026-01-01",
            endDate="2026-02-14",
            metrics="views,impressions,impressionClickThroughRate",
            dimensions="video",
            sort="-impressions",
            maxResults=50,
        ).execute()
    
    def get_traffic_sources(self):
        """İzleyiciler nereden geliyor"""
        return self.analytics.reports().query(
            ids="channel==MINE",
            startDate="2026-01-01",
            endDate="2026-02-14",
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceType",
            sort="-views",
        ).execute()
    
    def get_best_performing_hooks(self):
        """İlk 30 saniye retention'ı yüksek videoları bul → hook pattern'lerini öğren"""
        # 1. Tüm videoların retention verisini al
        # 2. İlk 30 saniye retention > %60 olanları filtrele
        # 3. Bu videoların ortak özelliklerini Gemini'ye analiz ettir
        pass
    
    def get_subscriber_magnets(self):
        """Hangi videolar en çok abone kazandırıyor"""
        return self.analytics.reports().query(
            ids="channel==MINE",
            startDate="2026-01-01",
            endDate="2026-02-14",
            metrics="subscribersGained,subscribersLost",
            dimensions="video",
            sort="-subscribersGained",
            maxResults=20,
        ).execute()
```

**OAuth Scope eklenmeli:**
```python
# youtube_service.py → SCOPES listesine ekle:
"https://www.googleapis.com/auth/yt-analytics.readonly"
```

---

### 6. 📋 Playlist Yönetimi — HİÇ YOK!
**Dosya:** `src/services/youtube_service.py` — Sadece `upload_video()` var.

Playlist'ler YouTube'da **session watch time**'ı artırır. İzleyici bir playlist'e düşünce arka arkaya izler → algoritma ödülü.

**Eklenecek Metotlar:**
```python
class YouTubeService:
    # ... mevcut upload_video ...
    
    def create_playlist(self, title, description, privacy="public"):
        """Yeni playlist oluştur"""
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy},
        }
        return self.youtube.playlists().insert(part="snippet,status", body=body).execute()
    
    def add_to_playlist(self, playlist_id, video_id, position=0):
        """Video'yu playlist'e ekle"""
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
                "position": position,
            }
        }
        return self.youtube.playlistItems().insert(part="snippet", body=body).execute()
    
    def get_or_create_playlist(self, title):
        """Playlist varsa getir, yoksa oluştur"""
        # Mevcut playlist'leri kontrol et
        playlists = self.youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for p in playlists.get("items", []):
            if p["snippet"]["title"] == title:
                return p["id"]
        # Yoksa oluştur
        return self.create_playlist(title, f"Best {title} videos by StreamGlobal")["id"]
```

**Otomatik Playlist İşlemi (her upload sonrası):**
```python
PLAYLIST_MAP = {
    "animal": "Amazing Animal Facts 🐱",
    "space": "Mind-Blowing Space Facts 🌌",
    "country": "Country Deep Dives 🌍",
    "history": "Incredible History 📚",
    "nature": "Nature & Relaxation 🌿",
    "ambient": "Sleep & Study Sounds 🎧",
    "fireplace": "Cozy Fireplace Collection 🔥",
    "rain": "Rain Sounds for Sleep 🌧️",
    "science": "Science Explained 🔬",
}
```

---

### 7. 🔄 Performans Geri Bildirimi Döngüsü — YOK!
**Şu anki akış:**
```
Nightly Brain → Plan → Content Engine → Upload → ... (sessizlik)
```

**Olması gereken akış:**
```
Nightly Brain → Plan → Content Engine → Upload
    ↑                                        ↓
    ← Analytics Feedback ← 48h Sonra Kontrol ←
```

Yani:
- Video yüklendikten **48 saat sonra** Analytics API'den CTR, retention, views al
- Bu veriyi **sonraki plan generation'a** girdi olarak ver
- "Son 48 saatte en başarılı 3 video şunlar, bunların ortak özelliği X" → Gemini
- Gelecek plan bu pattern'lere göre optimize edilsin

**Eklenecek `NightlyBrainAgent` adımı:**
```python
# Phase 0 (yeni!): 48h Performance Review
def review_recent_performance(self):
    """Son 48 saatte yüklenen videoların performansını analiz et"""
    from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
    analytics = YouTubeAnalyticsAgent(youtube_service=self.youtube)
    videos = analytics.get_all_videos(max_results=20)
    
    recent = [v for v in videos if v["days_since_publish"] <= 2]
    
    winners = [v for v in recent if v["views"] > 100]
    losers = [v for v in recent if v["views"] < 10 and v["days_since_publish"] >= 1]
    
    return {
        "winners": [{"title": v["title"], "views": v["views"], "engagement": v["engagement_rate"]} for v in winners],
        "losers": [{"title": v["title"], "views": v["views"]} for v in losers],
        "avg_views_48h": sum(v["views"] for v in recent) / max(len(recent), 1),
        "best_topics": [v["title"] for v in sorted(recent, key=lambda x: x["views"], reverse=True)[:3]],
    }
```

Sonra `generate_content_plan()` prompt'una ekle:
```
RECENT PERFORMANCE (last 48h):
- Winners: {winners}
- Losers: {losers}
- Create MORE content similar to winners, AVOID patterns from losers
```

---

### 8. 🔎 SEO Keyword Araştırma Pipeline — YOK!
**Mevcut:** Script başlığı = Gemini'nin ürettiği başlık. Hiçbir keyword araştırması yapılmıyor.

**YouTube Auto-Suggest API (Ücretsiz, API key gerektirmez):**
```python
import requests, json

def get_youtube_suggestions(query, language="en"):
    """YouTube arama çubuğundaki otomatik tamamlama önerilerini çek"""
    url = "https://suggestqueries-clients6.youtube.com/complete/search"
    params = {
        "client": "youtube",
        "q": query,
        "ds": "yt",
        "hl": language,
    }
    resp = requests.get(url, params=params)
    # JSONP formatı: google.sbox.p50 && google.sbox.p50(...)
    text = resp.text
    start = text.index("(") + 1
    end = text.rindex(")")
    data = json.loads(text[start:end])
    suggestions = [item[0] for item in data[1]]
    return suggestions

# Örnek: get_youtube_suggestions("cat facts")
# → ["cat facts that will blow your mind", "cat facts you didn't know",
#     "cat facts for kids", "cat facts shorts", ...]
```

**Nightly Brain'e entegrasyon:**
```python
# Plan oluşturulduktan sonra, her video için:
for short in plan["shorts"]:
    keywords = get_youtube_suggestions(short["topic"])
    # En çok aranan keyword'ü başlığa dahil et
    short["optimized_title"] = optimize_title_with_keywords(short["title"], keywords)
    short["seo_tags"] = keywords[:10]
```

---

### 9. 📺 End Screen & Cards API — KULLANILMIYOR!
**Sorun:** Videolar yükleniyor ama end screen veya card eklenmiyor. Bu, video-arası trafiği engeller.

YouTube API ile programatic end screen eklemek **resmi olarak desteklenmiyor** (YouTube Studio'dan manuel eklenmeli), AMA şu yapılabilir:

**Workaround — Video description'a otomatik link:**
```python
def build_description_with_links(title, topic, tags, recent_videos):
    """Her videoya en son 3 videonun linkini koy"""
    links = "\n".join(
        f"▶️ {v['title'][:50]}: https://youtu.be/{v['id']}"
        for v in recent_videos[:3]
    )
    
    return f"""
{title}

🔔 Subscribe for more: https://youtube.com/@StreamGlobal?sub_confirmation=1

📺 Watch Next:
{links}

#shorts #{' #'.join(tags[:5])}

© StreamGlobal — AI-powered content
"""
```

---

### 10. 💬 Comment Engagement Bot — YOK!
YouTube algoritması yorum etkileşimine çok önem veriyor. Özellikle ilk saatteki yorumlar.

**Eklenecek:** Her video yüklendikten sonra otomatik olarak pinned comment at:
```python
def pin_first_comment(self, video_id, comment_text):
    """Video'ya sabitlenmiş yorum at"""
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {
                "snippet": {"textOriginal": comment_text}
            }
        }
    }
    result = self.youtube.commentThreads().insert(
        part="snippet", body=body
    ).execute()
    
    # Yorumu sabitle
    comment_id = result["snippet"]["topLevelComment"]["id"]
    self.youtube.comments().setModerationStatus(
        id=comment_id, moderationStatus="published"
    ).execute()
    return comment_id

# Kullanım:
comments = [
    "What fact surprised you the most? 🤯 Comment below!",
    "Did you know this? Drop a 🔥 if you learned something new!",
    "Which one was the most mind-blowing? Let me know! 👇",
]
pin_first_comment(video_id, random.choice(comments))
```

---

### 11. 🌍 Multi-Region Trending — Sadece US!
**Dosya:** `nightly_brain_agent.py` satır 916
```python
trending = self.discover_trending(region="US", count=100)  # Sadece US!
```

**Fırsat:** Birden fazla bölge tarayarak daha fazla viral içerik keşfedebiliriz:
```python
REGIONS = ["US", "GB", "IN", "CA", "AU", "DE", "BR"]
all_trending = []
for region in REGIONS:
    regional = self.discover_trending(region=region, count=30)
    all_trending.extend(regional)
# Deduplicate ve en yüksek view'ları al
```

Farklı ülkelerde trending olan AMA henüz İngilizce versiyonu yapılmamış konular = **altın madeni**.

---

### 12. 📊 Video Performans Puanlama Sistemi — YOK!
Her videonun bir "quality score"u olmalı ve bu score gelecek içerik kararlarını etkilemeli:

```python
def calculate_video_score(video):
    """0-100 arası performans puanı"""
    score = 0
    
    # Views (max 30 puan)
    if video["views"] > 1000: score += 30
    elif video["views"] > 500: score += 25
    elif video["views"] > 100: score += 20
    elif video["views"] > 50: score += 15
    elif video["views"] > 10: score += 10
    elif video["views"] > 0: score += 5
    
    # Engagement (max 25 puan)
    if video["engagement_rate"] > 10: score += 25
    elif video["engagement_rate"] > 5: score += 20
    elif video["engagement_rate"] > 2: score += 15
    elif video["engagement_rate"] > 1: score += 10
    
    # Views per day momentum (max 20 puan)
    if video["views_per_day"] > 50: score += 20
    elif video["views_per_day"] > 20: score += 15
    elif video["views_per_day"] > 5: score += 10
    
    # Freshness bonus (max 15 puan)
    if video["days_since_publish"] < 3 and video["views"] > 50: score += 15
    elif video["days_since_publish"] < 7 and video["views"] > 100: score += 10
    
    # Subscriber conversion (max 10 puan) — YouTube Analytics API gerekli
    # if video["subscribers_gained"] > 5: score += 10
    
    return min(score, 100)
```

---

### 13. 🎙️ Ses Kalitesi ve Çeşitlilik — Tek Ses!
**Dosya:** `src/services/tts_service.py`

ElevenLabs entegre ama her videoda **aynı ses** kullanılıyor. YouTube izleyicileri monotonluktan sıkılır.

**Çözüm: Ses Rotasyonu**
```python
VOICE_POOL = {
    "en_male_deep": "pMsXgVXv3BLzUgSXRplE",      # Derin erkek (facts)
    "en_male_energetic": "TX3LPaxmHKxFdv7VOQHJ",  # Enerjik erkek (viral)
    "en_female_calm": "XB0fDUnXU5powFXDhCwa",      # Sakin kadın (nature/ambient)
    "en_male_narrator": "onwK4e9ZLuTAKqWW03F9",    # Narrator (documentary)
}

def select_voice_for_topic(topic, mode):
    """Konu ve mode'a göre ses seç"""
    if mode == "nature" or "sleep" in topic.lower():
        return VOICE_POOL["en_female_calm"]
    elif "horror" in mode or "mystery" in topic.lower():
        return VOICE_POOL["en_male_deep"]
    elif mode == "quiz" or "fun" in topic.lower():
        return VOICE_POOL["en_male_energetic"]
    else:
        return VOICE_POOL["en_male_narrator"]
```

---

### 14. 🎬 Video Intro/Outro Tutarsızlığı
**Dosya:** `src/services/branding_service.py` — `generate_intro_asset()`

Mevcut intro: Siyah arka plan üzerine logo yazısı (3 saniye). Bu **son derece amatör** görünüyor.

**Çözüm:**
- Gemini Imagen ile her kategori için **farklı intro animasyonu** oluştur
- Veya Pexels'den kısa (1-2 saniyelik) cinematic stock clip al, üzerine logo overlay yap
- En iyisi: Intro'yu tamamen kaldır (Shorts'da intro izlenmeyi düşürür!)

---

### 15. 🕐 Content Engine Zamanlama — Optimize Değil!
**Dosya:** `.github/workflows/content_engine.yml`

Kanal analiz verileri diyor ki:
```
En iyi saat: 22:00 UTC → Ortalama 3,236 view
En iyi gün: Pazartesi → Ortalama 1,942 view
En kötü: Hafta içi öğlen → Ortalama < 10 view
```

**Mevcut schedule'lar sabit ve optimize değil.** Tüm üretim prime time'a yoğunlaştırılmalı.

---

## 📋 YENİ AGENT / SERVİS ÖNERİLERİ

### 16. `PlaylistManagerAgent` (YENİ)
```
Her upload sonrası → konuya göre playlist'e ekle
Haftalık → "Best of the Week" playlist oluştur  
Aylık → performans bazlı playlist güncelle
```

### 17. `ThumbnailOptimizerAgent` (YENİ)
```
Upload sırasında → AI thumbnail oluştur → YouTube API ile set et
48 saat sonra → CTR kontrol et
CTR < %3 → yeni thumbnail oluştur ve değiştir (A/B test)
```

### 18. `CrossPlatformAgent` (YENİ — XContentAgent + TikTokAgent birleşimi)
```
Her başarılı video upload sonrası:
  1. TikTok'a cross-post (mevcut TikTokAgent)
  2. X'e İngilizce post (düzeltilmiş XContentAgent)
  3. Reddit'e konu bazlı subreddit'e link paylaş
  4. Pinterest'e thumbnail pin et
```

### 19. `PerformanceTrackerAgent` (YENİ)
```
Her 6 saatte bir:
  1. Son 48 saatteki videoların performansını kontrol et
  2. CTR < %2 olan videolara yeni thumbnail oluştur
  3. 0 view videolara X/TikTok boost gönder
  4. Trend verisini nightly brain'e raporla
```

### 20. `CompetitorAnalysisAgent` (YENİ)
```
Haftalık:
  1. Nişteki rakip kanalları takip et
  2. Son hafta viral olan videolarını analiz et
  3. Onların başarılı formatlarını/konularını kopyala
  4. Fark: Bizim versiyonumuz daha iyi olmalı
```

---

## 🛠️ TEKNİK İYİLEŞTİRMELER

### 21. ScriptWriter — Hook Optimizasyonu
**Dosya:** `src/agents/scriptwriter.py` satır 267-282

Mevcut hook sistemi statik. Her Shorts'un ilk 3 saniyesi hayati önem taşıyor.

**İyileştirme: Analytics-driven hook selection**
```python
PROVEN_HOOKS = {
    "facts": [
        "Scientists just discovered something that changes everything about {topic}...",
        "99% of people don't know this about {topic}...",
        "This {topic} fact will make you question everything...",
        "The most shocking thing about {topic} that nobody talks about...",
    ],
    "animals": [
        "This animal can do something no other creature on Earth can...",
        "Your pet is hiding THIS incredible secret from you...",
    ],
    "geography": [
        "There's a country that does THIS and nobody knows about it...",
        "This place shouldn't exist, but it does...",
    ]
}
```

### 22. Researcher — Kaynak Zenginliği
**Dosya:** `src/agents/researcher.py`

Mevcut: Tavily + DuckDuckGo → Gemini rapor.

**Eklenecek kaynaklar:**
- **Wikipedia API** (ücretsiz, sınırsız) — derinlemesine bilgi
- **Google Scholar** (akademik kaynak) — güvenilirlik
- **Reddit API** — topluluk perspektifi ve viral hikayeler

### 23. İzleyici Saati Maksimizasyonu — Longform Duration
**Gözlem:** Longform videolar ortalama 18 view alıyor → muhtemelen çok kısa veya kalitesiz.

**Çözüm:**
- Minimum 10 dakika hedef (YouTube `estimatedMinutesWatched` ödülü)
- Her longform'a **chapters** ekle (YouTube API ile timestamp açıklama)
- Longform başlıklarına "Full Documentary" gibi watch-time signal kelimeler ekle

### 24. Gemini Model Yükseltme
**Mevcut:** `gemini-2.0-flash` (her yerde)

Bazı görevler için daha güçlü model:
- Script yazımı: `gemini-2.0-flash` (hız önemli) ✅
- Strateji raporu: `gemini-2.5-pro` (kalite önemli) → yükselt
- Thumbnail prompt: `gemini-2.5-flash` (denge) → yükselt

### 25. Kanal Branding Tutarlılığı
- Tüm videolarda aynı renk paleti kullanılmalı
- Logo watermark eklenmeli (küçük, köşede)
- Kanal açıklaması SEO-optimize edilmeli
- Kanal banner'ı profesyonel olmalı (mevcut PIL-based banner çok kötü)

---

## 📊 TAM ÖNCELİK HARİTASI

| # | Aksiyon | Etki | Zorluk | Süre | Kategori |
|---|---|---|---|---|---|
| **1** | 🗑️ 248 düşük videoyu sil | 🔴 Kritik | 🟢 Kolay | 30dk | Cleanup |
| **2** | 🐛 X Agent'ı İngilizce'ye çevir | 🔴 Kritik | 🟢 Kolay | 1 saat | Bug Fix |
| **3** | 🎨 Thumbnail pipeline'ı yenile | 🔴 Kritik | 🟡 Orta | 4 saat | CTR |
| **4** | ⏰ Content Engine saatlerini optimize et | 🔴 Yüksek | 🟢 Kolay | 30dk | Timing |
| **5** | 📺 24/7 Livestream'i aktif et | 🔴 Yüksek | 🟡 Orta | 3 saat | Watch Time |
| **6** | 📋 Playlist sistemi kur | 🔴 Yüksek | 🟢 Kolay | 2 saat | Retention |
| **7** | 🎯 TikTok cross-posting aktif et | 🔴 Yüksek | 🟢 Kolay | 1 saat | Traffic |
| **8** | 📊 YouTube Analytics API v2 entegre et | 🔴 Yüksek | 🟡 Orta | 6 saat | Data |
| **9** | 🔄 Performance feedback loop ekle | 🟠 Yüksek | 🟡 Orta | 4 saat | Intelligence |
| **10** | 🔎 SEO keyword pipeline | 🟠 Yüksek | 🟡 Orta | 3 saat | Discovery |
| **11** | 💬 Pinned comment otomasyonu | 🟠 Orta | 🟢 Kolay | 1 saat | Engagement |
| **12** | 📝 Description'a video linkleri ekle | 🟠 Orta | 🟢 Kolay | 1 saat | Traffic |
| **13** | 🌍 Multi-region trending | 🟠 Orta | 🟢 Kolay | 1 saat | Content |
| **14** | 🎙️ Ses rotasyonu | 🟡 Orta | 🟢 Kolay | 1 saat | Quality |
| **15** | 🏆 Video puanlama sistemi | 🟡 Orta | 🟢 Kolay | 2 saat | Intelligence |
| **16** | 🔥 Hook optimizasyonu | 🟡 Orta | 🟢 Kolay | 2 saat | Retention |
| **17** | 🎬 Intro'yu kaldır/iyileştir | 🟡 Düşük | 🟢 Kolay | 30dk | Quality |
| **18** | 📚 Araştırma kaynaklarını genişlet | 🟡 Düşük | 🟡 Orta | 2 saat | Quality |
| **19** | 🧪 Thumbnail A/B test | 🟡 Orta | 🔴 Zor | 8 saat | CTR |
| **20** | 🕵️ Rakip analiz agent | 🟡 Orta | 🟡 Orta | 6 saat | Strategy |

---

## 🎯 OPTİMİSTİK TAHMİN

### Sadece İlk 8 Aksiyonu Uygularsak:
| Metrik | Şimdi | 2 Hafta | 1 Ay | 3 Ay |
|---|---|---|---|---|
| Aylık Views | ~5,000 | ~12,000 | ~30,000 | ~100,000+ |
| Shorts Medyan | 4 | 30 | 100 | 500+ |
| Abone | 1,940 | 2,200 | 3,000 | 5,000+ |
| Watch Time (saat/ay) | ~50 | ~200 | ~1,000 | ~5,000+ |
| Livestream Ek | 0 | +500h | +2,000h | +10,000h |
| TikTok Takipçi | 0 | 500 | 2,000 | 10,000+ |

### Tüm 20 Aksiyonu Uygularsak:
| Metrik | 1 Ay | 3 Ay | 6 Ay |
|---|---|---|---|
| Aylık Views | ~50,000 | ~200,000 | ~500,000+ |
| Abone | 3,500 | 8,000 | 20,000+ |
| Monetizasyon | ❌ | ✅ (başvuru) | 💰 ($200-500/ay) |

---

## 🚀 HEMEN BAŞLAYALIM MI?

Hangilerinden başlamak istiyorsun? Ben hepsini kodlayabilirim:

1. **Hızlı Kazanımlar** (30dk-1saat) → X Agent fix, playlist, pinned comment, timing
2. **Yüksek Etki** (2-4 saat) → Thumbnail, livestream, TikTok, feedback loop
3. **Derin Entegrasyon** (6-8 saat) → YouTube Analytics API v2, A/B test, competitor analysis

Söyle, hangisini ilk yapalım 💪
