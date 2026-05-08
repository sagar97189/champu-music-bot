import os
from groq import Groq
from config.settings import GROQ_API_KEY

class AIProvider:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.system_prompt = """
        You are a real Telegram user. You are active in group chats and voice chat discussion sections.
        Your tone is natural, cool, Gen-Z/internet style. 
        Keep replies short, engaging, and context-aware.
        Never sound like a robot or assistant. 
        Avoid phrases like "As an AI..." or "How can I help you?".
        Use lowercase occasionally. Be helpful but with a chill personality.
        Avoid spammy or promotional behavior.
        If you see someone joining a voice chat or if a voice chat starts, be welcoming.
        """

    def generate_reply(self, message_text, context=None):
        try:
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if context:
                context_str = "\n".join([f"{m['sender']}: {m['text']}" for m in context])
                messages.append({"role": "user", "content": f"Context of recent messages:\n{context_str}\n\nNew message to reply to: {message_text}"})
            else:
                messages.append({"role": "user", "content": message_text})

            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model="llama3-70b-8192",
                temperature=0.7,
                max_tokens=100
            )
            
            reply = chat_completion.choices[0].message.content.strip()
            if reply.startswith('"') and reply.endswith('"'):
                reply = reply[1:-1]
            return reply
        except Exception as e:
            print(f"AI Generation Error: {e}")
            return None

ai_provider = AIProvider()
