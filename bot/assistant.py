from openai import OpenAI
import os
from pydantic import BaseModel
import time
from dotenv import load_dotenv

load_dotenv()

class Assistant():
    # client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # thread = client.beta.threads.create()
    assistant_id = "asst_rQTRO7OnR7FrMnd4c5MpdeDO"
    
    def __init__(self, client, thread_id) -> None:
        self.client = client
        self.thread_id = thread_id

    def add_message(self, content, attachments=None) -> None:
        if attachments is None:
            message = self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=content,
            )
        else:
            message = self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=content,
                attachments=attachments,
            )

    def create_a_run(self):
        # instruction = None
        # if "name" in kwargs:
        #     instruction = f"发送者是：{kwargs['name']}"
        #     print(instruction)
        
        run = self.client.beta.threads.runs.create_and_poll(
            assistant_id=self.assistant_id,
            thread_id=self.thread_id,
        )

        while run.status != "completed":
            print(run.status)
            time.sleep(1)

        messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
        return messages

if __name__ == "__main__":
    image_url = "https://upload-bbs.miyoushe.com/upload/2024/07/22/288909600/5073838317d8bf76afdb06020fd83424_7475603835828891488.png?x-oss-process=image//resize,s_600/quality,q_80/auto-orient,0/interlace,1/format,png"
    content = [
        # {
        #     "type":"image_url",
        #     "image_url":{
        #         "url":image_url,
        #         "detail": "high"
        #     },
        # },
        {
            "type":"text",
            "text":"你好啊",
        }
    ]
    attachments = [
        {
            "file_id":"file-rATMbiAdvwxMyy4CrzxwAzsn",
            "tools":[
                {
                    "type":"file_search"
                }
            ]
        }
    ]
    
    assistant = Assistant()
    # assistant.add_message(content)
    # res = assistant.create_a_run()
    # print(res.data[0].content[0].text.value)
    assistant.add_message("[Lawrence (id:123456789111)] 我叫什么名字")
    res = assistant.create_a_run()
    print(res.data[0].content[0].text.value)