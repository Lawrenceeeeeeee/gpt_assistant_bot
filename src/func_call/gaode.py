import requests
import os
from urllib.parse import urlparse
import json
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

api_key = os.getenv("GAODE_API_KEY")
# city=None, sig=None, output=None, callback=None

class POI(BaseModel):
    parent: str
    address: str
    distance: str
    pcode: str
    adcode: str
    pname: str
    cityname: str
    type: str
    typecode: str
    adname: str
    citycode: str
    name: str
    location: str
    id: str

def seconds_to_human_readable(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if seconds > 0 or len(parts) == 0:  # 处理只有秒数的情况
        parts.append(f"{seconds}秒")
    
    return "".join(parts)

def search_poi2(keywords=None, types=None, region=None, city_limit=False, show_fields=None, page_size=10, page_num=1):
    """
    构建高德地图关键字搜索API请求URL并执行查询。

    :param key: str, 必填, 用户在高德地图申请的Web服务API类型Key
    :param keywords: str, 选填, 地点关键字，长度不可超过80字符，keywords或types二选一必填
    :param types: str, 选填, 指定地点类型，多个类型用“|”分隔，keywords或types二选一必填
    :param region: str, 选填, 搜索区划，可以输入citycode，adcode，cityname
    :param city_limit: bool, 选填, 指定城市数据召回限制，为True时，仅召回region对应区域内数据
    :param show_fields: str, 选填, 返回结果控制字段，多个字段间采用“,”进行分割
    :param page_size: int, 选填, 当前分页展示的数据条数，默认为10，取值1-25
    :param page_num: int, 选填, 请求第几分页，默认为1，取值1-100
    :return: dict, 返回API响应的JSON数据
    """
    base_url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key": api_key,
        "keywords": keywords,
        "types": types,
        "region": region,
        "city_limit": "true" if city_limit else "false",
        "show_fields": show_fields,
        "page_size": page_size,
        "page_num": page_num,
        "output": "json"
    }
    
    # 过滤掉值为None的参数
    params = {k: v for k, v in params.items() if v is not None}
    
    response = requests.get(base_url, params=params)
    
    # 检查响应状态码
    if response.status_code == 200:
        if response.json()["infocode"] != "10000":
            raise Exception(response.json()["info"])
            return None
        return response.json()
    else:
        response.raise_for_status()

def route_planning(origin, destination, method="drive", show_fields="cost"):
    """
    构建高德地图路线规划API请求URL并执行查询。

    :param key: str, 必填, 用户在高德地图申请的Web服务API类型Key
    :param origin: str, 必填, 起点经纬度，格式为 "经度,纬度"
    :param destination: str, 必填, 目的地经纬度，格式为 "经度,纬度"
    :param show_fields: str, 选填, 返回结果控制字段，多个字段用逗号分隔
    :return: dict, 返回API响应的JSON数据
    """
    origin = search_poi2(origin)["pois"][0]
    destination = search_poi2(destination)["pois"][0]
    origin = POI(**origin)
    destination = POI(**destination)
    urls = {
        "drive": "https://restapi.amap.com/v5/direction/driving",
        "walk": "https://restapi.amap.com/v5/direction/walking",
        "bike": "https://restapi.amap.com/v5/direction/bicycling",
        "ebike": "https://restapi.amap.com/v5/direction/electrobike",
        "bus": "https://restapi.amap.com/v5/direction/transit/integrated",
    }
    
    base_url = urls[method]
    
    params = {
        "key": api_key,
        "origin": origin.location,
        "destination": destination.location,
        "show_fields": show_fields,
        "output": "json"
    }
    if method == "bus":
        # param增加两个地方的city_code
        params["city1"] = origin.citycode
        params["city2"] = destination.citycode
    
    # 过滤掉值为None的参数
    params = {k: v for k, v in params.items() if v is not None}
    
    response = requests.get(base_url, params=params)
    
    # 检查响应状态码
    if response.status_code == 200:
        output = {}
        if method == "drive" or method == "walk":
            output = {
                "taxi_cost(CNY)": response.json()["route"]["taxi_cost"] if "taxi_cost" in response.json()["route"] else None,
                "distance(m)": response.json()["route"]["paths"][0]["distance"],
                "duration(s)": response.json()["route"]["paths"][0]["cost"]["duration"] if "cost" in response.json()["route"]["paths"][0] else None,
            }
        elif method == "bike" or method == "ebike":
            output["duration(s)"] = response.json()["route"]["paths"][0]["duration"]
        elif method == "bus":
            output["distance(m)"] = response.json()["route"]["transits"][0]["distance"]
            output["duration(s)"] = response.json()["route"]["transits"][0]["cost"]["duration"]
        output["duration"] = seconds_to_human_readable(int(output["duration(s)"]))
        output = {k: v for k, v in output.items() if v is not None}
        
        return output    
    else:
        response.raise_for_status()

def get_coordinates(address):
    res = search_poi2(keywords=address)
    if res["count"] == 0:
        return None
    else:
        return res["pois"][0]["location"].split(",")

def get_coordinates_with_detailed_address(address):
    url = "https://restapi.amap.com/v3/geocode/geo"
    
    params = {
        "key": api_key,
        "address": address,
        "output": "json"
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "1":
            return data["geocodes"][0]["location"]
        else:
            return None
    else:
        response.raise_for_status()

import math

def haversine(lon1, lat1, lon2, lat2):
    # 地球半径，单位为公里
    R = 6371.0
    
    # 将角度转换为弧度
    lon1_rad = math.radians(lon1)
    lat1_rad = math.radians(lat1)
    lon2_rad = math.radians(lon2)
    lat2_rad = math.radians(lat2)
    
    # Haversine公式
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c  # 得到的距离，单位为公里
    return distance
     
def nearest_maimai(location, n=5):  # n为要获取的机厅数量
    location = search_poi2(keywords=location)["pois"][0]["location"]
    with open("store_data_detailed.json", "r", encoding="utf-8") as f:
        store_data = json.load(f)
    
    distances = []  # 用于存储所有机厅及其距离

    for store in store_data:
        try:
            distance_km = haversine(float(location.split(",")[0]), float(location.split(",")[1]), 
                                    float(store["location"].split(",")[0]), float(store["location"].split(",")[1]))
            store["distance(km)"] = distance_km
            distances.append(store)  # 将机厅和距离添加到列表中
        except Exception as e:
            continue  # 如果有错误，跳过该机厅

    # 按照距离排序
    distances.sort(key=lambda x: x["distance(km)"])
    
    return distances[:n]  # 返回最近的n个机厅
    