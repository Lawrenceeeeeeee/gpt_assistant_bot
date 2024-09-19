from okx import OkxRestClient
import pandas as pd
import time
from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
import os

import contextvars

api = OkxRestClient()


async def get_candlesticks(msg, instId, start_time, end_time, bar='1H', limit=100):
    from kook_bot import bot
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
        path = f"./src/tmp/candlesticks_{int(time.time())}.csv"
        df.to_csv(path)
        file_url = await bot.client.create_asset(path)
        await msg.reply(file_url,type=MessageTypes.FILE)
        os.remove(path)
        return True
    except Exception as e:
        return False
    
if __name__ == '__main__':

    instId = 'BTC-USDT-SWAP'
    now = int(time.time()*1000)
    start = now - 365*24*60*60*1000
    df = get_candlesticks(instId, start, now)
    print(df)
