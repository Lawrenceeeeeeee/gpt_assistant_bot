# 使用 Python 3 镜像
FROM python:3.12.6-slim

# 设置工作目录
WORKDIR /usr/src/myapp

# 将当前目录下的所有文件复制到容器中
COPY . .

# 安装依赖（从 requirements.txt 中安装）
RUN pip install --no-cache-dir -r requirements.txt

# 启动 Python 脚本
CMD ["python", "get_cryptonews.py"]