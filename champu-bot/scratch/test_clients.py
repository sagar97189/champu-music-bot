import asyncio
import os
from hydrogram import Client
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def test():
    print("Testing Assistant...")
    assistant = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)
    await assistant.start()
    me_a = await assistant.get_me()
    print(f"Assistant: {me_a.first_name}")
    
    print("Testing Bot...")
    bot = Client("test_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await bot.start()
    me_b = await bot.get_me()
    print(f"Bot: {me_b.first_name}")
    
    await assistant.stop()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(test())
