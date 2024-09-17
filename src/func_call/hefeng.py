import requests
import os
from urllib.parse import urlparse
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from . import gaode

load_dotenv()

api_key = os.getenv("HEFENG_API_KEY")

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

class Location(BaseModel):
    name: str
    id: str
    lat: str
    lon: str
    adm2: str
    adm1: str
    country: str
    tz: str
    utcOffset: str
    isDst: str
    type: str
    rank: str
    fxLink: str

def get_location(location: str):
    url = f"https://geoapi.qweather.com/v2/city/lookup?location={location}&key={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    data = json.loads(res.text)
    l = Location(**data["location"][0])
    return l

def get_now(location: str="昌平"):
    try:
        location = get_location(location)
        print(f"正在获取{location.name}的实时天气数据...")
        location_id = location.id
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