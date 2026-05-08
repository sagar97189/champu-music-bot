import asyncio
import os
from hydrogram import Client
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def check():
    bot = Client("check_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await bot.start()
    me = await bot.get_me()
    print(f"Bot Username: @{me.username}")
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(check())
