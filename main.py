from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, ClassVar
from openai import OpenAI, AsyncOpenAI
import os
from dotenv import load_dotenv
import requests
import discord
from discord.ext import commands
import re

from bot import Assistant

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


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
thread = client.beta.threads.create()


class UserMessage(BaseModel):
    text: str | None = None
    image_urls: list[str] | None = None
    file_urls: list[discord.message.Attachment] | None = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def user_content(self):
        text_dict = [{
            "type": "text",
            "text": self.text,
        }] if self.text else []

        image_dict = [
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                    "detail": "auto"
                },
            } for image_url in self.image_urls
        ] if self.image_urls else []

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
        if self.file_urls:
            for url in self.file_urls:
                local_filename = f"tmp/{url.filename}"
                file_ext = url.filename.split(".")[-1]
                if file_ext in tools_selection["file_search"]:
                    tool = "file_search"
                elif file_ext in tools_selection["code_interpreter"]:
                    tool = "code_interpreter"
                # elif file_ext in tools_selection["image"]:
                #     continue
                else:
                    raise ValueError(f"Unsupported file type: {file_ext}")
                
                self.download_file(url.url, local_filename)
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
    

# 获取 Discord 机器人令牌
token = os.getenv("DISCORD_BOT_TOKEN")

# 设置 Discord 的 Intents
intents = discord.Intents.default()
intents.message_content = True

# 创建一个新的 bot 客户端
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree


threads = {}

@bot.event
async def on_ready():
    slash = await bot.tree.sync()
    print(f"目前登入身份 --> {bot.user}")
    print(f"載入 {len(slash)} 個斜線指令")


async def check_thread(thread_id):
    try:
        res = await aclient.beta.threads.retrieve(thread_id)
    except Exception as e:
        res = None
    return res


# 当收到消息时，使用 DeepSeek 模型生成响应
@bot.event
async def on_message(message):
    sender = f"{message.channel.id}-{message.author.id}" 
    user_name = message.author.display_name
    user_id = message.author.id
    channel_id = message.channel.id
    
    print(f"user: {user_name} ({user_id}), channel: {channel_id}")
    
    # 不响应自己的消息
    if not isinstance(message.channel, discord.DMChannel):
        if message.author == bot.user or (bot.user.mention not in message.content):
            return
    else:
        if message.author == bot.user:
            return
    
    if channel_id not in threads.keys():
        thread_info = await aclient.beta.threads.create()
        threads[channel_id] = thread_info.id
    elif await check_thread(threads[channel_id]) is None:
        thread_info = await aclient.beta.threads.create()
        threads[channel_id] = thread_info.id
        
    chatbot = Assistant(aclient, threads[channel_id])
    
    image_urls = []
    files = []
    
    if message.attachments:
        for attachment in message.attachments:
            file_ext = attachment.filename.split(".")[-1]
            if file_ext in tools_selection["image"]:
                image_urls.append(attachment.url)
            elif file_ext in tools_selection["file_search"] or file_ext in tools_selection["code_interpreter"]:
                files.append(attachment)
            else:
                await message.reply(f"Unsupported file type: {file_ext}", mention_author=False)
                
    msg = UserMessage(
        text=f"[{user_name} (id: {user_id})] {message.content}",
        image_urls=image_urls if image_urls else None,
        file_urls=files if files else None
    )
    attachments = await msg.attachments()
    print(msg.user_content())
    await chatbot.add_message(msg.user_content(), attachments)
    
    async with message.channel.typing():
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
                await message.reply(response, mention_author=False)


@bot.tree.command(name = "clear_history", description = "清除历史记录")
async def clear_history(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    response = await aclient.beta.threads.delete(threads[channel_id])
    new_thread = await aclient.beta.threads.create()
    threads[channel_id] = new_thread.id
    await interaction.response.send_message("[系统消息] 聊天记录已清除", ephemeral=True)

# 运行机器人
bot.run(token)
    
    
    
    