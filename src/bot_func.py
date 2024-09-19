from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
import os
import json
import traceback
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))

async def send(msg: Message, channel_id: str):
    try:
        # 检查权限
        user_id = msg.author_id
        guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
        guild_user = await guild.fetch_user(user_id)
        # 如果权限id不是管理员id或者文字频道管理员id就不行
        if os.getenv("ADMIN_ID") not in guild_user.roles and os.getenv("TEXT_CHANNEL_ADMIN_ID") not in guild_user.roles:
            return
        with open("CardMessage.json", "r") as f:
            CardMessage = json.load(f)
        channel = await bot.client.fetch_public_channel(channel_id)
        ret = await channel.send(CardMessage)
        print(f"ch.send | msg_id {ret['msg_id']}") # 方法1 发送消息的id
    except Exception as result:
        print(traceback.format_exc())

