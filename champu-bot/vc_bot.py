# 🚀 HOW TO DEPLOY ON JustRunMyApp:
# 1. Upload this file (vc_bot.py) and requirements.txt.
# 2. Add your API_ID, API_HASH, and SESSION_NAME to the environment variables in the hosting dashboard.
# 3. Ensure FFmpeg is installed on the host (usually pre-installed on JustRunMyApp).
# 4. Set the start command to: python vc_bot.py

import os
import sys

# Fix Windows terminal Unicode encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
import asyncio
import logging
import yt_dlp
import subprocess
import random
from dotenv import load_dotenv

# Load Environment Variables (.env)
load_dotenv()

# --- Monkeypatch Hydrogram Errors for PyTgCalls Compatibility ---
import hydrogram.errors
try:
    import hydrogram.errors.exceptions as hydrogram_error_exceptions
except Exception:
    hydrogram_error_exceptions = None

for error_module in filter(None, (hydrogram.errors, hydrogram_error_exceptions)):
    if not hasattr(error_module, "GroupcallInvalid") and hasattr(error_module, "GroupCallInvalid"):
        error_module.GroupcallInvalid = error_module.GroupCallInvalid
    if not hasattr(error_module, "GroupcallForbidden") and hasattr(error_module, "GroupCallForbidden"):
        error_module.GroupcallForbidden = error_module.GroupCallForbidden

# --- 1. Linux & Windows FFmpeg Fallback ---
# Standard Linux paths + your custom Windows path
FFMPEG_PATHS = [
    r"C:\Users\Admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin",
    "/usr/bin",
    "/usr/local/bin"
]
for path in FFMPEG_PATHS:
    if os.path.exists(path):
        os.environ["PATH"] += f"{os.pathsep}{path}"

from hydrogram import Client, filters, idle
from hydrogram.errors import FloodWait
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.exceptions import NoActiveGroupCall

# --- 2. Configuration (Loaded from Environment) ---
API_ID = int(os.getenv("API_ID", "31713839"))
API_HASH = os.getenv("API_HASH", "6fbf8b8296f9a798e1fe911e28a9a706")
SESSION_NAME = os.getenv("SESSION_NAME", "champu_server_session")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- CLI Target Chat ID ---
# Set this to the chat ID where you want terminal commands to play music.
# You can find a group's chat ID by forwarding a message to @userinfobot or from the bot logs.
# Can also be set via environment variable: CLI_CHAT_ID
CLI_CHAT_ID = int(os.getenv("CLI_CHAT_ID", "0"))
VOLUME_LOCK_ENABLED = os.getenv("VOLUME_LOCK_ENABLED", "1").lower() in ("1", "true", "yes", "on")
VOLUME_LOCK_LEVEL = max(1, min(int(os.getenv("VOLUME_LOCK_LEVEL", "200")), 200))
VOLUME_LOCK_INTERVAL = max(2, int(os.getenv("VOLUME_LOCK_INTERVAL", "10")))

# --- 2. Configuration (Loaded from Environment) ---
SILENT_AUDIO_SOURCE = "anullsrc=channel_layout=stereo:sample_rate=48000"
SILENT_AUDIO_FFMPEG_PARAMS = "--audio-start -f lavfi"

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Clients
assistant = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)
bot = Client("champu_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(assistant)

# 🧠 State Tracking
active_calls = {}
volume_lock_tasks = {}
volume_lock_levels = {}
# Track the service message ID for VC comments
active_vc_message_ids = {}

# 3. 🛠️ Optimized yt-dlp Options for Server Hosting
ydl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "web", "mweb", "tv"],
            "skip": ["dash", "hls"]
        }
    },
    "compat_opts": ["no-youtube-unavailable-videos"],
    "js_runtimes": {"node": {}},
    "remote_components": ["ejs:github"]
}


async def _set_call_volume(chat_id, volume):
    """Set the bot participant volume in a VC when PyTgCalls supports it."""
    volume = max(1, min(int(volume), 200))
    if hasattr(call_py, "change_volume_call"):
        await call_py.change_volume_call(chat_id, volume)
        return True
    if hasattr(call_py, "set_my_volume"):
        await call_py.set_my_volume(volume)
        return True
    logger.warning("This PyTgCalls version does not expose VC volume control.")
    return False


async def _volume_lock_loop(chat_id):
    while active_calls.get(chat_id):
        volume = volume_lock_levels.get(chat_id, VOLUME_LOCK_LEVEL)
        try:
            await _set_call_volume(chat_id, volume)
        except Exception as e:
            logger.warning(f"Volume lock failed for {chat_id}: {e}")
        await asyncio.sleep(VOLUME_LOCK_INTERVAL)


