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

class Bot(commands.AutoBot):
    def __init__(self):
        super().__init__(
            client_id=TWITCH_CLIENT_ID,
            client_secret=TWITCH_CLIENT_SECRET,
            bot_id=TWITCH_BOT_ID,
            owner_id=TWITCH_OWNER_ID,
            prefix="!",
            redirect_uri="http://localhost:4343/oauth",
            scopes=["user:read:chat", "user:write:chat", "user:bot", "channel:read:redemptions", "moderator:read:chat_messages"],
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
            LOGGER.info(f"No TWITCH_CHANNEL configured, using owner's channel: {target_channel_id}")        # Check if we have a token for the target channel owner
        channel_token = None
        if self.tokens:
            for token_id, token in self.tokens.items():
                if token_id == str(target_channel_id):
                    channel_token = token
                    break

        if not channel_token:
            LOGGER.warning(f"⚠️  No token found for channel owner (ID: {target_channel_id})")
            LOGGER.warning("   Channel points redemptions will likely fail with 403 Forbidden")
            LOGGER.warning("   The channel owner needs to authorize this bot!")        # First, let's check existing subscriptions
        try:
            LOGGER.info("🔍 Checking existing EventSub subscriptions...")
            existing_subs = await self.fetch_eventsub_subscriptions()
            # Handle the EventsubSubscriptions object properly
            if hasattr(existing_subs, '__iter__'):
                subs_list = list(existing_subs)
            else:
                subs_list = []
                LOGGER.warning(f"Cannot iterate over subscriptions object: {type(existing_subs)}")

            LOGGER.info(f"Found {len(subs_list)} existing subscriptions")
            for i, sub in enumerate(subs_list):
                LOGGER.info(f"  {i+1}. {sub.type} (status: {sub.status}, id: {sub.id})")

            # If we can't see subscriptions but get 409 conflicts, try to delete all subscriptions
            if len(subs_list) == 0:
                LOGGER.info("🗑️ No subscriptions visible but conflicts exist - attempting to delete all subscriptions")
                try:
                    # This should delete all EventSub subscriptions for our client
                    await self.delete_eventsub_subscriptions()
                    LOGGER.info("✅ Deleted all EventSub subscriptions")
                except Exception as delete_error:
                    LOGGER.warning(f"Could not delete all subscriptions: {delete_error}")

        except Exception as e:
            LOGGER.error(f"Error fetching existing subscriptions: {e}")
            subs_list = []

        # Subscribe to events for the target channel
        if target_channel_id:
            # Try to clean up existing subscriptions that might conflict
            try:
                LOGGER.info("🧹 Attempting to clean up conflicting subscriptions...")
                for sub in subs_list:
                    if sub.type == 'channel.chat.message' and hasattr(sub, 'condition'):
                        condition_broadcaster = sub.condition.get('broadcaster_user_id') if isinstance(sub.condition, dict) else getattr(sub.condition, 'broadcaster_user_id', None)
                        if str(condition_broadcaster) == str(target_channel_id):
                            LOGGER.info(f"Found existing chat subscription: {sub.id}, deleting it...")
                            await self.delete_eventsub_subscription(sub.id)
                            LOGGER.info("✅ Deleted existing chat subscription")
                            break
            except Exception as e:
                LOGGER.warning(f"Could not clean up existing subscriptions: {e}")

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
                    LOGGER.warning(f"Failed to subscribe to some events:")
                    has_conflicts = False
                    for error in resp.errors:
                        LOGGER.warning(f"  - {error.subscription.__class__.__name__}: {error.error}")
                        if "409" in str(error.error):
                            has_conflicts = True
                            LOGGER.warning(f"❌ Subscription conflict: {error.subscription.__class__.__name__}")
                        elif "403" in str(error.error) and "ChannelPoints" in error.subscription.__class__.__name__:
                            LOGGER.error("❌ Channel Points subscription failed with 403 Forbidden!")
                            LOGGER.error("   This means the bot needs to be authorized by the channel owner.")
                            LOGGER.error("   Make sure the channel owner has authorized this bot with channel:read:redemptions scope.")

                    # If we have conflicts, try the nuclear option: delete all and retry
                    if has_conflicts:
                        LOGGER.info("🧨 Trying nuclear option: delete all subscriptions and retry...")
                        try:
                            await self.delete_eventsub_subscriptions()
                            LOGGER.info("✅ Deleted all subscriptions, retrying...")

                            # Wait a moment for deletion to propagate
                            await asyncio.sleep(2)

                            # Retry subscription
                            resp2 = await self.multi_subscribe(subs)
                            if resp2.errors:
                                LOGGER.error("❌ Still failed after cleanup:")
                                for error in resp2.errors:
                                    LOGGER.error(f"  - {error.subscription.__class__.__name__}: {error.error}")
                            else:
                                LOGGER.info("🎉 SUCCESS! All subscriptions created after cleanup!")
                                for sub in subs:
                                    LOGGER.info(f"  ✅ {sub.__class__.__name__}")
                        except Exception as cleanup_error:
                            LOGGER.error(f"Nuclear cleanup failed: {cleanup_error}")

                    for success in resp.success:
                        LOGGER.info(f"✅ Successfully subscribed to: {success.subscription.type}")
                else:
                    LOGGER.info(f"✅ Successfully subscribed to all {len(subs)} events for channel {target_channel_id}")
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

    # Override ALL possible event methods to catch anything
    def __getattr__(self, name):
        if name.startswith('event_'):
            async def debug_handler(*args, **kwargs):
                print(f"🔥 CAUGHT EVENT: {name}")
                print(f"   Args: {[type(arg).__name__ for arg in args]}")

                # Special handling for specific events we care about
                if 'chat' in name.lower() and args:
                    print(f"💬 CHAT EVENT DETECTED!")
                    print(f"   Full args: {args}")
                    try:
                        payload = args[0]
                        if hasattr(payload, 'chatter_user_name') and hasattr(payload, 'message'):
                            print(f"   Chat: {payload.chatter_user_name}: {payload.message.text}")
                        elif hasattr(payload, 'event'):
                            event = payload.event
                            if hasattr(event, 'chatter_user_name') and hasattr(event, 'message'):
                                print(f"   Chat: {event.chatter_user_name}: {event.message.text}")
                    except Exception as e:
                        print(f"   Error parsing chat: {e}")

                elif 'point' in name.lower() and args:
                    print(f"🎁 CHANNEL POINTS EVENT DETECTED!")
                    print(f"   Full args: {args}")

                return
            return debug_handler
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    # Specific EventSub handlers
    async def event_eventsub_notification_channel_chat_message(self, data):
        """EventSub chat message handler - specific method"""
        print(f"💬 EventSub Chat (specific): Received chat message event")
        print(f"   Data type: {type(data)}")
        print(f"   Data: {data}")
        return

    async def event_eventsub_notification(self, payload):
        """Generic EventSub notification handler"""
        print(f"📡 EventSub notification (generic): {type(payload).__name__}")
        print(f"   Payload: {payload}")
        return

    async def on_eventsub_notification(self, payload):
        """Alternative EventSub handler name"""
        print(f"📡 EventSub (on_): {type(payload).__name__}")
        return

    async def eventsub_notification(self, payload):
        """Another alternative EventSub handler name"""
        print(f"📡 EventSub (direct): {type(payload).__name__}")
        return

    async def event_error(self, error):
        print(f"Error occurred: {error}")
        return

    async def event_custom_redemption_add(self, payload: twitchio.ChannelPointsRedemptionAdd):
        """EventSub channel points redemption event"""
        print(f"🎁 Channel points redeemed: {payload.reward.title} by {payload.user.display_name}")
        if payload.user_input:
            print(f"   User input: {payload.user_input}")
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
