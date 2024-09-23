import requests
from datetime import datetime, timedelta, timezone
import pytz
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
from khl import Bot, Message, MessageTypes, EventTypes, Event, PrivateMessage, PublicMessage, guild
from khl.card import Card, CardMessage, Module, Types, Element, Struct
import asyncio
import schedule
import time

load_dotenv()

## websocket
bot = Bot(token = os.getenv("KOOK_WEBSOCKET_TOKEN"))

# 设置 OpenAI API Key
openai_api_key = os.getenv('OPENAI_API_KEY')   # 替换为你的 OpenAI API Key

# 初始化 OpenAI 客户端
client = OpenAI(api_key=openai_api_key)

# 定义新闻结构
class NewsExtraction(BaseModel):
    title: str
    abstract: str
    keywords: list[str]
    sentiment: str
    published_on: str

def translate_to_chinese(text):
    """使用 GPT-4o-mini 模型将英文文本翻译为中文"""
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert at structured data extraction. You will be given unstructured news content and should convert it into the given structure."},
            {"role": "user", "content": f"请将以下内容翻译为中文：\n{text}"}
        ]
    )
    
    # 使用 .message.content 来获取返回的文本
    return completion.choices[0].message.content.strip()

def format_news_with_time(news_data):
    """格式化每条新闻，包含标题、摘要、关键词、情绪及UTC时间"""
    formatted_news = []
    
    for article in news_data['Data']:
        # 提取新闻信息
        title = article.get('TITLE', '')
        body = article.get('BODY', '')
        keywords = article.get('KEYWORDS', '').split('|')  # 将关键词从竖线分隔转换为列表
        sentiment = article.get('SENTIMENT', '')

        # 提取UTC时间并格式化
        published_on = datetime.utcfromtimestamp(article.get('PUBLISHED_ON', 0)).strftime('%Y-%m-%d %H:%M UTC')

        # 翻译标题、摘要、关键词、情绪
        title_cn = translate_to_chinese(title)
        body_cn = translate_to_chinese(body)
        keywords_cn = [translate_to_chinese(keyword) for keyword in keywords]
        sentiment_cn = translate_to_chinese(sentiment)

        # 格式化输出
        formatted_news.append(f"发布时间：{published_on}\n标题：{title_cn}\n关键词：{', '.join(keywords_cn)}\n摘要：{body_cn}\n情绪：{sentiment_cn}\n")

    return formatted_news

def generate_morning_report(news_data):
    """生成包含10条新闻大意的简短晨报"""
    # 提取每条新闻的大意
    news_summary = [f"{article.get('TITLE', '')}: {article.get('BODY', '')[:100]}..." for article in news_data['Data']]
    
    # 生成中文的晨报文本
    news_summary_text = "\n".join(news_summary)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"请根据以下新闻生成一段包含10条新闻大意的晨报,不需要分点，整理成一段通顺的文字：\n{news_summary_text}"}
        ]
    )
    
    return completion.choices[0].message.content.strip()

def get_news_data():
    """获取北京时间每天早上8点之前的10条新闻"""
    # 获取当前北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now_beijing = datetime.now(beijing_tz)

    # 计算当前时间的前一天早上8点的时间戳
    target_time = now_beijing.replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=1)
    
    # 转换为 UTC 时间戳
    target_timestamp_utc = int(target_time.astimezone(pytz.utc).timestamp())

    # 使用 CryptoCompare API 获取新闻
    api_key = os.getenv('CRYPTOCOMPARE_API_KEY')  # 替换为你的CryptoCompare API Key
    response = requests.get('https://data-api.cryptocompare.com/news/v1/article/list',
                            params={"lang": "EN", "limit": 10, "to_ts": target_timestamp_utc, "api_key": api_key},
                            headers={"Content-type": "application/json; charset=UTF-8"}
                           )

    # 检查请求是否成功
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

crypto_channel_id = "5816881603343440"

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
    # 获取新闻数据
    news_data = get_news_data()

    if news_data:
        # 格式化新闻并输出每条新闻
        formatted_news = format_news_with_time(news_data)
        for news in formatted_news:
            print(news)  # 格式化输出为可读文本
        
        # 生成晨报
        morning_report = generate_morning_report(news_data)
        print("\n### 今日晨报 ###")
        print(morning_report)
        msg = "**今日晨报**\n" + morning_report
        await send_msg(ch, msg)

# 定时调度器的包装器，运行异步函数
def run_async_job():
    asyncio.run(main())

if __name__ == "__main__":
    print("crypto新闻启动！")
    # 每天早上8点运行任务
    schedule.every().day.at("08:00").do(run_async_job)
    # 每天下午6点运行任务
    schedule.every().day.at("18:00").do(run_async_job)

    while True:
        # 检查是否有任务到期需要执行
        schedule.run_pending()
        time.sleep(60)  # 每隔 60 秒检查一次