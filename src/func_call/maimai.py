from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import re
import json

# 自定义等待条件
def wait_for_li_with_chinese(driver):
    try:
        # 查找所有li元素
        li_elements = driver.find_elements(By.TAG_NAME, 'li')
        for li in li_elements:
            if re.search(r'[\u4e00-\u9fa5]', li.text):  # 检查是否有中文
                return True
        return False
    except:
        return False

chrome_options = Options()
chrome_options.add_argument("--headless")  # 无头模式
chrome_options.add_argument("--no-sandbox")  # 解决运行环境问题
chrome_options.add_argument("--disable-dev-shm-usage")  # 解决共享内存不足的问题

driver = webdriver.Chrome(options=chrome_options)
driver.get('http://wc.wahlap.net/maidx/location/index.html')  # 替换成你要爬取的网址

# 等待特定元素加载
try:
    # 等待直到li中包含中文文字
    WebDriverWait(driver, 10).until(wait_for_li_with_chinese)

    store_data = []

    # 查找所有li元素
    li_elements = driver.find_elements(By.TAG_NAME, 'li')

    for li in li_elements:
        store_name = li.find_element(By.CLASS_NAME, 'store_name').text.strip()
        store_address = li.find_element(By.CLASS_NAME, 'store_address').text.strip()
        store_data.append({'店名': store_name, '地址': store_address})

    with open('store_data.json', 'w', encoding='utf-8') as f:
        json.dump(store_data, f, ensure_ascii=False, indent=4)
    
    print(store_data[:5])

finally:
    driver.quit()  # 确保在完成后关闭浏览器
