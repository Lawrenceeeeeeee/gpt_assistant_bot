import sqlite3
import time
from collections import defaultdict

# 创建用户信息数据库连接
def create_user_info_db():
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()

    # 创建用户等级表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_levels (
        user_id TEXT PRIMARY KEY,
        level TEXT
    )
    ''')
    conn.commit()
    return conn, cursor

# 创建请求记录的数据库连接
def create_requests_db():
    conn = sqlite3.connect('requests.db')
    cursor = conn.cursor()

    # 创建请求记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS requests (
        user_id TEXT,
        function_name TEXT,
        timestamp REAL
    )
    ''')
    conn.commit()
    return conn, cursor

# 存储用户请求时间戳
request_timestamps = defaultdict(list)

def get_rate_limit(user_id):
    # 根据用户ID查询其会员级别
    user_conn, user_cursor = create_user_info_db()
    user_cursor.execute('SELECT level FROM user_levels WHERE user_id = ?', (user_id,))
    level = user_cursor.fetchone()
    user_conn.close()
    
    # 定义不同会员等级的请求限制
    if level:
        if level[0] == "T-1":
            return 3600  # 管理员
        elif level[0] == "T0":
            return 20  # 正常用户
        elif level[0] == "T1":
            return 180
        else:
            raise Exception("Invalid user level.")
    else:
        # 给他加一个T0
        user_conn, user_cursor = create_user_info_db()
        user_cursor.execute('INSERT OR REPLACE INTO user_levels (user_id, level) VALUES (?, ?)', (user_id, "T0"))
        user_conn.commit()
        user_conn.close()
        return 20

def rate_limit(func):
    def wrapper(user_id, *args, **kwargs):
        max_requests = get_rate_limit(user_id)  # 根据用户查询限制
        period = 3600 # 1h
        current_time = time.time()
        
        # 清理过期的时间戳
        request_timestamps[user_id] = [t for t in request_timestamps[user_id] if current_time - t < period]
        
        if len(request_timestamps[user_id]) < max_requests:
            request_timestamps[user_id].append(current_time)

            # 记录请求到数据库
            request_conn, request_cursor = create_requests_db()
            request_cursor.execute('INSERT INTO requests (user_id, function_name, timestamp) VALUES (?, ?, ?)', 
                                   (user_id, func.__name__, current_time))
            request_conn.commit()
            request_conn.close()

            # 调用原函数
            return func(user_id, *args, **kwargs)
        else:
            raise Exception("Rate limit exceeded: Try again later.")
    return wrapper

@rate_limit
def user_request_handler(user_id, request_data):
    # 处理用户请求的代码
    return f"Request from user {user_id} processed."

if __name__ == "__main__":
    # 创建用户信息数据库连接并插入用户等级示例
    user_conn, user_cursor = create_user_info_db()
    user_cursor.execute('INSERT OR REPLACE INTO user_levels (user_id, level) VALUES (?, ?)', ("123456", "T0"))
    user_conn.commit()
    user_conn.close()

    # 使用示例
    try:
        while True:
            data = input("Enter a data: ")
            print(user_request_handler("123456", data))
    except Exception as e:
        print(e)
