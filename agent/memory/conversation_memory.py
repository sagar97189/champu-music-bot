import time
from collections import deque

class ConversationMemory:
    def __init__(self, max_history=10):
        self.history = {}
        self.max_history = max_history
        self.last_reply_time = {}
        self.user_cooldowns = {}
        
    def add_message(self, chat_id, sender, text):
        if chat_id not in self.history:
            self.history[chat_id] = deque(maxlen=self.max_history)
        self.history[chat_id].append({"sender": sender, "text": text})

    def get_context(self, chat_id):
        if chat_id not in self.history:
            return []
        return list(self.history[chat_id])

    def can_reply(self, chat_id, user_id, cooldown_seconds=45):
        now = time.time()
        if chat_id in self.last_reply_time:
            if now - self.last_reply_time[chat_id] < cooldown_seconds:
                return False
        if user_id in self.user_cooldowns:
            if now - self.user_cooldowns[user_id] < cooldown_seconds * 1.5:
                return False
        return True

    def mark_replied(self, chat_id, user_id):
        now = time.time()
        self.last_reply_time[chat_id] = now
        self.user_cooldowns[user_id] = now

memory = ConversationMemory()
