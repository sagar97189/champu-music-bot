import aiosqlite
import json
import time
from datetime import datetime

class SQLiteMemory:
    def __init__(self, db_path="memory/chat_memory.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    sender_id INTEGER,
                    username TEXT,
                    text TEXT,
                    timestamp DATETIME
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cooldowns (
                    chat_id INTEGER PRIMARY KEY,
                    last_reply_time REAL
                )
            """)
            await db.commit()

    async def save_message(self, chat_id, sender_id, username, text):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (chat_id, sender_id, username, text, timestamp) VALUES (?, ?, ?, ?, ?)",
                (chat_id, sender_id, username, text, datetime.now())
            )
            await db.commit()

    async def get_recent_context(self, chat_id, limit=15):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT username, text FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?",
                (chat_id, limit)
            )
            rows = await cursor.fetchall()
            return [{"sender": r[0], "text": r[1]} for r in reversed(rows)]

    async def get_last_reply_time(self, chat_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT last_reply_time FROM cooldowns WHERE chat_id = ?", (chat_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def mark_replied(self, chat_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cooldowns (chat_id, last_reply_time) VALUES (?, ?)",
                (chat_id, time.time())
            )
            await db.commit()

db_memory = SQLiteMemory()
