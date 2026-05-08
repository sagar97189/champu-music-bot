#!/bin/bash

echo "🚀 Setting up Champu Music Bot..."

# Create project folder
mkdir champu-bot
cd champu-bot

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install python-telegram-bot yt-dlp

# Create bot file
cat > bot.py <<EOL
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import os

BOT_TOKEN = "8747905993:AAFP_nxBNivbjHXZr5A3pINxS4J9Si6DbbM"
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 Welcome to Champu Music Bot!\\nSend any song name 🎶"
    )

async def download_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'outtmpl': 'song.%(ext)s'
    }

    await update.message.reply_text("🎶 Champu is finding your song... ⏳")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            file_name = ydl.prepare_filename(info['entries'][0])

        await update.message.reply_audio(audio=open(file_name, 'rb'))
        os.remove(file_name)

        await update.message.reply_text("🔥 Done by Champu Bot")

    except Exception as e:
        await update.message.reply_text("Error 😢")

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_song))

app.run_polling()
EOL

echo "✅ Setup complete!"
echo "👉 Now run: python bot.py"