async def _start_volume_lock(chat_id, volume=None):
    volume = max(1, min(int(volume or VOLUME_LOCK_LEVEL), 200))
    volume_lock_levels[chat_id] = volume

    task = volume_lock_tasks.get(chat_id)
    if task and not task.done():
        task.cancel()

    try:
        await _set_call_volume(chat_id, volume)
    except Exception as e:
        logger.warning(f"Initial volume lock failed for {chat_id}: {e}")

    volume_lock_tasks[chat_id] = asyncio.create_task(_volume_lock_loop(chat_id))


def _stop_volume_lock(chat_id):
    task = volume_lock_tasks.pop(chat_id, None)
    if task and not task.done():
        task.cancel()
    volume_lock_levels.pop(chat_id, None)


async def _find_vc_service_message(chat_id):
    """Finds the 'Voice Chat Started' service message to reply to."""
    try:
        async for message in assistant.get_chat_history(chat_id, limit=100):
            if message.service:
                # Check for Video Chat / Group Call start messages
                if (getattr(message, "video_chat_started", None) or 
                    getattr(message, "group_call_started", None) or
                    getattr(message, "video_chat_scheduled", None)):
                    return message.id
                
                # Broad fallback check
                msg_str = str(message).lower()
                if "video_chat" in msg_str or "group_call" in msg_str:
                    return message.id
    except Exception as e:
        logger.warning(f"Error finding VC message: {e}")
    return None

# --- Shared Play Logic (used by both Telegram commands and CLI) ---
async def _play_song(chat_id, query, reply_func=None):
    """
    Core play logic. Searches YouTube, joins/switches VC stream.
    reply_func: an async callable(text) to send status messages. If None, prints to console.
    """
    async def send(text, cli_text=None):
        if reply_func:
            await reply_func(text)
        else:
            print(cli_text or text)

    await send(f"\U0001f50e Searching: `{query}`...", f"[*] Searching: {query}...")

    try:
        def get_stream(attempt=1):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                    if not info or not info.get('entries'):
                        return None
                    video = info['entries'][0]
                    return {
                        "url": video.get("url") or video["formats"][0].get("url"),
                        "title": video.get("title", "Unknown Title")
                    }
            except Exception as e:
                if attempt == 1:
                    return get_stream(attempt=2)
                return None

        result = await asyncio.to_thread(get_stream)
        if not result or not result["url"]:
            await send("Source unavailable.", "[!] Source unavailable.")
            return

        stream_url = result["url"]
        title = result["title"]

        # Stream Logic (Join Once, Switch Often)
        if active_calls.get(chat_id):
            logger.info(f"Switching stream: {title}")
            await call_py.play(chat_id, MediaStream(stream_url, video_flags=MediaStream.Flags.IGNORE))
        else:
            logger.info(f"Joining VC: {title}")
            try:
                await call_py.play(chat_id, MediaStream(stream_url, video_flags=MediaStream.Flags.IGNORE))
                active_calls[chat_id] = True
            except FloodWait as e:
                logger.warning(f"FloodWait: Waiting {e.value}s")
                await asyncio.sleep(e.value)
                await call_py.play(chat_id, MediaStream(stream_url, video_flags=MediaStream.Flags.IGNORE))
                active_calls[chat_id] = True

        if VOLUME_LOCK_ENABLED:
            await _start_volume_lock(chat_id)

        await send(f"Now Playing: {title}", f"[>] Now Playing: {title}")

    except Exception as e:
        logger.error(f"Play Error: {e}")
        await send(f"Play Error: {e}", f"[X] Play Error: {e}")


async def _stop_song(chat_id, reply_func=None):
    """Core stop logic."""
    async def send(text):
        if reply_func:
            await reply_func(text)
        else:
            print(text)

    try:
        await call_py.leave_call(chat_id)
        active_calls[chat_id] = False
        _stop_volume_lock(chat_id)
        await send("Stopped and left VC.", "[*] Stopped and left VC.")
    except Exception:
        await send("Not playing.", "[!] Not playing.")


