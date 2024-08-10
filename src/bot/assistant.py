from openai import AsyncOpenAI
import os
from pydantic import BaseModel
import time
from dotenv import load_dotenv
from retry import retry
import json
from ..func_call.hefeng import get_now, get_minutely
from ..func_call.gaode import route_planning
import traceback

load_dotenv()

class Assistant():
    # client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # thread = client.beta.threads.create()
    assistant_id = "asst_rQTRO7OnR7FrMnd4c5MpdeDO"
    prev_run_id: str | None = None
    
    def __init__(self, aclient, thread_id) -> None:
        self.aclient = aclient
        self.thread_id = thread_id

    @retry(tries=5, delay=1)
    async def add_message(self, content, attachments=None) -> None:
        
        if attachments is None:
            message = await self.aclient.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=content,
            )
        else:
            message = await self.aclient.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=content,
                attachments=attachments,
            )

    @retry(tries=5, delay=1)
    async def create_a_run(self, tool_outputs=None, run_id=None) -> None:
        # instruction = None
        # if "name" in kwargs:
        #     instruction = f"发送者是：{kwargs['name']}"
        #     print(instruction)
        if tool_outputs:
            run = await self.aclient.beta.threads.runs.submit_tool_outputs_and_poll(
                thread_id=self.thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
        else:
            run = await self.aclient.beta.threads.runs.create_and_poll(
                assistant_id=self.assistant_id,
                thread_id=self.thread_id,
            )

        if run.status == 'completed':
            messages = await self.aclient.beta.threads.messages.list(
                thread_id=self.thread_id
            )
            return messages
        else:
            print(run.status)
        
        # Define the list to store tool outputs
        tool_outputs = []
        
        # Loop through each tool in the required action section
        for tool in run.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "get_now":
                print("get_now")
                try:
                    print(tool.function.arguments)
                    res = get_now(json.loads(tool.function.arguments)["location"])
                    res = res.dict()
                except Exception as e:
                    print("Failed to get weather data:", e)
                    print(traceback.format_exc())
                    res = "获取天气数据失败"
                print(res)
                tool_outputs.append({
                    "tool_call_id": tool.id,
                    "output": f"{res}"
                })
            elif tool.function.name == "get_minutely":
                print("get_minutely")
                try:
                    print(tool.function.arguments)
                    res = get_minutely(json.loads(tool.function.arguments)["location"])
                    res = res.dict()
                except Exception as e:
                    print("Failed to get weather data:", e)
                    print(traceback.format_exc())
                    res = "获取分钟级降水数据失败"
                print(res)
                tool_outputs.append({
                    "tool_call_id": tool.id,
                    "output": f"{res}"
                })
            elif tool.function.name == "route_planning":
                print("route_planning")
                try:
                    print(tool.function.arguments)
                    res = route_planning(**json.loads(tool.function.arguments))
                except Exception as e:
                    print("Failed to get route data:", e)
                    print(traceback.format_exc())
                    res = "获取路线规划数据失败"
                print(res)
                tool_outputs.append({
                    "tool_call_id": tool.id,
                    "output": f"{res}"
                })
        
        # Submit all tool outputs at once after collecting them in a list
        if tool_outputs:
            try:
                res = await self.create_a_run(tool_outputs=tool_outputs, run_id=run.id)
                print("Tool outputs submitted successfully.")
                return res
            except Exception as e:
                print(traceback.format_exc())
        else:
            print("No tool outputs to submit.")
        
        if run.status == 'completed':
            messages = await self.aclient.beta.threads.messages.list(
                thread_id=self.thread_id
            )
            return messages
        else:
            print(run.status)
        return None
