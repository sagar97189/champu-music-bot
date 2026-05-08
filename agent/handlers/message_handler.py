import asyncio
import random
from telethon import events, types
from ai.local_ai import local_ai
from services.filters import filters
from services.humanizer import humanizer
from services.limiter import limiter
from services.typing_simulator import typing_simulator
from memory.sqlite_memory import db_memory

class MessageHandler:
    def __init__(self, client):
        self.client = client
        self.me = None

    async def init(self):
        self.me = await self.client.get_me()
        await db_memory.init()

    async def handle_new_message(self, event):
        if not self.me: await self.init()

        chat_id = event.chat_id
        sender = await event.get_sender()
        sender_id = event.sender_id
        username = getattr(sender, 'first_name', 'Unknown')
        text = event.raw_text

        # 1. Ignore self and bots
        if not filters.should_process(event, self.me.id):
            return

        # 2. Store in SQLite memory
        await db_memory.save_message(chat_id, sender_id, username, text)

        # 3. Decision Logic: Should we reply?
        is_triggered = filters.contains_trigger(text)
        is_reply_to_me = event.is_reply and (await event.get_reply_message()).sender_id == self.me.id
        
        # Service message (VC Start)
        if event.message.is_service:
            await self.handle_service_message(event)
            return

        if not (is_triggered or is_reply_to_me or random.random() < 0.05):
            return

        # 4. Check Rate Limits & Cooldowns
        can_reply, _ = limiter.check_limit()
        if not can_reply: return

        last_reply = await db_memory.get_last_reply_time(chat_id)
        if (asyncio.get_event_loop().time() - last_reply) < 45: # Per-chat cooldown
            return

        # 5. Generate Local AI Reply
        context = await db_memory.get_recent_context(chat_id)
        reply_text = await local_ai.generate_reply(text, context)
        
        if not reply_text or "Error:" in reply_text:
            return

        # 6. Humanize & Delay
        reply_text = humanizer.process_text(reply_text)
        delay = humanizer.get_reply_delay(len(reply_text))
        
        # 7. Typing Simulation
        await typing_simulator.simulate(self.client, event.input_chat, delay * 0.6)
        await asyncio.sleep(delay * 0.4)

        # 8. Send
        try:
            # Check if it should be a reply or a normal comment
            await event.reply(reply_text)
            limiter.record_message()
            await db_memory.mark_replied(chat_id)
            print(f"[AI] Sent: {reply_text}")
        except Exception as e:
            print(f"[Error] {e}")

    async def handle_service_message(self, event):
        from telethon.tl.types import MessageActionGroupCall
        if isinstance(event.message.action, MessageActionGroupCall):
            # Voice Chat Detected
            greeting = await local_ai.generate_reply("A voice chat just started in the group. Say something cool and short.")
            if greeting:
                await asyncio.sleep(5)
                await event.reply(greeting)

def register_handlers(client):
    handler = MessageHandler(client)
    @client.on(events.NewMessage(incoming=True))
    async def on_msg(event):
        await handler.handle_new_message(event)
    return handler
