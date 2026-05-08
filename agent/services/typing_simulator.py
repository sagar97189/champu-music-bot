import asyncio

class TypingSimulator:
    @staticmethod
    async def simulate(client, entity, duration):
        """Shows 'typing...' action for a specific duration."""
        try:
            async with client.action(entity, 'typing'):
                await asyncio.sleep(duration)
        except Exception:
            pass

typing_simulator = TypingSimulator()
