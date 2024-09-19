import os
from dotenv import load_dotenv
import json
import traceback
import asyncio
import random

from src import email_verif as ev
from src import chatbot_reply, chatbot
from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, bot, guild
from khl.card import Card, CardMessage, Module, Types, Element, Struct

load_dotenv()

bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))


candidate = {}
lock = asyncio.Lock()

# 题库(从question.json文件中读取)
with open("questions.json", "r") as f:
    questions = json.load(f)

# @bot.command()
async def verify(msg: Message):
    if isinstance(msg, PrivateMessage):
        user_id = msg.author_id
        guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
        guild_user = await guild.fetch_user(user_id)
        if guild_user.roles:
            await msg.reply("您已经通过验证了", mention_author=False)
            return
        if user_id in candidate.keys():
            await msg.reply(f"题目已生成，请先完成题目：{questions[candidate[user_id]]['question']}", mention_author=False)
            return

        async with lock:
            question_num = random.randint(0, len(questions) - 1)
            question = questions[question_num]
            candidate[user_id] = question_num
            await msg.reply(f"问题：{question['question']}", mention_author=False)
    else:
        await msg.reply("请私信我进行验证", mention_author=False)

# @bot.command()
async def answer(msg: Message, text: str):
    if isinstance(msg, PrivateMessage):
        user_id = msg.author_id
        guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
        guild_user = await guild.fetch_user(user_id)
        if guild_user.roles:
            await msg.reply("您已经通过验证了", mention_author=False)
            return
        if user_id not in candidate.keys():
            await msg.reply("请先输入`/verify`指令", mention_author=False)
            return

        async with lock:
            question_num = candidate[user_id]
            question = questions[question_num]
            if text == question['answer']:
                await msg.reply("验证成功，欢迎来到CUFER'S HUB", mention_author=False)
                await guild.grant_role(user_id, os.getenv("MEMBER_ID"))
                del candidate[user_id]
            else:
                await msg.reply("验证失败，请重新输入`/verify`指令", mention_author=False)
                del candidate[user_id]
    else:
        await msg.reply("请私信我进行验证", mention_author=False)
