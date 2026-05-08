import os
import asyncio
import logging
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from telegram.error import TimedOut

# --- Configuration ---
BOT_TOKEN = "8747905993:AAFP_nxBNivbjHXZr5A3pINxS4J9Si6DbbM"
PERFORMER_NAME = "Champu Bot 🎧"
CUSTOM_FFMPEG_PATH = r"C:\Users\Admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text("🎧 Welcome to Champu Music Bot!\nSend me a song name or YouTube link. 🎶")

async def download_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Downloads a song and sends it with extended timeouts and retry logic."""
    query = update.message.text
    status_message = await update.message.reply_text("🎶 Champu is finding your song... ⏳")
    
    files_to_delete = []

    # yt-dlp Options - Quality reduced to 128kbps for faster upload/smaller size
    ydl_opts_mp3 = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'restrictfilenames': True,
        'outtmpl': '%(title)s.%(ext)s',
        'ffmpeg_location': CUSTOM_FFMPEG_PATH,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',  # Reduced from 192 for better reliability
        }],
    }

    ydl_opts_fallback = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'restrictfilenames': True,
        'outtmpl': '%(title)s.%(ext)s',
    }

    logger.info(f"Downloading started: {query}")

    try:
        def process_download():
            # Attempt 1: MP3
            try:
                with yt_dlp.YoutubeDL(ydl_opts_mp3) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                    if not info or 'entries' not in info or not info['entries']:
                        return None
                    entry = info['entries'][0]
                    base_path = ydl.prepare_filename(entry)
                    mp3_path = os.path.splitext(base_path)[0] + ".mp3"
                    if os.path.exists(mp3_path):
                        return {'path': mp3_path, 'title': entry.get('title'), 'is_mp3': True}
            except Exception as e:
                logger.warning(f"MP3 conversion failed: {e}")

            # Attempt 2: Fallback
            try:
                with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                    if not info or 'entries' not in info or not info['entries']:
                        return None
                    entry = info['entries'][0]
                    file_path = ydl.prepare_filename(entry)
                    if os.path.exists(file_path):
                        return {'path': file_path, 'title': entry.get('title'), 'is_mp3': False}
            except Exception as e:
                logger.error(f"Fallback download failed: {e}")
            return None

        # Execute download using asyncio.to_thread for better async performance
        result = await asyncio.to_thread(process_download)

        if not result or not os.path.exists(result['path']):
            await status_message.edit_text("😢 Sorry, I couldn't find that song.")
            return

        files_to_delete.append(result['path'])
        caption = "🔥 Downloaded by @Champu_Bot"
        if not result['is_mp3']:
            caption = "⚠️ Sent without MP3 conversion\n" + caption

        # --- Send Audio with Retry Logic and Extended Timeouts ---
        for attempt in range(2):
            try:
                with open(result['path'], 'rb') as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=result['title'],
                        performer=PERFORMER_NAME,
                        caption=caption,
                        read_timeout=60,   # Extended timeout
                        write_timeout=60,  # Extended timeout
                        connect_timeout=60 # Extended timeout
                    )
                break # Success!
            except TimedOut:
                if attempt == 0:
                    logger.warning("Upload timed out, retrying once...")
                    await status_message.edit_text("⚠️ Network slow, retrying upload... ⏳")
                    await asyncio.sleep(2)
                else:
                    raise
            except Exception as e:
                logger.error(f"Send error on attempt {attempt+1}: {e}")
                if attempt == 1: raise

        await status_message.delete()

    except Exception as e:
        logger.error(f"Global error: {e}")
        await status_message.edit_text("❌ Failed to send audio. Please try again later.")

    finally:
        for file in files_to_delete:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    logger.info(f"Cleaned up: {file}")
                except Exception: pass

if __name__ == "__main__":
    # Configure global request timeouts
    request = HTTPXRequest(
        read_timeout=60, 
        write_timeout=60, 
        connect_timeout=60
    )

    # Initialize Application
    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_song))

    print("🚀 Champu Bot is online with timeout fixes...")
    app.run_polling()
