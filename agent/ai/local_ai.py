import ollama
import asyncio
from ai.personality import SYSTEM_PERSONALITY

class LocalAI:
    def __init__(self, model_name="mistral"):
        self.model_name = model_name

    async def generate_reply(self, message_text, context=None):
        try:
            # Construct messages list for conversation
            messages = [{"role": "system", "content": SYSTEM_PERSONALITY}]
            
            if context:
                for m in context:
                    messages.append({"role": "user", "content": f"{m['sender']}: {m['text']}"})
            
            messages.append({"role": "user", "content": message_text})

            # Run Ollama in a thread pool to avoid blocking the event loop
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model_name,
                messages=messages,
                options={"temperature": 0.8, "num_predict": 100}
            )
            
            content = response['message']['content'].strip()
            # Clean up potential AI artifacts
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            
            return content
        except Exception as e:
            return f"Error: {str(e)}"

    async def verify_model(self):
        try:
            models = ollama.list()
            return any(m['name'].split(':')[0] == self.model_name for m in models['models'])
        except Exception:
            return False

local_ai = LocalAI(model_name="mistral")
