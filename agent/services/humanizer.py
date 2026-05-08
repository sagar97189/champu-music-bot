import asyncio
import random

class Humanizer:
    @staticmethod
    def get_reply_delay(text_length):
        """Calculates realistic delay based on message length."""
        if text_length < 30:
            return random.uniform(3, 8)
        else:
            return random.uniform(8, 20)

    @staticmethod
    def process_text(text):
        """Adds human-like variations to text."""
        # 20% chance of lowercase only
        if random.random() < 0.2:
            text = text.lower()
            
        # 10% chance of removing punctuation at the end
        if random.random() < 0.1 and text.endswith(('.', '!', '?')):
            text = text[:-1]
            
        return text

humanizer = Humanizer()
