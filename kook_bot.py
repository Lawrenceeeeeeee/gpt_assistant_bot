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

from bot import Assistant
from khl import Bot, Message, EventTypes, Event

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
async def gpt_assistant_reply(msg: Message):  # when `name` is not set, the function name will be used
    bot_info = await bot.client.fetch_me()
    bot_id = bot_info.id
    
    channel_id = msg._ctx.channel._id
    author_id = msg.author_id
    author_nickname = msg.extra['author']['nickname']
    is_bot = msg.extra['author']['bot']
    
    mentioned_ids = [mention['id'] for mention in msg.extra['kmarkdown']['mention_part']]
    mentioned = True if bot_id in mentioned_ids else False
    
    try:
        content = json.loads(msg.content)
    except Exception as e:
        content = msg.content
    
    if mentioned and not is_bot:
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

if __name__ == '__main__':
    bot.run() 


'''
[{
	"theme": "invisible",
	"color": "",
	"size": "lg",
	"expand": false,
	"modules": [{
		"type": "file",
		"title": "3 远期与期货 4.pdf",
		"src": "https://img.kookapp.cn/attachments/2024-08/03/66ae2c7d88544.pdf",
		"external": false,
		"size": 572524,
		"canDownload": true,
		"elements": []
	}, {
		"type": "container",
		"elements": [{
			"type": "image",
			"src": "https://img.kookapp.cn/assets/2024-08/03/dif2vLUtAF046046.jpeg",
			"alt": "",
			"size": "lg",
			"circle": false,
			"title": "",
			"elements": []
		}]
	}, {
		"type": "section",
		"mode": "left",
		"accessory": null,
		"text": {
			"type": "kmarkdown",
			"content": "(met)3166139532(met) 测试",
			"elements": []
		},
		"elements": []
	}],
	"type": "card"
}]

'[Lawrence (id: 2633893164)] [{"theme":"invisible","color":"","size":"lg","expand":false,"modules":[{"type":"section","mode":"left","accessory":null,"text":{"type":"kmarkdown","content":"(met)3166139532(met) 描述一下这张图片","elements":[]},"elements":[]},{"type":"container","elements":[{"type":"image","src":"https:\\/\\/img.kookapp.cn\\/assets\\/2024-08\\/03\\/bs9EDM2hM80dw09u.png","alt":"","size":"lg","circle":false,"title":"","elements":[]}]}],"type":"card"}]'

'''