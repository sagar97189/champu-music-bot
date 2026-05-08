from pytgcalls.types import MediaStream

try:
    m = MediaStream("test", video_flags=MediaStream.Flags.IGNORE)
    print("MediaStream with video_flags=IGNORE works")
except Exception as e:
    print(f"Error: {e}")
