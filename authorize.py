import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

async def main():
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    if not api_id or not api_hash:
        print("Error: API_ID or API_HASH not found in .env file")
        return

    api_id = int(api_id)
    
    # We use a fixed session name for the scanner
    session_name = 'scanner_session'
    client = TelegramClient(session_name, api_id, api_hash)

    print(f"Connecting to Telegram for session: {session_name}...")
    await client.start()
    
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Successfully authorized as: {me.first_name} (@{me.username})")
        print(f"Session file '{session_name}.session' is ready.")
    else:
        print("Failed to authorize.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
