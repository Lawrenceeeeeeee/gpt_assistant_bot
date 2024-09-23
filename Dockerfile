# 使用 Ubuntu 作为基础镜像
FROM ubuntu:22.04

# 安装一些基础依赖，例如 Python 和常用工具
RUN apt-get update && apt-get install -y \
    git \
    vim \
    build-essential \
    curl \
    wget

# RUN curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
# RUN bash Miniforge3-$(uname)-$(uname -m).sh -y

# 设置工作目录
WORKDIR /usr/src/app

# 复制项目文件到容器中
COPY . .

# 安装项目依赖
# RUN pip3 install -r requirements.txt

# 运行 bash，保持容器活跃
CMD ["/bin/bash"]