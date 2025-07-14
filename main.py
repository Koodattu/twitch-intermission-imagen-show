import os
import asyncio
import logging
import webbrowser
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
            redirect_uri="http://localhost:4343/oauth",
            scopes=["user:read:chat", "user:write:chat", "user:bot", "channel:read:redemptions"],
        )

    async def setup_hook(self):
        await self.add_component(MyComponent(self))

    async def setup_eventsub_subscriptions(self):
        """Set up EventSub subscriptions for the target channel"""
        # Get the target channel user ID (the channel we want to monitor)
        target_channel_id = None
        if TWITCH_CHANNEL:
            try:
                # Fetch user info for the target channel
                users = await self.fetch_users(logins=[TWITCH_CHANNEL])
                if users:
                    target_channel_id = users[0].id
                    LOGGER.info(f"Target channel '{TWITCH_CHANNEL}' has user ID: {target_channel_id}")
                else:
                    LOGGER.error(f"Could not find user ID for channel: {TWITCH_CHANNEL}")
                    return
            except Exception as e:
                LOGGER.error(f"Error fetching user ID for {TWITCH_CHANNEL}: {e}")
                return
        else:
            # If no specific channel is configured, use the bot's own channel
            # Note: For AutoBot, we need to get the owner's ID
            target_channel_id = self.owner_id
            LOGGER.info(f"No TWITCH_CHANNEL configured, using owner's channel: {target_channel_id}")

        # Subscribe to events for the target channel
        if target_channel_id:
            subs = [
                # Chat messages for the target channel
                eventsub.ChatMessageSubscription(broadcaster_user_id=target_channel_id, user_id=self.bot_id),
                # Channel points events for the target channel
                eventsub.ChannelPointsRedeemAddSubscription(broadcaster_user_id=target_channel_id),
            ]

            try:
                LOGGER.info(f"Attempting to subscribe to EventSub events for channel {target_channel_id}")
                resp = await self.multi_subscribe(subs)
                if resp.errors:
                    LOGGER.warning(f"Failed to subscribe to some events: {resp.errors}")
                    for success in resp.success:
                        LOGGER.info(f"Successfully subscribed to: {success.subscription.type}")
                else:
                    LOGGER.info(f"Successfully subscribed to all {len(subs)} events for channel {target_channel_id}")
                    for sub in subs:
                        LOGGER.info(f"  - {sub.__class__.__name__}")
            except Exception as e:
                LOGGER.error(f"Error subscribing to events: {e}")
                import traceback
                LOGGER.error(f"Traceback: {traceback.format_exc()}")

    async def event_oauth_authorized(self, payload: twitchio.authentication.UserTokenPayload):
        """Event called when OAuth authorization completes successfully."""
        await self.add_token(payload.access_token, payload.refresh_token)
        LOGGER.info(f"OAuth authorized for user: {payload.user_id}")
        # Set up EventSub subscriptions after authorization
        await self.setup_eventsub_subscriptions()

    async def event_ready(self):
        LOGGER.info(f"Bot is now ready. Username: {self.user.name or 'Unknown'}")

        # Check if we have any tokens stored
        if not self.tokens or len(self.tokens) == 0:
            LOGGER.info("No tokens found. Opening OAuth URL for authorization...")
            oauth_url = f"http://localhost:4343/oauth?scopes=user:read:chat%20user:write:chat%20user:bot%20channel:read:redemptions&force_verify=true"
            print(f"\nPlease visit this URL to authorize the bot:\n{oauth_url}\n")
            try:
                webbrowser.open(oauth_url)
                LOGGER.info("OAuth URL opened in browser")
            except Exception as e:
                LOGGER.warning(f"Could not open browser automatically: {e}")
                print("Please manually open the URL above in your browser.")
        else:
            LOGGER.info(f"Existing tokens found for {len(self.tokens)} users, bot is ready to use")
            # Set up EventSub subscriptions since we already have tokens
            await self.setup_eventsub_subscriptions()

        if TWITCH_CHANNEL:
            LOGGER.info(f"Bot will monitor channel: {TWITCH_CHANNEL} via EventSub subscriptions")
        else:
            LOGGER.info("No TWITCH_CHANNEL configured - will monitor owner's channel")

    async def event_message(self, message: twitchio.ChatMessage):
        """IRC-style message event - handles regular chat messages via IRC"""
        print(f"IRC Message: {message.chatter.name}: {message.text}")
        return

    async def event_error(self, error: twitchio.EventErrorPayload):
        print(f"Error occurred: {error.error}")
        return

    async def event_custom_redemption_add(self, payload: twitchio.ChannelPointsRedemptionAdd):
        """EventSub channel points redemption event"""
        print(f"🎁 Channel points redeemed: {payload.reward.title} by {payload.user.display_name}")
        if payload.user_input:
            print(f"   User input: {payload.user_input}")
        return

    async def event_eventsub_notification_received(self, payload):
        """Debug handler for all EventSub notifications"""
        print(f"📡 EventSub notification received: {type(payload).__name__}")
        return

async def main():
    twitchio.utils.setup_logging(level=logging.INFO)

    async with Bot() as bot:
        # Load any existing tokens from the default file
        await bot.load_tokens()
        await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.warning("Shutting down due to KeyboardInterrupt")
