from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, ClassVar
from openai import OpenAI, AsyncOpenAI
import os
from dotenv import load_dotenv
import requests
import re
import asyncio

from bot import Assistant

import botpy
from botpy import logging, BotAPI
from botpy.ext.command_util import Commands
from botpy.message import Message

load_dotenv()

_log = logging.get_logger()

aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

threads = {}

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

class UserMessage(BaseModel):
    text: str | None = None
    images: list[botpy.message.Message._Attachments] | None = None
    file_urls: list[Message._Attachments] | None = None
    
    class Config:
        arbitrary_types_allowed = True
    
    async def user_content(self):
        text_dict = [{
            "type": "text",
            "text": self.text,
        }] if self.text else []
        
        
        if self.images:
            image_dict = []
            for image in self.images:
                image_url = f"https://{image.url}"
                local_filename = f"tmp/{image.filename}"
                self.download_file(image_url, local_filename)
                image = f"tmp/{image.filename}"
                
                upload_file = await aclient.files.create(
                    file=open(image, "rb"),
                    purpose="vision"
                )

                image_file = {
                    "type": "image_file",
                    "image_file": {
                        "file_id": upload_file.id,
                        "detail": "auto"
                    }
                }
                image_dict.append(image_file)           
        else:
            image_dict = []

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

async def check_thread(thread_id):
    try:
        res = await aclient.beta.threads.retrieve(thread_id)
    except Exception as e:
        res = None
    return res

@Commands("清除历史")
async def clear_history(api: BotAPI, message: Message, params=None):
    channel_id = message.channel_id
    if channel_id not in threads.keys():
        await message.reply(content="[系统消息] 暂无聊天记录，无需清除")
    else:
        response = await aclient.beta.threads.delete(threads[channel_id])
        new_thread = await aclient.beta.threads.create()
        threads[channel_id] = new_thread.id
        await message.reply(content="[系统消息] 聊天记录已清除")

class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")

    async def on_at_message_create(self, message: Message):
        # 注册指令handler
        handlers = [
            clear_history,
        ]
        for handler in handlers:
            if await handler(api=self.api, message=message):
                print(f"handler {handler} executed")
                return

        _log.info(message.author.avatar)
        if "sleep" in message.content:
            await asyncio.sleep(10)
        _log.info(message.author.username)
        
        user_name = message.author.username
        user_id = message.author.id
        channel_id = message.channel_id
        
        if channel_id not in threads.keys():
            thread_info = await aclient.beta.threads.create()
            threads[channel_id] = thread_info.id
        elif await check_thread(threads[channel_id]) is None:
            thread_info = await aclient.beta.threads.create()
            threads[channel_id] = thread_info.id
            
        chatbot = Assistant(aclient, threads[channel_id])
        images = []
        files = []
        
        if message.attachments:
            for attachment in message.attachments:
                file_ext = attachment.filename.split(".")[-1]
                if file_ext in tools_selection["image"]:
                    print(type(attachment))
                    images.append(attachment)
                elif file_ext in tools_selection["file_search"] or file_ext in tools_selection["code_interpreter"]:
                    files.append(attachment)
                else:
                    await message.reply(f"Unsupported file type: {file_ext}", mention_author=False)
        
        msg = UserMessage(
            text=f"[{user_name} (id: {user_id})] {message.content}",
            images=images if images else None,
            file_urls=files if files else None
        )
        attachments = await msg.attachments()
        print(await msg.user_content())
        await chatbot.add_message(await msg.user_content(), attachments)
        
        
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
                await message.reply(content=response)
        # print(message.attachments[0].url)
        # print(message)
        # print(message.message_reference.message_id)
        # await message.reply(content=f"机器人{self.robot.name}收到你的@消息了: {message.content}")

'''
{
	"author": "{'id': '2796060948822921914', 'username': 'Laaaaawrence', 'bot': False, 'avatar': 'http://thirdqq.qlogo.cn/g?b=oidb&k=dZbIvvabybdgWNRd4bH7qw&kti=Zapd0QAAAAA&s=0&t=1690089318'}",
	"content": "<@!6254063431239261533> 测试一下",
	"channel_id": "655932294",
	"id": "08c28c9cb9d49abafaff011086f7e2b8023806488d82b7b506",
	"guild_id": "18443622376708441666",
	"member": "{'nick': 'Laaaaawrence', 'roles': ['4', '12'], 'joined_at': '2024-05-29T20:15:24+08:00'}",
	"message_reference": "{'message_id': None}",
	"mentions": "[{'id': '6254063431239261533', 'username': '青雀-测试中', 'bot': True, 'avatar': 'http://thirdqq.qlogo.cn/g?b=oidb&k=22xwwicVm0MlqiaIBB5sk2ag&kti=Zq3A1AAAAAI&s=0&t=1722660688'}]",
	"attachments": "[{'content_type': 'image/jpeg', 'filename': '10C3A477751E679CE9B5E2A71B140C16.jpeg', 'height': 2412, 'width': 1080, 'id': '3182969374', 'size': 171216, 'url': 'gchat.qpic.cn/qmeetpic/673753304020408412/655932294-3182969374-10C3A477751E679CE9B5E2A71B140C16/0'}]",
	"seq": "6",
	"seq_in_channel": "6",
	"timestamp": "2024-08-03T13:33:01+08:00",
	"event_id": "AT_MESSAGE_CREATE:98fd6dd4-eb3f-437c-891a-f11d78858f81"
}
'''

'''
{
	"author": "{'id': '2796060948822921914', 'username': 'Laaaaawrence', 'bot': False, 'avatar': 'http://thirdqq.qlogo.cn/g?b=oidb&k=dZbIvvabybdgWNRd4bH7qw&kti=Zapd0QAAAAA&s=0&t=1690089318'}",
	"content": "<@!6254063431239261533> 测试",
	"channel_id": "655932294",
	"id": "08c28c9cb9d49abafaff011086f7e2b802380f488987b7b506",
	"guild_id": "18443622376708441666",
	"member": "{'nick': 'Laaaaawrence', 'roles': ['4', '13'], 'joined_at': '2024-05-29T20:15:24+08:00'}",
	"message_reference": "{'message_id': '08c28c9cb9d49abafaff011086f7e2b802380e48ab86b7b506'}",
	"mentions": "[{'id': '6254063431239261533', 'username': '青雀-测试中', 'bot': True, 'avatar': 'http://thirdqq.qlogo.cn/g?b=oidb&k=0HVXpheeTibTPFuFGlFgjYg&kti=Zq3DigAAAAE&s=0&t=1722660688'}]",
	"attachments": "[]",
	"seq": "15",
	"seq_in_channel": "15",
	"timestamp": "2024-08-03T13:43:37+08:00",
	"event_id": "AT_MESSAGE_CREATE:91dc7cbb-8bb0-47aa-bf78-96c553d4178c"
}
'''

if __name__ == "__main__":
    # 通过预设置的类型，设置需要监听的事件通道
    # intents = botpy.Intents.none()
    # intents.public_guild_messages=True

    # 通过kwargs，设置需要监听的事件通道
    appid = os.getenv("QQ_BOT_APPID")
    secret = os.getenv("QQ_BOT_APPSECRET")
    
    intents = botpy.Intents(public_guild_messages=True)
    client = MyClient(intents=intents)
    client.run(appid=appid, secret=secret)