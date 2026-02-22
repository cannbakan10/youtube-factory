import os
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Youtube Factory Yönetim Botu Aktif!*\n\n"
        "Kullanılabilir Komutlar:\n\n"
        "👉 `/videouret <sayı>` - Otomatik plana göre 'en' (İngilizce) dilinde shorts üretir. (Örn: /videouret 2)\n"
        "👉 `/trendcek` - İnternetteki yeni trendleri araştırır ve günlük planı baştan oluşturur.\n"
        "👉 `/uretozel <konu>` - Plana bakmadan doğrudan belirttiğiniz konuda özel bir shorts üretir. (Örn: /uretozel AI Teknolojileri)\n\n"
        "_Not: Islemler sunucuda arkaplanda (pm2) çalişacağından hemen dönüş yapmayabilir. Loglari DigitalOcean panelinizden izleyebilirsiniz._"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def videouret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = 1
    if context.args:
        try:
            count = int(context.args[0])
        except ValueError:
            pass
            
    await update.message.reply_text(f"⏳ *İşlem Başladı:* {count} adet Shorts üretimi arkaplanda sıraya alındı...", parse_mode='Markdown')
    # PM2 üzerinden tekil komut ya da subprocess tetiklenebilir
    # PM2 altında main.py çalıştırmak yerine subprocess ile bağımsız süreç yaratıyoruz
    subprocess.Popen(["venv/bin/python3", "main.py", "--execute-plan", "--plan-shorts", str(count), "--langs", "en"])

async def trendcek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ *Trend Araştırması:* Nightly Brain (Gece Planlayıcısı) tetiklendi. Yeni trendler çekiliyor...", parse_mode='Markdown')
    subprocess.Popen(["venv/bin/python3", "src/agents/nightly_brain_agent.py"])

async def uretozel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    if not topic:
        await update.message.reply_text("❌ Lütfen bir konu girin! Örnek:\n`/uretozel Antik Mısır Sırları`", parse_mode='Markdown')
        return
        
    await update.message.reply_text(f"⏳ *Özel Üretim:* '{topic}' konusunda bağımsız İngilizce video üretimi başlatıldı!", parse_mode='Markdown')
    subprocess.Popen(["venv/bin/python3", "main.py", "--topic", topic, "--langs", "en"])


def main():
    if not TELEGRAM_TOKEN:
         print("❌ TELEGRAM_BOT_TOKEN .env dosyasında bulunamadı!")
         return
         
    print("🚀 Telegram Bot Başlatıldı ve Komut Dinliyor...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("videouret", videouret))
    app.add_handler(CommandHandler("trendcek", trendcek))
    app.add_handler(CommandHandler("uretozel", uretozel))
    
    app.run_polling()

if __name__ == '__main__':
    main()
