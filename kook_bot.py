import os
from dotenv import load_dotenv
import json
import traceback
import asyncio
import random

from src import email_verif as ev
from src import commands, chatbot_reply, msg_const
from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
from khl.card import Card, CardMessage, Module, Types, Element, Struct

load_dotenv()

## websocket
bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))

@bot.on_message()
async def on_message(msg: Message):  # when `name` is not set, the function name will be used

    bot_info = await bot.client.fetch_me()
    bot_id = bot_info.id
    
    channel_id = msg._ctx.channel._id if isinstance(msg, PublicMessage) else msg._ctx.channel.id
    author_id = msg.author_id
    author_nickname = msg.extra['author']['nickname']
    is_bot = msg.extra['author']['bot']
    
    mentioned_ids = [mention['id'] for mention in msg.extra['kmarkdown']['mention_part']]
    mentioned = True if bot_id in mentioned_ids else False
    
    async def reply_decision():
        guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
        guild_user = await guild.fetch_user(author_id)
        if isinstance(msg,PrivateMessage) and guild_user.roles:
            if msg.extra['kmarkdown']['raw_content'][0] != "/":
                return True
            else:
                return False
        else:
            if mentioned and not is_bot and guild_user.roles: return True
            else: return False
    
    try:
        content = json.loads(msg.content)
    except Exception as e:
        content = msg.content
    
    if await reply_decision():
        response = await chatbot_reply(content, channel_id, author_id, author_nickname)
        await msg.reply(response, mention_author=False)

@bot.on_event(EventTypes.JOINED_GUILD)
async def join_guild_send_event(b: Bot, e: Event):
    try:
        print("user join guild", e.body)  # 用户加入了服务器
        ch = await bot.client.fetch_public_channel(os.getenv("ENTRANCE_ID"))  # 获取指定文字频道的对象
        ret = await ch.send(f"欢迎入群，(met){e.body['user_id']}(met)！现在你应该只能看到“欢迎”分组。请先查看私信，获取身份组，然后就可以在服务器内畅谈了~\n\
为了方便及时收到最新消息, 请务必开启kook通知权限, 并在kook中“我的”-“通知设置”中设置“手机始终接收通知”。")
        print(f"ch.send | msg_id {ret['msg_id']}") # 方法1 发送消息的id

        user = await bot.client.fetch_user(e.body['user_id'])
        welcome_msg = msg_const.WELCOME_MSG
        await user.send(welcome_msg, type=MessageTypes.CARD)  # 发送私聊
    except Exception as result:
        print(traceback.format_exc())  # 打印报错详细信息

@bot.on_event(EventTypes.EXITED_GUILD)
async def exit_guild_send_event(b: Bot, e: Event):
    try:
        ev.delete_user(e.body['user_id'])
        print("user exit guild", e.body)  # 用户退出了服务器
    except Exception as result:
        print(traceback.format_exc())

@bot.on_startup
async def on_startup(bot: Bot):
    print("bot, 启动!")
    commands.init(bot)

if __name__ == '__main__':
    bot.run() 
