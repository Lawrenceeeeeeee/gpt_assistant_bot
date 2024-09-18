from .bot import Assistant
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, ClassVar
from urllib.parse import urlparse
import requests
import os
import sqlite3

from khl import Message, PublicMessage

load_dotenv()

aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conn = sqlite3.connect('threads.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS threads (
    channel_id TEXT PRIMARY KEY,
    thread_id TEXT
);
''')
conn.commit()

threads = {}

tools_selection = {
    "file_search": ["c","cs","cpp","doc","docx","html","java","json","md","pdf","php","pptx","py","py","rb","tex","txt","css","js","sh","ts"],
    "code_interpreter": ["c","cs","cpp","doc","docx","html","java","json","md","pdf","php","pptx","py","rb","tex","txt","css","js","sh","ts","csv","tar","xlsx","xml","zip"],
    "image": ["jpeg","jpg","gif","png","bmp","tiff","svg","webp","heic","ico","eps","raw","psd","tga","ai"]
    
}

async def check_thread(thread_id):
    try:
        res = await aclient.beta.threads.retrieve(thread_id)
    except Exception as e:
        res = None
    return res

class Message(BaseModel):
    responses: list[str] | None = None
    attachments: list[str] | None = None

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
                file_path = self.download_file(image, f"src/tmp/{file_name}")
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


async def chatbot_reply(msg, content, channel_id, author_id, author_nickname):
    # 从数据库中获取指定channel的thread_id, 如果有就返回thread_id,没有thread_id就是None
    c.execute(f"SELECT thread_id FROM threads WHERE channel_id = '{channel_id}';")
    thread_id = c.fetchone()
    
    if not thread_id:
        thread_info = await aclient.beta.threads.create()
        # 在数据库中添加新的thread_id
        c.execute(f"INSERT INTO threads (channel_id, thread_id) VALUES ('{channel_id}', '{thread_info.id}');")
        thread_id = thread_info.id
    else: 
        print(f"频道{channel_id}正在使用的thread_id为{thread_id}")
        if await check_thread(thread_id[0]) is None:
            print(f"频道{channel_id}的thread_id {thread_id}已失效")
            thread_info = await aclient.beta.threads.create()
            # 更新数据库中的thread_id        
            c.execute(f"UPDATE threads SET thread_id = '{thread_info.id}' WHERE channel_id = '{channel_id}';")
            thread_id = thread_info.id
        else:
            thread_id = thread_id[0]
    chatbot = Assistant(aclient, thread_id)
    
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
                # await msg.reply(f"Unsupported file type: {module['type']}", mention_author=False)
                return f"Unsupported file type: {module['type']}"
    else:
        text = content
                
    user_message = UserMessage(
        text=f"[{author_nickname} (id: {author_id})] {text}",
        images=images if images else None,
        files=files if files else None
    )
    attachments = await user_message.attachments()
    user_content_msg = await user_message.user_content()
    print(user_content_msg)
    await chatbot.add_message(user_content_msg, attachments)
    
    response = await chatbot.create_a_run(msg)
    # res.data[0].content[0].text.value
    if response.data[0].role == "assistant":
        for res in response.data[0].content:                
            if res.type == "text":
                text_response = res.text.value
            else:
                text_response = "Unsupported message type"
            atts = []
            if res.text.annotations:
                for annotation in res.text.annotations:
                    if annotation.type == "file_path":
                        file_id = annotation.file_path.file_id
                        file_name = annotation.text.split("/")[-1]
                        atts.append(file_name)
                        file_data = await aclient.files.content(file_id)
                        file_data_bytes = file_data.read()
                        with open(f'./src/tmp/{file_name}', "wb") as file:
                            file.write(file_data_bytes)
            # 发送响应
            print(text_response)
            return {"text": text_response, "attachments": atts}


async def clear_history(msg:Message):
    channel_id = msg._ctx.channel._id if isinstance(msg, PublicMessage) else msg._ctx.channel.id
    c.execute(f"SELECT thread_id FROM threads WHERE channel_id = '{channel_id}';")
    conn.commit()
    thread_id = c.fetchone()
    if not thread_id:
        await msg.reply("[系统消息] 无需清除聊天记录", mention_author=False)
        return
    else:
        thread_id = thread_id[0]
    response = await aclient.beta.threads.delete(thread_id)
    new_thread = await aclient.beta.threads.create()
    c.execute(f"UPDATE threads SET thread_id = '{new_thread.id}' WHERE channel_id = '{channel_id}';")
    conn.commit()
    await msg.reply("[系统消息] 聊天记录已清除", ephemeral=True)

