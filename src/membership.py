import random
import sqlite3
import time
import pandas as pd

conn = sqlite3.connect('secrets.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS secrets (
    secret TEXT PRIMARY KEY,
    type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expired_at TIMESTAMP,
    used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    user_id TEXT
);
''')
conn.commit()

def generate_secret(type='t1_1M'):
    '''
    生成16位的激活码，包含数字和大写字母，每隔4位加一个'-'
    '''
    secret = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=16))
    ts = int(time.time())
    c.execute("INSERT INTO secrets (secret, type, created_at) VALUES (?, ?, ?)", (secret, type, ts))
    conn.commit()
    return '-'.join([secret[i:i+4] for i in range(0, 16, 4)])

def export_secrets(type):
    '''
    导出未使用的激活码，格式为xlsx
    '''
    c.execute("SELECT secret FROM secrets WHERE type = ? AND used = FALSE", (type,))
    secrets = c.fetchall()
    secrets = [secret[0] for secret in secrets]
    # 导出的时候每一个激活码都是4位一组，中间隔着'-'
    secrets = ['-'.join([secret[i:i+4] for i in range(0, 16, 4)]) for secret in secrets]
    df = pd.DataFrame(secrets, columns=['卡券码'])
    df.to_excel(f'{type}_secrets.xlsx', index=False)
    
async def secret_verify(secret, user_id):
    '''
    验证激活码是否有效
    '''
    if '-' in secret:
        secret = secret.replace('-', '')
    user_conn = sqlite3.connect('user_info.db')
    user_c = user_conn.cursor()
    c.execute("SELECT * FROM secrets WHERE secret = ? AND used = FALSE", (secret,))
    secret_info = c.fetchone()
    if secret_info:
        ts = int(time.time())
        if secret_info[3] and ts > int(secret_info[3]):
            return False, '激活码已过期'
        type = secret_info[1]
        c.execute("UPDATE secrets SET used = TRUE, used_at = ?, user_id = ? WHERE secret = ?", (ts, user_id, secret))
        conn.commit()
        if type == 't1_1M':
            expired_at = ts + 30*24*60*60
            user_c.execute("SELECT level_expires_at FROM users WHERE user_id = ?", (user_id,))
            user_info = user_c.fetchone()
            if user_info and user_info[0] and user_info[0] > ts:
                expired_at = user_info[0] + 30*24*60*60
            user_c.execute("UPDATE users SET level = ?, level_expires_at = ? WHERE user_id = ?", ('t1', expired_at, user_id))
            user_conn.commit()
            return True, '激活成功，您已获得一个月的T1会员权限'
        else:
            user_c.execute("SELECT level_expires_at FROM users WHERE user_id = ?", (user_id,))
            user_info = user_c.fetchone()
            if user_info:
                user_c.execute("UPDATE users SET level_expires_at = ? WHERE user_id = ?", (None, user_id))
            user_c.execute("UPDATE users SET level = ? WHERE user_id = ?", ('t1', user_id))
            user_conn.commit()
            return True, '激活成功'
    else:
        return False, '激活码无效'

if __name__ == "__main__":
    print(generate_secret())