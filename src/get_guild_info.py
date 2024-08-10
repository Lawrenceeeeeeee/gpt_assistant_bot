import os
from dotenv import load_dotenv
import asyncio

from rate_limit import get_rate_limit

from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild

load_dotenv()

## websocket
bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))


async def get_guild_users():
    guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
    members = await guild.fetch_user_list()
    return members

async def main():
    members = await get_guild_users()
    for member in members:
        print(member.id)
        get_rate_limit(member.id)

if __name__ == "__main__":
    asyncio.run(main())


