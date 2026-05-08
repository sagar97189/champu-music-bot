import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

MAX_MESSAGES_PER_HOUR = int(os.getenv("MAX_MESSAGES_PER_HOUR", 20))
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 150))
MIN_DELAY = int(os.getenv("MIN_DELAY", 10))
MAX_DELAY = int(os.getenv("MAX_DELAY", 45))

ENABLED_GROUPS = os.getenv("ENABLED_GROUPS", "").split(",")
ENABLED_GROUPS = [int(g) for g in ENABLED_GROUPS if g.strip()]

TRIGGER_KEYWORDS = ["bot", "ai", "hello", "hi", "help", "vc", "voice", "chat"]

TYPING_SPEED_CPS = 7
EMOJI_CHANCE = 0.4
SHORT_REPLY_CHANCE = 0.3
