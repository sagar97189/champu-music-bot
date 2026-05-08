import time
from config.settings import MAX_MESSAGES_PER_HOUR, DAILY_LIMIT

class RateLimiter:
    def __init__(self):
        self.hourly_messages = []
        self.daily_messages = []

    def check_limit(self):
        now = time.time()
        self.hourly_messages = [t for t in self.hourly_messages if now - t < 3600]
        self.daily_messages = [t for t in self.daily_messages if now - t < 86400]
        if len(self.hourly_messages) >= MAX_MESSAGES_PER_HOUR:
            return False, "Hourly limit"
        if len(self.daily_messages) >= DAILY_LIMIT:
            return False, "Daily limit"
        return True, "OK"

    def record_message(self):
        now = time.time()
        self.hourly_messages.append(now)
        self.daily_messages.append(now)

limiter = RateLimiter()
