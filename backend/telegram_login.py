"""Interactive Telegram login — run once to create the session file."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


async def main():
    from telethon import TelegramClient
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    channel = os.getenv("TELEGRAM_CHANNEL")

    print(f"Connecting with API ID: {api_id}, channel: {channel}")
    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_session")
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()

    me = await client.get_me()
    print(f"\nLogged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")
    print("Session saved to: telegram_session.session")

    print(f"\nFetching 3 messages from {channel} to verify access...")
    count = 0
    async for msg in client.iter_messages(channel, limit=3):
        text_preview = (msg.text or "[media/no text]")[:100]
        print(f"  [{msg.id}] {text_preview}")
        count += 1

    if count == 0:
        print("  (no messages found — check channel name)")
    else:
        print(f"\nSuccess! Channel is accessible. You can now run the sync.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
