from config.settings import TRIGGER_KEYWORDS, ENABLED_GROUPS

class MessageFilter:
    @staticmethod
    def should_process(event, me_id):
        if event.sender_id == me_id:
            return False
        if event.sender and hasattr(event.sender, 'bot') and event.sender.bot:
            return False
        if ENABLED_GROUPS and event.chat_id not in ENABLED_GROUPS:
            return False
        return True

    @staticmethod
    def contains_trigger(text):
        if not text: return False
        text = text.lower()
        return any(keyword in text for keyword in TRIGGER_KEYWORDS)

filters = MessageFilter()