async def _join_voice_chat(chat_id, reply_func=None):
    """Join/start a group voice chat by streaming silence."""
    async def send(text, cli_text=None):
        if reply_func:
            await reply_func(text)
        else:
            print(cli_text or text)

    if active_calls.get(chat_id):
        await send("Already in VC.", "[*] Already in VC.")
        return

    try:
        await call_py.play(
            chat_id,
            MediaStream(
                SILENT_AUDIO_SOURCE,
                audio_flags=MediaStream.Flags.REQUIRED,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=SILENT_AUDIO_FFMPEG_PARAMS,
            ),
        )
        active_calls[chat_id] = True
        if VOLUME_LOCK_ENABLED:
            await _start_volume_lock(chat_id)
        await send("Joined VC silently.", "[*] Joined VC silently.")
    except FloodWait as e:
        logger.warning(f"FloodWait: Waiting {e.value}s")
        await asyncio.sleep(e.value)
        await _join_voice_chat(chat_id, reply_func=reply_func)
    except Exception as e:
        await send(f"Could not join VC: {e}", f"[X] Could not join VC: {e}")


async def _end_voice_chat(chat_id, reply_func=None):
    """Close the group voice chat if this account has permission."""
    async def send(text, cli_text=None):
        if reply_func:
            await reply_func(text)
        else:
            print(cli_text or text)

    try:
        await call_py.leave_call(chat_id, close=True)
        active_calls[chat_id] = False
        _stop_volume_lock(chat_id)
        await send("Voice chat ended.", "[*] Voice chat ended.")
    except Exception as e:
        await send(f"Could not end voice chat: {e}", f"[X] Could not end voice chat: {e}")


async def _send_chat_message(chat_id, text, reply_func=None):
    """Send a text message to the target group from the terminal/controller."""
    async def send(text_to_send, cli_text=None):
        if reply_func:
            await reply_func(text_to_send)
        else:
            print(cli_text or text_to_send)

    text = text.strip()
    if not text:
        await send("Message is empty.", "[X] Message is empty.")
        return

    try:
        await assistant.send_message(chat_id, text)
        await send("Message sent.", "[OK] Message sent.")
    except Exception as e:
        await send(f"Could not send message: {e}", f"[X] Could not send message: {e}")


async def _join_group(link, reply_func=None):
    """Join a group using an invite link."""
    async def send(text, cli_text=None):
        if reply_func:
            await reply_func(text)
        else:
            print(cli_text or text)

    link = link.strip()
    if not link:
        await send("Link is empty.", "[X] Link is empty.")
        return

    try:
        chat = await assistant.join_chat(link)
        await send(f"Joined group: {chat.title} ({chat.id})", f"[OK] Joined group: {chat.title} ({chat.id})")
    except Exception as e:
        await send(f"Could not join group: {e}", f"[X] Could not join group: {e}")


