import email
from math import prod
import smtplib
import redis
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from dotenv import load_dotenv
import os
import random
import hashlib
import sqlite3
import time
from datetime import timedelta
from khl import Message, PrivateMessage
import traceback
from requests import delete


r = redis.Redis(host='localhost', port=6379, db=0)

# 创建数据库表
conn = sqlite3.connect('/root/gpt_assistant_bot/user_info.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
user_id TEXT PRIMARY KEY,
student_id TEXT,
level TEXT DEFAULT 't0',
level_expires_at TIMESTAMP
);
''')
conn.commit()

load_dotenv()

# 哈希函数
def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

def generate_verification_code():
    return ''.join(random.choices('0123456789', k=6))

def send_verification_code(to_email, verification_code):
    # QQ 邮箱的 SMTP 服务器地址
    smtp_server = 'smtp.qq.com'
    smtp_port = 465
    
    # 发件人邮箱和授权码
    sender_email = os.getenv('EMAIL_ADDRESS')
    sender_password = os.getenv('EMAIL_PASSWORD')
    
    # 发件人姓名和邮箱
    sender_name = '青雀'
    
    # 收件人姓名和邮箱
    recipient_name = to_email.split('@')[0]
    recipient_email = to_email
    
    # 邮件内容
    subject = 'CUFER\'S HUB 验证码'
    html_body = f'''\
<html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f6f6f6;
                padding: 20px;
            }}
            .container {{
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #333;
            }}
            .code {{
                font-size: 24px;
                color: #007bff;
                font-weight: bold;
                margin: 10px 0;
            }}
            p {{
                color: #555;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #aaa;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>您的验证码是：</h1>
            <p class="code">{verification_code}</p>
            <p>千万不要告诉别人哦！</p>
            <p>什么? 没有申请过验证码？那就不用管这封邮件</p>
        </div>
        <div class="footer">
            <p>此邮件由CUFER'S HUB发送，请勿回复。</p>
        </div>
    </body>
</html>
    '''
    
    # 创建邮件对象
    msg = MIMEMultipart()
    msg['From'] = formataddr((sender_name, sender_email))
    msg['To'] = formataddr((recipient_name, recipient_email))
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        # 连接到 SMTP 服务器
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender_email, sender_password)
        
        # 发送邮件
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        
        # 关闭连接
        server.quit()
        print('Email sent successfully')
    except Exception as e:
        print(f'Failed to send email: {e}')

def create_captcha(user_id, student_id):
    timestamp = int(time.time())
    email = student_id + '@email.cufe.edu.cn'
    key = f"{user_id}"

    # 检查学号是否已注册
    student_id_hash = hash_value(student_id)
    c.execute("SELECT * FROM users WHERE student_id = ?", (student_id_hash,))
    conn.commit()
    if c.fetchone():
        return False, '该学号已注册。'

    # 检查是否已有验证码
    stored_data = r.hgetall(key)
    if stored_data:
        created_at = int(stored_data.get(b'created_at', 0))
        if timestamp - created_at < 60:
            return False, '验证码请求过于频繁，请稍后再试。'

    # 生成验证码
    verification_code = generate_verification_code()
    # 生成验证码哈希值
    verification_code_hash = hash_value(verification_code)

    # 存储到 Redis
    r.hset(key, mapping={
        'student_id': student_id_hash,
        'code': verification_code_hash,
        'attempts': 0,
        'created_at': timestamp
    })
    r.expire(key, timedelta(minutes=10))

    send_verification_code(email, verification_code)

    return True, '验证码已发送，请查收。'

def verify_captcha(user_id, user_code, max_attempts=3):
    key = f"{user_id}"
    stored_data = r.hgetall(key)
    
    if stored_data:
        # 获取存储的哈希值和尝试次数
        student_id = stored_data.get(b'student_id').decode('utf-8')
        stored_code_hash = stored_data.get(b'code').decode('utf-8')
        attempts = int(stored_data.get(b'attempts', 0))
        
        # 计算用户输入验证码的哈希值
        user_code_hash = hash_value(user_code)
        
        if stored_code_hash == user_code_hash:
            # 验证成功，删除验证码数据
            r.delete(key)
            
            # 将用户信息写入数据库
            c.execute("INSERT INTO users (user_id, student_id) VALUES (?, ?)", (user_id, student_id))
            conn.commit()
            
            return True, '验证成功，欢迎加入服务器！'
        else:
            # 验证失败，增加尝试次数
            attempts += 1
            if attempts >= max_attempts:
                # 尝试次数超限，作废验证码
                r.delete(key)
                return False, '尝试次数超限，验证码已失效。'
            else:
                r.hset(key, 'attempts', attempts)
                return False, f'验证码错误。还剩 {max_attempts - attempts} 次机会。'
    else:
        return False, '验证码未生成或已失效，请重新获取。'

def delete_user(user_id):
    try:
        # 删掉数据库中的用户信息
        c.execute(f"DELETE FROM users WHERE user_id = '{user_id}';")
        conn.commit()
    except Exception as e:
        print(f'Failed to delete user: {e}')

# -----------------------------------------
# 以下是命令处理函数

async def verif(msg: Message, student_id: str):
    try:
        user_id = msg.author_id
        result, message = create_captcha(user_id, student_id)
        await msg.reply(message, mention_author=False)
    except Exception as result:
        print(traceback.format_exc())

async def captcha(msg: Message, code: str):
    try:
        user_id = msg.author_id
        result, message = verify_captcha(user_id, code)
        return result, message
    except Exception as result:
        print(traceback.format_exc())
        return False, '验证失败。请联系管理员。'


if __name__ == '__main__':
    user_id = '26338xxxxxx'
    student_id = '202xxxxxxx'
    key = f"{user_id}"
    try:
        r.delete(key)
        # 删掉数据库中的用户信息
        #c.execute(f"DELETE FROM users WHERE user_id = '{user_id}';")
        #conn.commit()
    except:
        pass
    result = create_captcha(user_id, student_id)
    print(result)
    while result[0]:
        user_code = input('Enter verification code: ')
        result, message = verify_captcha(user_id, user_code)
        print(message)
        if result:
            break

    conn.close()
