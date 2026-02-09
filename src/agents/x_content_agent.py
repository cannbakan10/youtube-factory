import os
import json
import time
import random
from datetime import datetime
from src.agents.researcher import ResearchAgent
from src.services.twitter_service import TwitterService
from src.services.pexels_service import PexelsService
from src.services.pixabay_service import PixabayService
from src.utils.logger import get_logger

logger = get_logger(__name__)

class XContentAgent:
    def __init__(self, factory_instance=None):
        self.researcher = ResearchAgent()
        self.twitter = TwitterService()
        self.pexels = PexelsService()
        self.pixabay = PixabayService()
        self.factory = factory_instance
        
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.project_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.plan_file = os.path.join(self.data_dir, "x_daily_plan.json")
        self.history_file = os.path.join(self.data_dir, "x_history.json")

    def generate_daily_plan(self, custom_topic=None):
        """Generates 1 high-quality, media-rich post for the day."""
        logger.info(f"Generating daily plan for X (Topic: {custom_topic or 'Auto Trend'})...")
        
        # Strategy Update: Always try to be media-rich (image/video) for maximum engagement
        post_type = "image"
        
        if custom_topic:
            topic = custom_topic
        else:
            # Categorize to ensure variety
            categories = ["bilim", "tarih", "uzay", "doğa", "hayvanlar", "teknoloji", "psikoloji", "sanat", "coğrafya", "arkeoloji", "denizaltı"]
            selected_category = random.choice(categories)
            topic = f"{selected_category} hakkında bilinmeyen, çok şaşırtıcı, 'yok artık' dedirtecek ilginç bir bilgi"
            
        research_data = self.researcher.research(topic)
        
        prompt = f"""
        RESEARCH DATA:
        {research_data}
        
        TASK:
        Bu bilgiden yola çıkarak X (Twitter) için 1 adet "Vay Be!" dedirtecek post hazırla.
        
        STRATEJİ KURALLARI:
        1. Dil tamamen Türkçe olmalı. 
        2. ASLA "Stream Global" veya herhangi bir marka ismi kullanma.
        3. BAŞLIK: İlgi çekici bir emoji ile başla (Örn: 🧠 BUNLARI BİLİYOR MUYDUNUZ?, 🌌 ŞAŞIRTICI GERÇEK:).
        4. SORU: Postun sonuna mutlaka etkileşim artıracak bir soru ekle (Örn: Sizce bu mümkün mü?, En çok hangisine şaşırdınız?).
        5. HASHTAG: Maksimum 2-3 tane hashtag kullan. #VayBeBilgi etiketi SABİT olsun, diğeri konuya özel olsun (Örn: #uzay, #tarih).
        6. ÇEŞİTLİLİK: Daha önceki postlarla aynı cümle yapılarını kullanma. ASLA "Satürn" hakkında bilgi verme; bu konu çok kez işlendi, farklı bir gezegen veya tamamen farklı bir konu seç.
        
        FORMAT (JSON):
        {{
          "type": "image",
          "text": "Post metni...",
          "keywords": ["görsel aramak için 2-3 adet ingilizce anahtar kelime"],
          "scheduled_time": "08:00"
        }}
        
        Sadece JSON objesini döndür (liste değil).
        """
        
        response = self.researcher._generate_report_gemini(prompt)
        try:
            clean_response = response.strip()
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1].split("```")[0].strip()
                
            post_data = json.loads(clean_response)
            plan = [post_data] # Store as a list of 1 item for compatibility
            
            # Anti-Repeat: Check history
            if self._is_repeated(post_data["text"]):
                logger.warning("Generated post looks repeated. Retrying...")
                return self.generate_daily_plan()

            with open(self.plan_file, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Vay Be Plan generated: {post_data['type']} at {post_data['scheduled_time']}")
            return plan
        except Exception as e:
            logger.error(f"Failed to parse daily plan: {e}")
            return None

    def _is_repeated(self, text):
        if not os.path.exists(self.history_file):
            return False
        
        # Clean text for comparison
        def clean(t):
            return "".join(c for i, c in enumerate(t.lower()) if c.isalnum() or c.isspace()).strip()

        clean_text = clean(text)
        
        # Hard Blacklist for "Saturn" and its common variations in Turkish
        blacklist = ["saturn", "satürn", "halkalı gezegen"]
        if any(word in clean_text for word in blacklist):
            logger.warning(f"Post contains blacklisted word: {clean_text}")
            return True
        
        with open(self.history_file, "r", encoding="utf-8") as f:
            try:
                history = json.loads(f.read())
            except:
                return False
                
            for old_post in history:
                old_text = old_post.get("text", "")
                if not old_text: continue
                
                # Check for 60% substring match
                clean_old = clean(old_text)
                if len(clean_text) > 20 and clean_text[:20] in clean_old:
                    return True
                if len(clean_old) > 20 and clean_old[:20] in clean_text:
                    return True
                    
        return False

    def run_scheduled_tasks(self, force=False):
        """Checks the plan and executes posts if it's time or if forced."""
        if not os.path.exists(self.plan_file):
            plan = self.generate_daily_plan()
            if not plan: return
        else:
            with open(self.plan_file, "r", encoding="utf-8") as f:
                plan = json.loads(f.read())
            
            # If everything in the current plan is already posted, generate a NEW one
            if all(post.get("posted", False) for post in plan):
                logger.info("Current plan is fully executed. Generating fresh content...")
                plan = self.generate_daily_plan()
                if not plan: return
        
        # Current time in UTC (GitHub default)
        current_time = datetime.now().strftime("%H:%M")
        logger.info(f"Checking schedule... Current time: {current_time}, Plan time: {plan[0].get('scheduled_time')}")
        
        for post in plan:
            if post.get("posted", False):
                continue
                
            plan_time = post["scheduled_time"]
            # Trigger if we are within the scheduled window OR if it's a manual force run
            if force or current_time >= plan_time:
                success = self.execute_post(post)
                if success:
                    post["posted"] = True
                    self._save_plan(plan)
                    self._log_history(post)
                else:
                    logger.error("Execution failed. Check API logs.")
    
    def execute_post(self, post):
        """Executes a single post with media support or just text."""
        logger.info(f"Executing Vay Be post: {post['text'][:50]}...")
        
        if post["type"] == "text":
            return self.twitter.post_text(post["text"])
        
        # Try media if type is image or video
        media_path = None
        keywords = post.get("keywords", ["interesting"])
        
        try:
            if post["type"] == "image":
                media_path = self.pexels.get_image(keywords)
                if not media_path:
                    media_path = self.pixabay.get_image(keywords)
            elif post["type"] == "video":
                media_path = self.pexels.get_video(keywords, orientation="portrait")

            if media_path:
                logger.info(f"Attempting to post with media: {media_path}")
                result = self.twitter.post_with_media(post["text"], media_path)
                if result: 
                    return result
                logger.warning("Media post failed (likely API tier), falling back to text only.")
        except Exception as e:
            logger.warning(f"Media handling failed: {e}. Falling back to text.")
        
        # Ultimate fallback for all types
        logger.info("Posting as text-only tweet...")
        return self.twitter.post_text(post["text"])

    def _save_plan(self, plan):
        with open(self.plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)

    def _log_history(self, post):
        history = []
        if os.path.exists(self.history_file):
            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.loads(f.read())
        
        post["posted_at"] = datetime.now().isoformat()
        history.append(post)
        
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