@assistant.on_message(filters.command(["play", "p"]) & filters.group)
async def play_handler(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/play <song name or URL>`")
        return
    query = " ".join(message.command[1:])
    await _play_song(message.chat.id, query, reply_func=message.reply_text)

@assistant.on_message(filters.command(["stop", "leave"]) & filters.group)
async def stop_handler(client, message):
    await _stop_song(message.chat.id, reply_func=message.reply_text)

@assistant.on_message(filters.command("joinvc") & filters.group)
async def joinvc_handler(client, message):
    await _join_voice_chat(message.chat.id, reply_func=message.reply_text)

@assistant.on_message(filters.command("endvc") & filters.group)
async def endvc_handler(client, message):
    await _end_voice_chat(message.chat.id, reply_func=message.reply_text)

@assistant.on_message(filters.command("join") & (filters.group | filters.private))
async def join_group_handler(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/join <invite link>`")
        return
    link = message.command[1]
    await _join_group(link, reply_func=message.reply_text)

@assistant.on_message(filters.command("bothelp") & (filters.group | filters.private))
async def help_handler(client, message):
    help_text = (
        "🎵 **Assistant Bot Commands**\n\n"
        "▶️ `/play <name>` - Play music in VC\n"
        "⏹️ `/stop` - Stop music & leave VC\n"
        "🎙️ `/joinvc` - Join VC silently\n"
        "🚪 `/endvc` - End the VC session\n"
        "🔗 `/join <link>` - Join a new group\n"
        "🆔 `/chatid` - Get current chat ID"
    )
    await message.reply_text(help_text)


# --- 🤖 BOT ACCOUNT HANDLERS (@ChampuMusicBot) ---

@bot.on_message(filters.command(["play", "p"]) & filters.group)
async def bot_play_handler(client, message):
    print(f"[BOT] Received /play from {message.from_user.first_name if message.from_user else 'User'}")
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/play <song name or URL>`")
        return
    query = " ".join(message.command[1:])
    
    # 1. Check if Assistant is in the group
    try:
        me_assistant = await assistant.get_me()
        await client.get_chat_member(chat_id, me_assistant.id)
    except Exception:
        # Assistant not in group, attempt to join
        await message.reply_text("🔄 **Assistant is not here.** Joining group...")
        try:
            # Try to get an invite link (requires bot to be admin)
            invite_link = await client.export_chat_invite_link(chat_id)
            await assistant.join_chat(invite_link)
        except Exception:
            # Fallback for public groups
            if message.chat.username:
                try:
                    await assistant.join_chat(message.chat.username)
                except Exception as e:
                    await message.reply_text(f"❌ **Assistant couldn't join.**\nMake me admin or send an invite link to the assistant.\nError: {e}")
                    return
            else:
                await message.reply_text("❌ **Assistant couldn't join.**\nMake me admin (to create invite link) or add the assistant manually.")
                return

    # 2. Trigger Play Song via Assistant logic
    await _play_song(chat_id, query, reply_func=message.reply_text)

@bot.on_message(filters.command(["stop", "leave", "endvc"]) & filters.group)
async def bot_stop_handler(client, message):
    print(f"[BOT] Received /stop")
    await _stop_song(message.chat.id, reply_func=message.reply_text)

@bot.on_message(filters.command("bothelp") & (filters.group | filters.private))
async def bot_help_handler(client, message):
    help_text = (
        "🎵 **@ChampuMusicBot Commands**\n\n"
        "▶️ `/play <name>` - Play music in Voice Chat\n"
        "⏹️ `/stop` - Stop music & leave VC\n"
        "📚 `/bothelp` - Show this menu\n\n"
        "💡 *Note: I will automatically invite my Assistant account if it's not in the group.*"
    )
    await message.reply_text(help_text)


async def cli_listener():
    """
    Reads commands from your terminal (stdin) and triggers play/stop in Telegram VC.
    
    Supported terminal commands:
        play <song name or URL>    - Play a song in the target group's VC
        joinvc                     - Join/start VC without playing a song
        stop                       - Stop playback and leave VC
        endvc                      - End/close the group voice chat
        msg <text>                 - Send a message to the target group
        volume <1-200>             - Set the bot VC volume
        volumelock on [1-200]      - Keep forcing the bot VC volume up
        volumelock off             - Disable volume lock for the target chat
        setchat <chat_id>          - Change the target chat at runtime
        join <link>                - Join a group using an invite link
        help                       - Show available commands
        exit / quit                - Stop the bot
    """
    global CLI_CHAT_ID

    print()
    print("=" * 50)
    print("  TERMINAL MUSIC CONTROLLER READY")
    print("=" * 50)
    if CLI_CHAT_ID:
        print(f"  Target Chat ID: {CLI_CHAT_ID}")
    else:
        print("  [!] No CLI_CHAT_ID set!")
        print("  Use 'setchat <id>' or set CLI_CHAT_ID in .env")
    print()
    print("  Commands:")
    print("    play <song name>  - Play song in Telegram VC")
    print("    joinvc            - Join/start VC silently")
    print("    stop              - Stop playback")
    print("    endvc             - End/close the group VC")
    print("    msg <text>        - Send message to group chat")
    print("    volume <1-200>    - Set VC volume")
    print("    volumelock on 200 - Keep VC volume boosted")
    print("    volumelock off    - Disable volume lock")
    print("    setchat <id>      - Set target group chat ID")
    print("    join <link>       - Join group via link")
    print("    np                - Now playing info")
    print("    help              - Show this help")
    print("    exit              - Shutdown bot")
    print("=" * 50)
    print()

    loop = asyncio.get_event_loop()

    while True:
        try:
            # Read input from terminal without blocking the event loop
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                # EOF reached (e.g., piped input ended)
                continue
            
            line = line.strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            cmd = parts[0].lower().lstrip("/")

            if cmd == "play":
                if len(parts) < 2:
                    print("[X] Usage: play <song name or YouTube URL>")
                    continue
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                query = parts[1]
                # Run play in background so CLI stays responsive
                asyncio.create_task(_play_song(CLI_CHAT_ID, query))

            elif cmd == "joinvc":
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                asyncio.create_task(_join_voice_chat(CLI_CHAT_ID))

            elif cmd == "stop":
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                asyncio.create_task(_stop_song(CLI_CHAT_ID))

            elif cmd == "endvc":
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                asyncio.create_task(_end_voice_chat(CLI_CHAT_ID))

            elif cmd in ("msg", "chat", "comment"):
                if len(parts) < 2:
                    print("[X] Usage: msg <text>")
                    continue
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                asyncio.create_task(_send_chat_message(CLI_CHAT_ID, parts[1]))

            elif cmd in ("volume", "vol"):
                if len(parts) < 2:
                    print("[X] Usage: volume <1-200>")
                    continue
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                try:
                    volume = max(1, min(int(parts[1]), 200))
                    volume_lock_levels[CLI_CHAT_ID] = volume
                    asyncio.create_task(_set_call_volume(CLI_CHAT_ID, volume))
                    print(f"[OK] Volume set to {volume}")
                except ValueError:
                    print("[X] Volume must be a number from 1 to 200")

            elif cmd == "volumelock":
                if not CLI_CHAT_ID:
                    print("[X] No target chat set! Use: setchat <chat_id>")
                    continue
                args = parts[1].split() if len(parts) > 1 else ["on"]
                action = args[0].lower()
                if action in ("off", "stop", "disable"):
                    _stop_volume_lock(CLI_CHAT_ID)
                    print("[OK] Volume lock off")
                    continue
                try:
                    volume = int(args[1]) if len(args) > 1 else VOLUME_LOCK_LEVEL
                    asyncio.create_task(_start_volume_lock(CLI_CHAT_ID, volume))
                    print(f"[OK] Volume lock on at {max(1, min(volume, 200))}")
                except ValueError:
                    print("[X] Usage: volumelock on <1-200> or volumelock off")

            elif cmd == "setchat":
                if len(parts) < 2:
                    print("[X] Usage: setchat <chat_id>")
                    continue
                try:
                    CLI_CHAT_ID = int(parts[1])
                    print(f"[OK] Target chat set to: {CLI_CHAT_ID}")
                except ValueError:
                    print("[X] Invalid chat ID. Must be a number (e.g., -1001234567890)")

            elif cmd == "join":
                if len(parts) < 2:
                    print("[X] Usage: join <link>")
                    continue
                link = parts[1]
                asyncio.create_task(_join_group(link))

            elif cmd == "np":
                if not CLI_CHAT_ID:
                    print("No target chat set.")
                elif active_calls.get(CLI_CHAT_ID):
                    print(f"[>] Active stream in chat: {CLI_CHAT_ID}")
                else:
                    print("[*] Nothing playing.")

            elif cmd == "help":
                print("\nAvailable Commands:")
                print("  play <song>    - Play a song in Telegram VC")
                print("  joinvc         - Join/start VC without playing a song")
                print("  stop           - Stop playback and leave VC")
                print("  endvc          - End/close the group voice chat")
                print("  msg <text>     - Send a message to the target group")
                print("  volume <1-200> - Set bot VC volume")
                print("  volumelock on [1-200] - Keep forcing bot VC volume")
                print("  volumelock off - Disable volume lock")
                print("  setchat <id>   - Set target group chat ID")
                print("  join <link>    - Join group via invite link")
                print("  np             - Now playing status")
                print("  exit / quit    - Shutdown bot\n")

            elif cmd in ("exit", "quit"):
                print("Shutting down...")
                # Gracefully leave any active calls
                for cid in list(active_calls.keys()):
                    if active_calls[cid]:
                        try:
                            _stop_volume_lock(cid)
                            _stop_autochat(cid)
                            await call_py.leave_call(cid)
                        except Exception:
                            pass
                os._exit(0)

            else:
                print(f"[?] Unknown command: '{cmd}'. Type 'help' for available commands.")

        except Exception as e:
            logger.error(f"CLI Error: {e}")


# --- Auto-detect chat ID helper ---
@assistant.on_message(filters.command("chatid") & filters.group)
async def chatid_handler(client, message):
    """Send /chatid in a group to get its chat ID for CLI usage."""
    chat_id = message.chat.id
    await message.reply_text(
        f"📋 **Chat ID:** `{chat_id}`\n\n"
        f"Use this in your terminal:\n`setchat {chat_id}`\n\n"
        f"Or add to your `.env`:\n`CLI_CHAT_ID={chat_id}`"
    )


async def main():
    print("-" * 40)
    print("Bot starting...")
    
    # Verify Node.js
    try:
        node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
        print(f"Node.js detected: {node_v}")
    except Exception:
        print("WARNING: Node.js not detected.")

    await assistant.start()
    await bot.start()
    await call_py.start()
    
    print(f"Assistant connected: {(await assistant.get_me()).first_name}")
    print(f"Bot connected: {(await bot.get_me()).first_name}")
    print("Ready for commands")
    print("-" * 40)

    # Start the CLI listener as a background task
    asyncio.create_task(cli_listener())

    # Use hydrogram's idle to keep the dispatcher alive
    await idle()
    
    await assistant.stop()
    await bot.stop()

if __name__ == "__main__":
    # Clean Entry Point
    # Use loop.run_until_complete instead of app.run(main()) since we have two clients
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
