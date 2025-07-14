
import os
import asyncio
import logging
import webbrowser
import twitchio
from twitchio.ext import commands
from dotenv import load_dotenv

load_dotenv()

TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_BOT_ID = os.getenv('TWITCH_BOT_ID')
TWITCH_OWNER_ID = os.getenv('TWITCH_OWNER_ID')
TWITCH_CHANNEL = os.getenv('TWITCH_CHANNEL')

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Bot")

class Bot(commands.AutoBot):
    def __init__(self):
        super().__init__(
            client_id=TWITCH_CLIENT_ID,
            client_secret=TWITCH_CLIENT_SECRET,
            bot_id=TWITCH_BOT_ID,
            owner_id=TWITCH_OWNER_ID,
            prefix="!",
            redirect_uri="http://localhost:4343/oauth",
            scopes=["user:read:chat", "user:write:chat", "user:bot", "moderator:read:chat_messages"],
        )

    async def event_ready(self):
        LOGGER.info(f"Bot is now ready. Username: {self.user.name or 'Unknown'}")
        if not self.tokens or len(self.tokens) == 0:
            LOGGER.info("No tokens found. Opening OAuth URL for authorization...")
            oauth_url = f"http://localhost:4343/oauth?scopes=user:read:chat%20user:write:chat%20user:bot&force_verify=true"
            print(f"\nPlease visit this URL to authorize the bot:\n{oauth_url}\n")
            try:
                webbrowser.open(oauth_url)
                LOGGER.info("OAuth URL opened in browser")
            except Exception as e:
                LOGGER.warning(f"Could not open browser automatically: {e}")
                print("Please manually open the URL above in your browser.")
        else:
            LOGGER.info(f"Existing tokens found for {len(self.tokens)} users, bot is ready to use")

    async def event_message(self, message: twitchio.ChatMessage):
        def dump_attrs(obj, indent=0, visited=None):
            if visited is None:
                visited = set()
            pad = '  ' * indent
            if id(obj) in visited:
                print(f"{pad}<circular reference>")
                return
            visited.add(id(obj))
            if isinstance(obj, dict):
                for k, v in obj.items():
                    print(f"{pad}{k}: {v}")
                    dump_attrs(v, indent + 1, visited)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    print(f"{pad}[{i}]: {item}")
                    dump_attrs(item, indent + 1, visited)
            elif hasattr(obj, "__dict__") or hasattr(obj, "__slots__"):
                for attr in dir(obj):
                    if not attr.startswith("_"):
                        try:
                            value = getattr(obj, attr)
                            print(f"{pad}{attr}: {value}")
                            if isinstance(value, (dict, list)) or hasattr(value, "__dict__"):
                                dump_attrs(value, indent + 1, visited)
                        except Exception as e:
                            print(f"{pad}{attr}: <error: {e}>")
        print("==== IRC Message Dump ====")
        dump_attrs(message)
        print("=========================")

async def main():
    import twitchio.utils
    twitchio.utils.setup_logging(level=logging.INFO)
    async with Bot() as bot:
        await bot.load_tokens()
        await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down due to KeyboardInterrupt")
