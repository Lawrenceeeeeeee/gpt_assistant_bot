from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, ClassVar
from openai import OpenAI, AsyncOpenAI
import os
from dotenv import load_dotenv
import requests
import re
from pprint import pprint
import json
from urllib.parse import urlparse
import traceback
import asyncio
import random

from bot import Assistant
from src import email_verif as ev
from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
from khl.card import Card, CardMessage, Module, Types, Element, Struct

load_dotenv()

tools_selection = {
    "file_search": [
        "c",
        "cs",
        "cpp",
        "doc",
        "docx",
        "html",
        "java",
        "json",
        "md",
        "pdf",
        "php",
        "pptx",
        "py",
        "py",
        "rb",
        "tex",
        "txt",
        "css",
        "js",
        "sh",
        "ts"
    ],
    "code_interpreter": [
        "c",
        "cs",
        "cpp",
        "doc",
        "docx",
        "html",
        "java",
        "json",
        "md",
        "pdf",
        "php",
        "pptx",
        "py",
        "rb",
        "tex",
        "txt",
        "css",
        "js",
        "sh",
        "ts",
        "csv",
        "tar",
        "xlsx",
        "xml",
        "zip"
    ],
    "image": [
        "jpeg",
        "jpg",
        "gif",
        "png",
        "bmp",
        "tiff",
        "svg",
        "webp",
        "heic",
        "ico",
        "eps",
        "raw",
        "psd",
        "tga",
        "ai"
    ]
    
}

## websocket
bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))

aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class UserMessage(BaseModel):
    text: str | None = None
    images: list[str] | None = None
    files: list[dict] | None = None
    
    class Config:
        arbitrary_types_allowed = True
    
    async def user_content(self):
        text_dict = [{
            "type": "text",
            "text": self.text,
        }] if self.text else []
        
        image_dict = []
        
        if self.images:
            for image in self.images:
                parsed_url = urlparse(image)
                # 提取文件名
                file_name = os.path.basename(parsed_url.path)
                file_path = self.download_file(image, f"tmp/{file_name}")
                uploaded_image = await aclient.files.create(
                    file=open(file_path, "rb"),
                    purpose="vision"
                )
                image_dict.append({
                    "type": "image_file",
                    "image_file": {"file_id": uploaded_image.id}
                })
                # 删除临时文件
                os.remove(file_path)

        content = text_dict + image_dict
        return content

    def download_file(self, url, local_filename):
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return local_filename

    async def attachments(self) -> List[str]:
        attachments_dicts = []
        if self.files:
            for file_item in self.files:
                local_filename = f"tmp/{file_item['title']}"
                file_ext = file_item['title'].split(".")[-1]
                if file_ext in tools_selection["file_search"]:
                    tool = "file_search"
                elif file_ext in tools_selection["code_interpreter"]:
                    tool = "code_interpreter"
                # elif file_ext in tools_selection["image"]:
                #     continue
                else:
                    raise ValueError(f"Unsupported file type: {file_ext}")
                
                self.download_file(file_item['src'], local_filename)
                with open(local_filename, "rb") as f:
                    response = await aclient.files.create(file=f, purpose="assistants")
                    file_id = response.id
                    attachment = {
                        "file_id": file_id,
                        "tools": [
                            {"type": tool}
                        ]
                    }
                    attachments_dicts.append(attachment)
                os.remove(local_filename)
        return attachments_dicts


threads = {}

async def check_thread(thread_id):
    try:
        res = await aclient.beta.threads.retrieve(thread_id)
    except Exception as e:
        res = None
    return res

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
        if channel_id not in threads.keys():
            thread_info = await aclient.beta.threads.create()
            threads[channel_id] = thread_info.id
        elif await check_thread(threads[channel_id]) is None:
            thread_info = await aclient.beta.threads.create()
            threads[channel_id] = thread_info.id
            
        chatbot = Assistant(aclient, threads[channel_id])
        
        text = ""
        images = []
        files = []
        
        if type(content) == list:
            for module in content[0]['modules']:
                if module['type'] == "container": # image
                    images.append(module['elements'][0]['src'])
                elif module['type'] == "file":
                    files.append(module)
                elif module['type'] == "section":
                    text += module['text']['content']
                else:
                    await msg.reply(f"Unsupported file type: {module['type']}", mention_author=False)
        else:
            text = msg.content
                    
        user_message = UserMessage(
            text=f"[{author_nickname} (id: {author_id})] {text}",
            images=images if images else None,
            files=files if files else None
        )
        attachments = await user_message.attachments()
        user_content_msg = await user_message.user_content()
        print(user_content_msg)
        await chatbot.add_message(user_content_msg, attachments)
        
        response = await chatbot.create_a_run()
        # res.data[0].content[0].text.value
        if response.data[0].role == "assistant":
            for res in response.data[0].content:                
                if res.type == "text":
                    response = res.text.value
                else:
                    response = "Unsupported message type"
                # 发送响应
                print(response)
                await msg.reply(response, mention_author=False)


