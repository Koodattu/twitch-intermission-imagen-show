import os
import asyncio
import logging
import twitchio
from twitchio import eventsub
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

class MyComponent(commands.Component):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.command()
    async def hi(self, ctx: commands.Context):
        await ctx.reply(f"Hi {ctx.chatter}!")

class Bot(commands.AutoBot):
    def __init__(self):
        super().__init__(
            client_id=TWITCH_CLIENT_ID,
            client_secret=TWITCH_CLIENT_SECRET,
            bot_id=TWITCH_BOT_ID,
            owner_id=TWITCH_OWNER_ID,
            prefix="!",
            subscriptions=[eventsub.ChatMessageSubscription(broadcaster_user_id=TWITCH_BOT_ID, user_id=TWITCH_BOT_ID)],
        )

    async def setup_hook(self):
        await self.add_component(MyComponent(self))

    async def event_ready(self):
        print(f"Bot ready | Username: {self.nick}")
        await self.join_channels([TWITCH_CHANNEL])

    async def event_message(self, message):
        print(f"{message.author.name}: {message.content}")
        await self.handle_commands(message)

    async def event_chat_message(self, event):
        print(f"Chat message: {event.content} by {event.author.name}")

    async def event_error(self, error):
        print(f"Error: {error}")

async def main():
    async with Bot() as bot:
        await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.warning("Shutting down due to KeyboardInterrupt")
