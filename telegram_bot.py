import os
import subprocess
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from dotenv import load_dotenv

import google.genai as genai

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key) if api_key else None

def save_chat_id(update: Update):
    chat_id = update.message.chat_id
    with open("data/telegram_chat_id.txt", "w") as f:
        f.write(str(chat_id))

# States
ASK_COUNT = 1
CONFIRM_TOPICS = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    msg = (
        "🤖 *Youtube Factory Yönetim Botu Aktif!*\n\n"
        "Kullanılabilir Komutlar:\n\n"
        "👉 `/videouret <sayı>` - Otomatik plana göre 'en' (İngilizce) dilinde shorts üretir.\n"
        "👉 `/analiz` - Detaylı kanal analizi yapar, az izlenenleri silip kopya/tekrar eden içerikleri temizler.\n"
        "👉 `/trendcek` - İnternetteki yeni trendleri araştırıp analiz ile birlikte günlük planı oluşturur.\n"
        "👉 `/uretozel <konu>` - Belirttiğiniz konuda özel bir shorts üretir.\n"
        "👉 `/uzunvideo` - Uzun (5+ dk) Youtube trend videoları üretmeniz için interaktif sihirbazı başlatır.\n\n"
        "_Not: Islemler sunucuda arkaplanda (pm2) çalişacağından geri dönüş gecikebilir. Loglari sunucudan izleyebilirsiniz._"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def videouret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    count = 1
    if context.args:
        try:
            count = int(context.args[0])
        except ValueError:
            pass
            
    await update.message.reply_text(f"⏳ *İşlem Başladı:* {count} adet Shorts üretimi arkaplanda sıraya alındı...", parse_mode='Markdown')
    subprocess.Popen(["venv/bin/python3", "main.py", "--execute-plan", "--plan-shorts", str(count), "--langs", "en"])

async def trendcek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    await update.message.reply_text("⏳ *Trend Araştırması:* Nightly Brain (Gece Planlayıcısı) tetiklendi. Analiz ve Trend tespiti başlatıldı...", parse_mode='Markdown')
    subprocess.Popen(["venv/bin/python3", "main.py", "--nightly"])

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    msg = (
        "🔬 *Detaylı Kanal Analizi ve Temizlik Başlatıldı!*\n\n"
        "Şunlar yapılıyor:\n"
        "1. Düşük izlenmeli videolar taranıp silinecek/gizlenecek\n"
        "2. Kopya veya tekrar eden içerikler kaldırılacak\n"
        "3. İçeriklerin izlenme ve abone getirme performansları incelenecek\n"
        "4. Yeni trendlere göre yarınki yayın planı oluşturulacak\n\n"
        "_Not: Analiz arka planda uzun sürebilir ve tamamlandığında loglar üzerinden sonuçları izleyebilirsiniz._"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')
    subprocess.Popen(["venv/bin/python3", "main.py", "--nightly"])

async def uretozel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("❌ Lütfen bir konu girin! Örnek:\n`/uretozel Antik Mısır Sırları`", parse_mode='Markdown')
        return
        
    await update.message.reply_text(f"⏳ *Özel Üretim:* '{topic}' konusunda bağımsız İngilizce video üretimi başlatıldı!", parse_mode='Markdown')
    subprocess.Popen(["venv/bin/python3", "main.py", "--topic", topic, "--langs", "en"])

# --- Uzun Video Sihirbazı ---
async def uzunvideo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    await update.message.reply_text(
        "🎬 *Uzun Video (5+ Dk) Üretim Sihirbazı*\n\n"
        "Google ve YouTube trendlerine göre uzun videolar üreteceğiz.\nKaç adet video üretmek istiyorsun? (Örn: 2)",
        parse_mode='Markdown'
    )
    return ASK_COUNT

async def uzunvideo_ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Lütfen sadece bir sayı girin (Örn: 2). /iptal komutu ile çıkabilirsiniz.")
        return ASK_COUNT
        
    count = int(text)
    if count < 1 or count > 10:
        await update.message.reply_text("❌ Lütfen 1 ile 10 arasında bir sayı girin.")
        return ASK_COUNT

    context.user_data['video_count'] = count
    await update.message.reply_text(f"⏳ Harika, {count} adet uzun video için küresel trendler (Google/YouTube API kullanarak) tespit ediliyor... Lütfen bekleyin.", parse_mode='Markdown')

    try:
        from src.agents.nightly_brain_agent import NightlyBrainAgent
        from src.agents.youtube_analytics_agent import YouTubeAnalyticsAgent
        
        import logging
        logging.getLogger().setLevel(logging.ERROR) # sessiz
        brain = NightlyBrainAgent()
        
        # Geçmiş içerikleri alıyoruz ki AYNI içerik üretilmesin
        analytics = YouTubeAnalyticsAgent(youtube_service=brain.youtube)
        recent_videos = analytics.get_all_videos(max_results=40)
        recent_titles = "\n".join([f"- {v['title']}" for v in recent_videos]) if recent_videos else "Yok"
        
        # YouTube API üzerinden günlük popüler 20 USA videosunu çekiyoruz:
        top_trends = brain.discover_trending(region="US", count=20)
        
        # Sadece başlıkları alarak ipucu hazırlıyoruz:
        trend_titles = "\n".join([f"- {t['title']}" for t in top_trends])
        
        prompt = f"""
Here are the top trending YouTube videos in the US right now based on real YouTube Data API:
{trend_titles}

CRITICAL RULES FOR REPETITION PREVENTION:
Here are the titles of my recently uploaded contents on this channel:
{recent_titles}
DO NOT suggest ANY topic that is highly similar, directly identical, or a re-hash of my recent uploads above. Ensure fresh, new concepts only.

Based heavily on these exact trends and strictly avoiding my history, provide {count} highly viral, highly engaging real-world topics optimized for an educational / storytelling Long-form video (minimum 5 minutes).
Return ONLY the topics, separated by the '|' character. 
DO NOT add any extra text, newlines or markdown.
Example format: The Crazy Economics of Super Bowl Ads | Uncovering the Secrets Behind ChatGPT 4.5
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        topics = response.text.replace('\n', '').strip().split('|')
        topics = [t.strip() for t in topics if t.strip()][:count]
        context.user_data['topics'] = topics
        
        topic_list = "\n".join([f"📌 {i+1}. {t}" for i, t in enumerate(topics)])
        
        reply_keyboard = [["Üret", "İptal"]]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"🎯 *Gerçek YouTube Trendlerinden Türetilen İçerik Fikirleri:*\n\n{topic_list}\n\n❗️ *Bu konuları İngilizce dilinde en az 5 dakikalık Youtube videoları haline dönüştüreyim mi?*",
            parse_mode='Markdown',
            reply_markup=markup
        )
        return CONFIRM_TOPICS
    except Exception as e:
        await update.message.reply_text("❌ Trendler çekilirken bir hata oluştu: " + str(e))
        return ConversationHandler.END

async def uzunvideo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update)
    answer = update.message.text.lower()
    if answer in ['üret', 'uret', 'evet', 'ok', 'onaylıyorum']:
        topics = context.user_data.get('topics', [])
        await update.message.reply_text("🚀 Onaylandı! Uzun videolar tek tek üretilmeye başlandı. Ciddi bir işlem sürebilir, arkaplanda otomatik çalışacak ve üretim bittikçe sizi Telegram'dan haberdar edeceğim!", reply_markup=ReplyKeyboardRemove())
        
        sh_script = "/tmp/run_long_videos.sh"
        with open(sh_script, "w") as f:
            f.write("#!/bin/bash\ncd /root/youtube-factory\nsource venv/bin/activate\n")
            for t in topics:
                t_escaped = t.replace('"', '\\"')
                f.write(f'python3 main.py --topic "{t_escaped}" --langs en --type long\n')
                
        os.chmod(sh_script, 0o755)
        subprocess.Popen(["nohup", "bash", sh_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
        
        return ConversationHandler.END
    else:
        await update.message.reply_text("🛑 İşlem iptal edildi.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 İşlem iptal edildi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    if not TELEGRAM_TOKEN:
         print("❌ TELEGRAM_BOT_TOKEN .env dosyasında bulunamadı!")
         return
         
    print("🚀 Telegram Bot Başlatıldı ve Komut Dinliyor...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("videouret", videouret))
    app.add_handler(CommandHandler("analiz", analiz))
    app.add_handler(CommandHandler("trendcek", trendcek))
    app.add_handler(CommandHandler("uretozel", uretozel))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('uzunvideo', uzunvideo_start)],
        states={
            ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, uzunvideo_ask_count)],
            CONFIRM_TOPICS: [MessageHandler(filters.TEXT & ~filters.COMMAND, uzunvideo_confirm)],
        },
        fallbacks=[CommandHandler('iptal', cancel)],
    )
    app.add_handler(conv_handler)
    
    app.run_polling()

if __name__ == '__main__':
    main()
