import asyncio
import os
import sys
from telethon import TelegramClient
from config.settings import API_ID, API_HASH, PHONE_NUMBER
from handlers.message_handler import register_handlers
from ai.local_ai import local_ai
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from datetime import datetime

console = Console()

class Dashboard:
    def __init__(self):
        self.start_time = datetime.now()
        self.status = "Initializing..."
        self.ollama_status = "Checking..."
        self.account = "N/A"
        self.total_sent = 0
        self.logs = []

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")
        if len(self.logs) > 10: self.logs.pop(0)

    def generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        layout["header"].update(Panel(f"Ollama Telegram Agent | Account: {self.account}", style="bold green"))
        
        # Stats Table
        table = Table(show_header=False, box=None)
        table.add_row("Uptime", str(datetime.now() - self.start_time).split(".")[0])
        table.add_row("Ollama Model", f"[bold cyan]{local_ai.model_name}[/bold cyan]")
        table.add_row("Ollama Status", self.ollama_status)
        table.add_row("Total Replies", str(self.total_sent))
        
        # Log Panel
        log_panel = Panel("\n".join(self.logs), title="Live Logs", border_style="blue")
        
        layout["main"].split_row(
            Layout(Panel(table, title="System Stats", border_style="white")),
            Layout(log_panel)
        )
        layout["footer"].update(Panel("Press Ctrl+C to shutdown safely", style="dim white"))
        return layout

async def check_ollama():
    """Verify Ollama is running and model exists."""
    if await local_ai.verify_model():
        return "[bold green]Online & Ready[/bold green]"
    else:
        return "[bold red]Model Not Found (Run: ollama pull mistral)[/bold red]"

async def main():
    if not API_ID or not API_HASH:
        console.print("[red]Error: API_ID/HASH missing in .env[/red]")
        return

    db = Dashboard()
    client = TelegramClient('ai_agent_session', API_ID, API_HASH)

    try:
        # 1. Start Ollama Check
        db.ollama_status = await check_ollama()
        
        # 2. Start Telegram
        db.status = "Connecting to Telegram..."
        await client.start(phone=PHONE_NUMBER)
        
        me = await client.get_me()
        db.account = f"{me.first_name} (@{me.username})"
        db.log(f"Logged in as {me.first_name}")

        # 3. Register Handlers
        handler = register_handlers(client)
        await handler.init()
        db.status = "Running"

        with Live(db.generate_layout(), refresh_per_second=2) as live:
            while True:
                from services.limiter import limiter
                db.total_sent = len(limiter.daily_messages)
                live.update(db.generate_layout())
                await asyncio.sleep(1)

    except Exception as e:
        console.print(f"[bold red]Startup Error: {e}[/bold red]")
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