candidate = {}
lock = asyncio.Lock()

# 题库(从question.json文件中读取)
with open("questions.json", "r") as f:
    questions = json.load(f)

@bot.on_event(EventTypes.JOINED_GUILD)
async def join_guild_send_event(b: Bot, e: Event):
    try:
        print("user join guild", e.body)  # 用户加入了服务器
        ch = await bot.client.fetch_public_channel(os.getenv("ENTRANCE_ID"))  # 获取指定文字频道的对象
        ret = await ch.send(f"欢迎入群，(met){e.body['user_id']}(met)！现在你应该只能看到“欢迎”分组。请先查看私信，获取身份组，然后就可以在服务器内畅谈了~\n\
为了方便及时收到最新消息, 请务必开启kook通知权限, 并在kook中“我的”-“通知设置”中设置“手机始终接收通知”。")
        print(f"ch.send | msg_id {ret['msg_id']}") # 方法1 发送消息的id

        async with lock:
            # 私信用户验证题目
            question_num = random.randint(0, len(questions) - 1)
            question = questions[question_num]
            candidate[e.body['user_id']] = question_num
            user = await bot.client.fetch_user(e.body['user_id'])
            welcome_msg = [
                            {
                                "type": "card",
                                "theme": "secondary",
                                "size": "lg",
                                "modules": [
                                {
                                    "type": "header",
                                    "text": {
                                    "type": "plain-text",
                                    "content": "欢迎加入CUFER'S HUB！"
                                    }
                                },
                                {
                                    "type": "section",
                                    "text": {
                                    "type": "kmarkdown",
                                    "content": f'''为了确保我们的社区安全，我们需要验证您的学生身份: 

请私信我指令`/verif [学号]`进行身份验证。稍后您将会在学校邮箱中收到验证码。放心，您的学号经过加密处理，即使是管理员也无法查看您的学号。
然后请用指令`/captcha [验证码]`进行验证。
一定要注意输入格式哦！格式错误将不会有任何响应！
如果您已毕业，请您私信管理员进行验证。

示例:  
    `/verif 20xxxxxxxx`
    `/captcha 123456`

**问：“诶？学校邮箱是什么？”**
答：如果您没有申请过学校邮箱，请查阅[学校邮箱使用攻略](http://zhxy.cufe.edu.cn/info/1082/2097.htm)。申请成功之后再进行学号验证。
**问：“怎么一直不发验证码？这bot是出问题了吗？”**
答：请检查您的输入，确保您按照正确的指令格式书写，并且指令拼写无误，斜杠方向无误。如果仍然不行，请联系管理员。

通过验证后，你将获得访问所有频道的权限。

感谢您的配合，祝您在CUFER'S HUB愉快！

如有任何问题，请联系管理员。
                                    '''
                                    }
                                }
                                ]
                            }
                        ]
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

@bot.command() 
async def clear_history(msg:Message):
    channel_id = msg._ctx.channel._id if isinstance(msg, PublicMessage) else msg._ctx.channel.id
    if channel_id not in threads.keys():
        await msg.reply("[系统消息] 无需清除聊天记录", mention_author=False)
        return
    response = await aclient.beta.threads.delete(threads[channel_id])
    new_thread = await aclient.beta.threads.create()
    threads[channel_id] = new_thread.id
    await msg.reply("[系统消息] 聊天记录已清除", ephemeral=True)

# 邮箱验证
@bot.command()
async def verif(msg: Message, student_id: str):
    try:
        if isinstance(msg, PrivateMessage):
            user_id = msg.author_id
            guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
            guild_user = await guild.fetch_user(user_id)
            if guild_user.roles:
                await msg.reply("您已经通过验证了", mention_author=False)
                return

            result, message = ev.create_captcha(user_id, student_id)
            await msg.reply(message, mention_author=False)
    except Exception as result:
        print(traceback.format_exc())

@bot.command()
async def captcha(msg: Message, code: str):
    try:
        if isinstance(msg, PrivateMessage):
            user_id = msg.author_id
            guild = await bot.client.fetch_guild(os.getenv("KOOK_GUILD_ID"))
            guild_user = await guild.fetch_user(user_id)
            if guild_user.roles:
                await msg.reply("您已经通过验证了", mention_author=False)
                return

            result, message = ev.verify_captcha(user_id, code)
            if result:
                await guild.grant_role(user_id, os.getenv("MEMBER_ID"))
            await msg.reply(message, mention_author=False)
    except Exception as result:
        print(traceback.format_exc())


if __name__ == '__main__':
    bot.run() 
