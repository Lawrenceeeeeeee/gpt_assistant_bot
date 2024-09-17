from . import chatbot, email_verif, bot_func, membership
from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
import os
from dotenv import load_dotenv

load_dotenv()

def init(bot:Bot):
    @bot.command(name="clear_history")
    async def clear_history(msg:Message):
        await chatbot.clear_history(msg)

    @bot.command(name="verif")
    async def verif(msg: Message, student_id: str):
        if isinstance(msg, PrivateMessage):
            user_id = msg.author_id
            guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
            guild_user = await guild.fetch_user(user_id)
            if guild_user.roles:
                await msg.reply("您已经通过验证了", mention_author=False)
                return
            await email_verif.verif(msg, student_id)

    @bot.command(name="captcha")
    async def captcha(msg: Message, code: str):
        if isinstance(msg, PrivateMessage):
            user_id = msg.author_id
            guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
            guild_user = await guild.fetch_user(user_id)
            if guild_user.roles:
                await msg.reply("您已经通过验证了", mention_author=False)
                return
            result, message = await email_verif.captcha(msg, code)
            if result:
                await guild.grant_role(user_id, os.getenv("MEMBER_ID"))
            await msg.reply(message, mention_author=False)

    @bot.command(name="send")
    async def send(msg: Message, channel_id: str):
        await bot_func.send(msg, channel_id)
        
    @bot.command(name="enterCode")
    async def enterCode(msg: Message, code: str):
        if isinstance(msg, PrivateMessage):
            user_id = msg.author_id
            guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
            guild_user = await guild.fetch_user(user_id)
            result, message = await membership.secret_verify(code, user_id)
            await msg.reply(message, mention_author=False)
        
