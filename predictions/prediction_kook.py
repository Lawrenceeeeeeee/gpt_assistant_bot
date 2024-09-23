from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
from dotenv import load_dotenv
import os
from okx import OkxRestClient, OkxSocketClient
import time
import traceback
import pandas as pd
import asyncio

from trainee import predict_next_value

load_dotenv()

## websocket
bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))
crypto_channel_id = "5816881603343440"

api = OkxRestClient()

def get_candlesticks(instId, start_time, end_time, bar='1H', limit=100):
    result = []
    current_end_time = end_time  # 初始的结束时间设为用户请求的结束时间
    try:
        while True:
            # 每次请求API，获取在时间范围内的数据
            res = api.public.get_candlesticks(instId, after=current_end_time, before=start_time, bar=bar, limit=limit)
            candlesticks = res.get('data', [])
            
            if candlesticks:
                # 将获取到的数据追加到结果中
                result.extend(candlesticks)
                
                # 更新下一次请求的结束时间，取到的数据中的最早时间
                current_end_time = int(candlesticks[-1][0])  # 假设第一个字段是时间戳
                if current_end_time <= start_time:  # 如果已经获取到了起始时间的数据，停止请求
                    break
            else:
                # 如果没有返回数据，停止循环
                break
        
        # 将获取到的结果转成DataFrame
        df = pd.DataFrame(result, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'volccy', 'volccyquote', 'confirm'])
        df[['ts', 'o', 'h', 'l', 'c', 'v']] = df[['ts', 'o', 'h', 'l', 'c', 'v']].astype(float)
        return df
    except Exception as e:
        traceback.print_exc()
        return 

async def send_msg(ch, text):
    structured_msg = [
                        {
                            "type": "card",
                            "theme": "secondary",
                            "size": "lg",
                            "modules": [
                            {
                                "type": "section",
                                "text": {
                                "type": "kmarkdown",
                                "content": f"{text}"
                                }
                            }
                            ]
                        }
                        ]
    ret = await ch.send(text) # 方法1
    print(f"ch.send | msg_id {ret['msg_id']}") # 方法1 发送消息的id 
    
async def main():
    ch = await bot.client.fetch_public_channel(crypto_channel_id)
    now = int(time.time() * 1000)
    before = now - 3 * 24 * 60 * 60 * 1000
    data = get_candlesticks('BTC-USDT-SWAP', before, now)
    res = predict_next_value(data)
    message = f"BTC-USDT-SWAP 未来1小时涨跌幅为{res*100:.2f}%"
    await send_msg(ch, message)


if __name__ == '__main__':
    asyncio.run(main())
    