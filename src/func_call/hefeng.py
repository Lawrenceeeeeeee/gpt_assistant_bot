import requests
import os
from urllib.parse import urlparse
import json
from dotenv import load_dotenv
from pydantic import BaseModel
import pandas as pd
from . import gaode

load_dotenv()

api_key = os.getenv("HEFENG_API_KEY")

china_cities = pd.read_csv("/root/gpt_assistant_bot/src/func_call/LocationList/China-City-List-latest.csv")

class Now(BaseModel):
    obsTime: str
    temp: str
    feelsLike: str
    icon: str
    text: str
    wind360: str
    windDir: str
    windScale: str
    windSpeed: str
    humidity: str
    precip: str
    pressure: str
    vis: str
    cloud: str
    dew: str

class MinutelyItem(BaseModel):
    fxTime: str
    precip: str
    type: str

class Minutely(BaseModel):
    summary: str
    minutely: list[MinutelyItem]


def get_now(location: str="昌平"):
    try:
        location_id = china_cities[china_cities["Location_Name_ZH"] == location]["Location_ID"].values[0]
    except:
        return None
    url = f"https://devapi.qweather.com/v7/weather/now?key={api_key}&location={location_id}"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    data = json.loads(res.text)
    # print(json.dumps(data, indent=4, ensure_ascii=False))
    now = Now(**data["now"])
    return now

def get_minutely(location: str ="中央财经大学沙河校区"):
    """
    获取分钟级降水数据
    """
    location = gaode.get_coordinates(location)
    if not location:
        return "未找到该地点的坐标."

    url = f"https://devapi.qweather.com/v7/minutely/5m?key={api_key}&location={location[0]},{location[1]}"
    res = requests.get(url)
    if res.status_code != 200:
        return "获取分钟级降水数据失败."
    data = json.loads(res.text)
    # print(json.dumps(data, indent=4, ensure_ascii=False))
    minutely = Minutely(**data)
    return minutely

if __name__ == "__main__":
    res = get_minutely()
    print(res.dict())