import asyncio
import os
import twitchio
from dotenv import load_dotenv

load_dotenv()

TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')

async def main() -> None:
    async with twitchio.Client(client_id=TWITCH_CLIENT_ID, client_secret=TWITCH_CLIENT_SECRET) as client:
        await client.login()
        user = await client.fetch_users(logins=["vaarattu", "vaarabot"])
        for u in user:
            print(f"User: {u.name} - ID: {u.id}")

if __name__ == "__main__":
    asyncio.run(main())